"""
Core order synchronization service
"""
from datetime import datetime, timezone, timedelta
from typing import List, Optional
import fnmatch
from models import Store, Order, OrderLine, OrderRouting, get_db
from connectors import get_connector


class OrderSyncService:
    """Handles the 4-step order sync process"""
    
    def __init__(self):
        self.db = get_db()
    
    # Step 1: Poll source store for orders
    def poll_source_orders(self, since: datetime) -> int:
        """Poll all source stores, save new orders to DB"""
        
        # Get all source stores
        sources = self.db.query(Store).filter(Store.role == 'source').all()
        if not sources:
            print("ERROR: No source stores configured")
            return 0
        
        total_synced = 0
        for source in sources:
            print(f"\nPolling {source.name} for orders since {since}")
            
            # Get connector
            connector = get_connector(source.store_type, {
                'shop_url': source.shop_url,
                'access_token': source.access_token,
                'api_version': source.api_version,
            })
            
            # Fetch orders
            orders = connector.fetch_orders(since)
            print(f"Found {len(orders)} orders")
            
            synced = 0
            for order_data in orders:
                # Check if already exists (by source_store_id + source_order_id)
                exists = self.db.query(Order).filter(
                    Order.source_store_id == source.id,
                    Order.source_order_id == str(order_data['id'])  # Ensure string comparison
                ).first()
                
                if exists:
                    print(f"  Skipping order {order_data['order_number']} - already imported (order_id={order_data['id']})")
                    continue
                
                # Skip orders created less than 5 minutes ago (give time for order to be complete)
                order_created_at = datetime.fromisoformat(order_data['created_at'].replace('Z', '+00:00'))
                five_mins_ago = datetime.now(timezone.utc) - timedelta(minutes=5)
                if order_created_at > five_mins_ago:
                    print(f"  Skipping order {order_data['order_number']} - created less than 5 mins ago")
                    continue
                
                # Create order
                order = Order(
                    source_store_id=source.id,
                    source_order_id=order_data['id'],
                    order_number=order_data.get('order_number'),
                    customer_email=order_data.get('email'),
                    customer_name=order_data.get('customer_name'),
                    customer_phone=order_data.get('customer_phone'),
                    total_price=order_data.get('total_price'),
                    currency=order_data.get('currency'),
                    shipping_address=order_data.get('shipping_address'),
                    billing_address=order_data.get('billing_address'),
                    order_json=order_data,  # Store full order JSON
                    status='pending'
                )
                self.db.add(order)
                self.db.flush()
                
                # Create order lines
                for line_data in order_data.get('line_items', []):
                    line = OrderLine(
                        order_id=order.id,
                        sku=line_data.get('sku'),
                        ean=line_data.get('ean'),
                        product_id=line_data.get('product_id'),
                        title=line_data.get('title'),
                        quantity=line_data.get('quantity'),
                        price=line_data.get('price'),
                        tags=line_data.get('tags')
                    )
                    self.db.add(line)
                
                self.db.commit()
                synced += 1
                print(f"  Saved order {order_data['order_number']}")
            
            total_synced += synced
        
        return total_synced
    
    # Step 2: Route pending orders to destinations
    def route_pending_orders(self) -> int:
        """Route orders to appropriate destinations based on routing rules"""
        
        # Get pending orders AND failed orders that haven't been retried in 10 minutes
        ten_mins_ago = datetime.now(timezone.utc) - timedelta(minutes=10)
        
        pending = self.db.query(Order).filter(
            (Order.status == 'pending') |
            ((Order.status == 'failed') & (Order.created_at < ten_mins_ago))
        ).all()
        
        if not pending:
            return 0
        
        failed_count = len([o for o in pending if o.status == 'failed'])
        if failed_count > 0:
            print(f"Routing {len(pending)} orders ({len(pending) - failed_count} pending, {failed_count} failed retries)")
        else:
            print(f"Routing {len(pending)} pending orders")
        
        sent = 0
        for order in pending:
            try:
                # Get all active routing configs for this order's source store (sorted by priority)
                active_routes = self.db.query(OrderRouting).filter(
                    OrderRouting.is_active == 1,
                    OrderRouting.source_store_id == order.source_store_id
                ).order_by(OrderRouting.priority.desc()).all()
                
                if not active_routes:
                    print(f"  Order {order.order_number}: No routing rules found for source store, skipping")
                    continue
                
                # Find matching destinations for this order
                matched_routes = self._find_matching_routes(order, active_routes)
                
                if not matched_routes:
                    print(f"  Order {order.order_number}: No matching destination found, skipping")
                    continue
                
                # Send to all matched destinations
                for route in matched_routes:
                    dest = route.destination_store
                    lookup_method = route.lookup_method
                    
                    print(f"  Sending order {order.order_number} to {dest.name}")
                    
                    # Get connector
                    connector = get_connector(dest.store_type, {
                        'shop_url': dest.shop_url,
                        'access_token': dest.access_token,
                        'api_version': dest.api_version,
                    })
                    
                    # Prepare order data with appropriate lookup field
                    order_data = {
                        'lookup_method': lookup_method,  # Pass lookup method to connector
                        'source_store_name': order.source_store.name,
                        'source_order_number': order.order_number,
                        'customer_email': order.customer_email,
                        'customer_name': order.customer_name,
                        'customer_phone': order.customer_phone,
                        'shipping_address': order.shipping_address,
                        'billing_address': order.billing_address,
                        'line_items': [
                            {
                                'sku': line.sku,
                                'ean': line.ean,
                                'title': line.title,
                                'quantity': line.quantity,
                                'price': float(line.price) if line.price else 0,
                            }
                            for line in order.order_lines
                        ]
                    }
                    
                    # Create order in destination
                    created = connector.create_order(order_data)
                    
                    # Update order record with destination info (always set, even for multi-destination)
                    order.destination_store_id = dest.id
                    order.destination_order_id = created['id']
                    
                    sent += 1
                    print(f"    ✓ Created as order {created.get('order_number')} (ID: {created.get('id')})")
                
                # Tag the source order as 'synced'
                source = order.source_store
                source_connector = get_connector(source.store_type, {
                    'shop_url': source.shop_url,
                    'access_token': source.access_token,
                    'api_version': source.api_version,
                })
                
                tagged = source_connector.tag_order(order.source_order_id, 'synced')
                if tagged:
                    print("    ✓ Tagged source order as 'synced'")
                else:
                    print("    ⚠ Could not tag source order")
                
                # Mark order as synced after sending to all destinations
                order.status = 'synced'
                order.synced_at = datetime.now(timezone.utc)
                self.db.commit()
                
            except Exception as e:
                print(f"    ✗ Error: {e}")
                order.status = 'failed'
                self.db.commit()
        
        return sent
    
    # Step 3: Poll destinations for cancellations
    def poll_cancellations(self) -> int:
        """Check synced orders in destination for cancellations and cancel in source"""
        
        # Get orders that are synced but tracking hasn't been synced yet (open orders only)
        orders = self.db.query(Order).filter(
            Order.status == 'synced',
            Order.tracking_synced_at.is_(None),
            Order.destination_store_id.isnot(None),
            Order.destination_order_id.isnot(None)
        ).all()
        
        if not orders:
            return 0
        
        print(f"Checking {len(orders)} synced orders for cancellations")
        
        cancelled_count = 0
        for order in orders:
            try:
                dest = order.destination_store
                if not dest:
                    continue
                
                # Get connector
                connector = get_connector(dest.store_type, {
                    'shop_url': dest.shop_url,
                    'access_token': dest.access_token,
                    'api_version': dest.api_version,
                })
                
                # Fetch order from destination
                dest_order = connector.get_order(order.destination_order_id)
                if not dest_order:
                    continue
                
                # Check if order is cancelled in destination
                is_cancelled = (
                    dest_order.get('cancelled_at') is not None or
                    dest_order.get('financial_status') == 'voided'
                )
                
                if is_cancelled:
                    print(f"  Order {order.order_number}: Cancelled in destination, cancelling in source...")
                    
                    # Cancel in source
                    source = order.source_store
                    source_connector = get_connector(source.store_type, {
                        'shop_url': source.shop_url,
                        'access_token': source.access_token,
                        'api_version': source.api_version,
                    })
                    
                    cancel_reason = dest_order.get('cancel_reason', 'other')
                    success = source_connector.cancel_order(order.source_order_id, cancel_reason)
                    
                    if success:
                        order.status = 'cancelled'
                        order.tracking_synced_at = datetime.now(timezone.utc)  # Mark as processed
                        self.db.commit()
                        cancelled_count += 1
                        print(f"    ✓ Order cancelled in source")
                    else:
                        print(f"    ✗ Failed to cancel order in source")
                
            except Exception as e:
                print(f"  Order {order.order_number}: ✗ Exception: {e}")
        
        return cancelled_count
    
    # Step 4: Poll destinations for tracking
    def poll_tracking(self) -> int:
        """Check synced orders for tracking info"""
        
        # Check orders that are synced but don't have tracking synced back to source yet
        # Add 5 minute delay - only check orders synced more than 5 mins ago
        # Exclude cancelled orders
        five_mins_ago = datetime.now(timezone.utc) - timedelta(minutes=5)
        
        orders = self.db.query(Order).filter(
            Order.status == 'synced',
            Order.tracking_synced_at.is_(None),
            Order.synced_at < five_mins_ago  # Only orders synced more than 5 mins ago
        ).all()
        
        if not orders:
            return 0
        
        print(f"Checking {len(orders)} orders for tracking (order_numbers: {', '.join([o.order_number for o in orders])})")
        
        updated = 0
        for order in orders:
            try:
                if not order.destination_store_id or not order.destination_order_id:
                    print(f"  Order {order.order_number}: Missing destination info (store_id={order.destination_store_id}, order_id={order.destination_order_id})")
                    continue
                
                dest = order.destination_store
                if not dest:
                    print(f"  Order {order.order_number}: Destination store not found")
                    continue
                
                # Get connector
                connector = get_connector(dest.store_type, {
                    'shop_url': dest.shop_url,
                    'access_token': dest.access_token,
                    'api_version': dest.api_version,
                })
                
                # Fetch order
                dest_order = connector.get_order(order.destination_order_id)
                if not dest_order:
                    print(f"  Order {order.order_number}: Could not fetch from destination")
                    continue
                
                # Check for tracking
                tracking = self._extract_tracking(dest_order)
                if not tracking:
                    # Show fulfillment status for debugging
                    fulfillment_status = dest_order.get('fulfillment_status', 'unknown')
                    fulfillments = dest_order.get('fulfillments', [])
                    fulfillment_count = len(fulfillments)
                    has_tracking = bool(fulfillments and fulfillments[0].get('tracking_number')) if fulfillments else False
                    print(f"  Order {order.order_number}: No tracking (dest fulfillment_status={fulfillment_status}, fulfillments={fulfillment_count}, has_tracking_in_first={has_tracking})")
                    continue
                
                print(f"  Found tracking for order {order.order_number}: {tracking['tracking_number']}")
                
                # Update local order with tracking info
                if not order.tracking_number:
                    order.tracking_number = tracking['tracking_number']
                    order.tracking_company = tracking.get('tracking_company')
                    order.tracking_url = tracking.get('tracking_url')
                    self.db.commit()
                
                # Sync back to source
                print(f"    Syncing tracking to source store...")
                if self._sync_tracking_to_source(order, tracking):
                    order.status = 'tracking_updated'
                    order.tracking_synced_at = datetime.now(timezone.utc)
                    updated += 1
                    print(f"    ✓ Tracking synced to source successfully")
                else:
                    print(f"    ✗ Failed to sync tracking to source")
                
                self.db.commit()
                
            except Exception as e:
                print(f"  Order {order.order_number}: ✗ Exception: {e}")
                import traceback
                traceback.print_exc()
        
        return updated
    
    # Helper: Find matching routes for an order
    def _find_matching_routes(self, order: Order, routes: List[OrderRouting]) -> List[OrderRouting]:
        """Find which destination routes match this order"""
        matched = []
        
        for route in routes:
            # Route to 'all' - matches everything
            if route.routing_method == 'all':
                matched.append(route)
                continue
            
            # Route by 'order_tags' - check if any line item has the matching tag
            if route.routing_method == 'order_tags' and route.routing_method_value:
                target_tag = route.routing_method_value.lower().strip()
                
                for line in order.order_lines:
                    if line.tags:
                        line_tags = [t.strip().lower() for t in line.tags.split(',') if t.strip()]
                        if target_tag in line_tags:
                            matched.append(route)
                            break  # Found match, no need to check other lines
        
        return matched
    
    # Helper: Extract tracking from order data
    def _extract_tracking(self, order_data: dict) -> Optional[dict]:
        """Extract tracking info from order"""
        if order_data.get('fulfillment_status') not in ['fulfilled', 'partial']:
            return None
        
        fulfillments = order_data.get('fulfillments', [])
        if fulfillments and len(fulfillments) > 0:
            f = fulfillments[0]
            if f.get('tracking_number'):
                return {
                    'tracking_number': f['tracking_number'],
                    'tracking_company': f.get('tracking_company'),
                    'tracking_url': f.get('tracking_url'),
                }
        
        return None
    
    # Helper: Sync tracking back to source
    def _sync_tracking_to_source(self, order: Order, tracking: dict) -> bool:
        """Update source store with tracking"""
        try:
            source = order.source_store
            
            connector = get_connector(source.store_type, {
                'shop_url': source.shop_url,
                'access_token': source.access_token,
                'api_version': source.api_version,
            })
            
            return connector.update_tracking(order.source_order_id, tracking)
        except:
            return False
    
    def close(self):
        """Close database connection"""
        self.db.close()
