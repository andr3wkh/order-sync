"""
Shopify connector implementation using REST API
"""
import requests
from typing import List, Dict, Optional
from datetime import datetime
from .base import StoreConnector


class ShopifyConnector(StoreConnector):
    """Shopify store connector using REST API"""
    
    def __init__(self, config: Dict):
        super().__init__(config)
        
        self.shop_url = config['shop_url']
        self.access_token = config['access_token']
        self.api_version = config.get('api_version', '2024-01')
        
        # Base URL for API requests
        self.base_url = f"https://{self.shop_url}/admin/api/{self.api_version}"
        
        # Setup session with auth
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'X-Shopify-Access-Token': self.access_token
        })
    
    def fetch_orders(self, since: datetime) -> List[Dict]:
        """Fetch unfulfilled orders from Shopify - exclude orders tagged with 'synced'"""
        url = f"{self.base_url}/orders.json"
        params = {
            'created_at_min': since.isoformat(),
            'status': 'any',
            'fulfillment_status': 'unfulfilled',  # Only unfulfilled orders
            'limit': 250
        }
        
        response = self.session.get(url, params=params)
        response.raise_for_status()
        
        orders = response.json().get('orders', [])
        
        # Filter out orders that are already tagged as 'synced', cancelled, or refunded
        unsynced_orders = [
            order for order in orders 
            if 'synced' not in [tag.lower() for tag in order.get('tags', '').split(',')]
            and order.get('cancelled_at') is None
            and order.get('financial_status') not in ['voided', 'refunded', 'partially_refunded']
        ]
        
        return [self._serialize_order(order) for order in unsynced_orders]
    
    def create_order(self, order_data: Dict) -> Dict:
        """Create order in Shopify - looks up existing products by SKU/EAN"""
        url = f"{self.base_url}/orders.json"
        
        # Determine lookup method (default to 'sku' if not specified)
        lookup_method = order_data.get('lookup_method', 'sku')
        
        # Build order payload - lookup products by SKU or EAN with fallback
        line_items = []
        for item in order_data.get('line_items', []):
            # Find existing product variant in destination store
            variant_id = None
            lookup_used = None
            
            if lookup_method == 'sku' and item.get('sku'):
                # Primary: Search by SKU
                variant_id = self._find_variant_by_sku(item['sku'])
                lookup_used = 'sku'
                
                # Fallback: Try EAN if SKU lookup failed
                if not variant_id and item.get('ean'):
                    variant_id = self._find_variant_by_barcode(item['ean'])
                    if variant_id:
                        lookup_used = 'ean (fallback)'
                        
            elif lookup_method == 'ean' and item.get('ean'):
                # Primary: Search by EAN/barcode
                variant_id = self._find_variant_by_barcode(item['ean'])
                lookup_used = 'ean'
                
                # Fallback: Try SKU if EAN lookup failed
                if not variant_id and item.get('sku'):
                    variant_id = self._find_variant_by_sku(item['sku'])
                    if variant_id:
                        lookup_used = 'sku (fallback)'
            
            if not variant_id:
                print(f"    ⚠ Warning: Product not found in destination - sku={item.get('sku')}, ean={item.get('ean')}, title='{item.get('title')}'")
                continue
            
            line_item = {
                'variant_id': variant_id,
                'quantity': item['quantity'],
            }
            
            line_items.append(line_item)
        
        if not line_items:
            raise Exception("No valid line items found - all products missing in destination store")
        
        # Build notes with source order info
        notes = []
        if order_data.get('source_store_name'):
            notes.append(f"ChannelName\n{order_data['source_store_name']}")
        if order_data.get('source_order_number'):
            notes.append(f"ChannelOrderNo\n{order_data['source_order_number']}")
        notes.append("Integrator\ninit_sync")
        note_content = '\n\n'.join(notes)
        
        # Build customer object
        customer = {}
        if order_data.get('customer_name'):
            # Split name into first and last
            name_parts = order_data['customer_name'].split(' ', 1)
            customer['first_name'] = name_parts[0]
            customer['last_name'] = name_parts[1] if len(name_parts) > 1 else ''
        if order_data.get('customer_email'):
            customer['email'] = order_data['customer_email']
        if order_data.get('customer_phone'):
            customer['phone'] = order_data['customer_phone']
        
        payload = {
            'order': {
                'email': order_data.get('customer_email'),
                'line_items': line_items,
                'note': note_content,
                'customer': customer if customer else None,
                'shipping_address': order_data.get('shipping_address'),
                'billing_address': order_data.get('billing_address'),
            }
        }
        
        response = self.session.post(url, json=payload)
        response.raise_for_status()
        
        created_order = response.json().get('order', {})
        return self._serialize_order(created_order)
    
    def get_order(self, order_id: str) -> Optional[Dict]:
        """Get order by ID"""
        try:
            url = f"{self.base_url}/orders/{order_id}.json"
            response = self.session.get(url)
            response.raise_for_status()
            
            order = response.json().get('order', {})
            return self._serialize_order(order) if order else None
        except requests.exceptions.RequestException:
            return None
    
    def update_tracking(self, order_id: str, tracking: Dict) -> bool:
        """Update order with tracking (creates fulfillment using FulfillmentOrders API)"""
        try:
            # Step 1: Get fulfillment orders for this order
            fulfillment_orders_url = f"{self.base_url}/orders/{order_id}/fulfillment_orders.json"
            response = self.session.get(fulfillment_orders_url)
            response.raise_for_status()
            
            fulfillment_orders = response.json().get('fulfillment_orders', [])
            if not fulfillment_orders:
                print(f"      ✗ No fulfillment orders found for order {order_id}")
                return False
            
            # Find an open fulfillment order (skip closed/cancelled ones)
            fulfillment_order = None
            for fo in fulfillment_orders:
                status = fo.get('status', '')
                if status == 'open':
                    fulfillment_order = fo
                    break
            
            if not fulfillment_order:
                print(f"      ⚠ All fulfillment orders are closed/cancelled for order {order_id}")
                return True  # Return True to mark as processed (don't retry)
            
            fulfillment_order_id = fulfillment_order['id']
            
            # Build line items from fulfillment order
            line_items_by_fulfillment_order = [{
                'fulfillment_order_id': fulfillment_order_id
            }]
            
            # Step 2: Create fulfillment using the new API
            fulfillments_url = f"{self.base_url}/fulfillments.json"
            payload = {
                'fulfillment': {
                    'line_items_by_fulfillment_order': line_items_by_fulfillment_order,
                    'tracking_info': {
                        'number': tracking['tracking_number'],
                        'company': tracking.get('tracking_company', ''),
                        'url': tracking.get('tracking_url', '')
                    },
                    'notify_customer': False
                }
            }
            
            response = self.session.post(fulfillments_url, json=payload)
            response.raise_for_status()
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"      ✗ Failed to create fulfillment: {e}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    print(f"      ✗ API Error: {error_detail}")
                except:
                    print(f"      ✗ Response: {e.response.text}")
            return False
    
    def tag_order(self, order_id: str, tag: str) -> bool:
        """Add a tag to an order (preserves existing tags)"""
        try:
            # Get the current order directly from API (not serialized)
            url = f"{self.base_url}/orders/{order_id}.json"
            response = self.session.get(url)
            response.raise_for_status()
            order = response.json().get('order', {})
            
            if not order:
                return False
            
            # Get existing tags from the raw order
            existing_tags = order.get('tags', '').strip()
            
            # Check if tag already exists
            tag_list = [t.strip() for t in existing_tags.split(',') if t.strip()]
            if tag.lower() in [t.lower() for t in tag_list]:
                return True  # Already tagged
            
            # Add new tag
            tag_list.append(tag)
            new_tags = ', '.join(tag_list)
            
            # Update order with new tags
            url = f"{self.base_url}/orders/{order_id}.json"
            payload = {
                'order': {
                    'id': order_id,
                    'tags': new_tags
                }
            }
            
            response = self.session.put(url, json=payload)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException:
            return False
    
    def cancel_order(self, order_id: str, reason: str = 'other') -> bool:
        """Cancel an order in Shopify"""
        try:
            url = f"{self.base_url}/orders/{order_id}/cancel.json"
            payload = {
                'reason': reason  # 'customer', 'inventory', 'fraud', 'declined', 'other'
            }
            
            response = self.session.post(url, json=payload)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            print(f"      ✗ Failed to cancel order: {e}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    print(f"      ✗ API Error: {error_detail}")
                except:
                    print(f"      ✗ Response: {e.response.text}")
            return False
    
    def _get_variant_barcode(self, variant_id: str) -> Optional[str]:
        """Fetch barcode/EAN for a variant from Shopify API"""
        try:
            if not variant_id:
                return None
            
            url = f"{self.base_url}/variants/{variant_id}.json"
            response = self.session.get(url)
            response.raise_for_status()
            
            variant = response.json().get('variant', {})
            return variant.get('barcode')
        except requests.exceptions.RequestException:
            return None
    
    def _find_variant_by_sku(self, sku: str) -> Optional[int]:
        """Find product variant ID by SKU in destination store"""
        try:
            if not sku:
                return None
            
            # Fetch all products using pagination
            url = f"{self.base_url}/products.json"
            params = {'limit': 250}
            
            while url:
                response = self.session.get(url, params=params)
                response.raise_for_status()
                
                products = response.json().get('products', [])
                
                # Check variants in this batch
                for product in products:
                    for variant in product.get('variants', []):
                        if variant.get('sku') == sku:
                            return variant['id']
                
                # Check for next page (Link header)
                link_header = response.headers.get('Link', '')
                if 'rel="next"' in link_header:
                    # Extract next URL from Link header
                    next_link = [l for l in link_header.split(',') if 'rel="next"' in l]
                    if next_link:
                        url = next_link[0].split(';')[0].strip('<> ')
                        params = {}  # URL already has params
                    else:
                        url = None
                else:
                    url = None
            
            return None
        except requests.exceptions.RequestException:
            return None
    
    def _find_variant_by_barcode(self, barcode: str) -> Optional[int]:
        """Find product variant ID by barcode/EAN in destination store"""
        try:
            if not barcode:
                return None
            
            # Fetch all products using pagination
            url = f"{self.base_url}/products.json"
            params = {'limit': 250}
            
            while url:
                response = self.session.get(url, params=params)
                response.raise_for_status()
                
                products = response.json().get('products', [])
                
                # Check variants in this batch
                for product in products:
                    for variant in product.get('variants', []):
                        if variant.get('barcode') == barcode:
                            return variant['id']
                
                # Check for next page (Link header)
                link_header = response.headers.get('Link', '')
                if 'rel="next"' in link_header:
                    # Extract next URL from Link header
                    next_link = [l for l in link_header.split(',') if 'rel="next"' in l]
                    if next_link:
                        url = next_link[0].split(';')[0].strip('<> ')
                        params = {}  # URL already has params
                    else:
                        url = None
                else:
                    url = None
            
            return None
        except requests.exceptions.RequestException:
            return None
    
    def _serialize_order(self, order: Dict) -> Dict:
        """Convert Shopify API response to standardized dict"""
        # Collect order-level tags (Shopify stores order tags as a comma-separated string)
        order_tags = order.get('tags') or ''

        def _line_tags(item):
            # Line item properties may be present; properties are often a list of {name, value} dicts
            props = item.get('properties') or []
            prop_vals = []
            # If properties is a list of dicts, extract values; if it's a list of strings, use them directly
            for p in props:
                if isinstance(p, dict):
                    # combine name and value when available
                    if p.get('value'):
                        prop_vals.append(str(p.get('value')))
                    elif p.get('name'):
                        prop_vals.append(str(p.get('name')))
                else:
                    prop_vals.append(str(p))

            # Combine order-level tags with any property-derived tags
            combined = []
            if order_tags:
                combined.extend([t.strip() for t in order_tags.split(',') if t.strip()])
            if prop_vals:
                combined.extend([t.strip() for t in prop_vals if t.strip()])

            return ','.join(combined) if combined else None

        # Extract customer info
        customer = order.get('customer') or {}
        customer_name = f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip()
        
        return {
            'id': str(order.get('id', '')),
            'order_number': order.get('order_number') or order.get('name'),
            'email': order.get('email') or customer.get('email'),
            'customer_name': customer_name if customer_name else None,
            'customer_phone': customer.get('phone') or order.get('phone'),
            'created_at': order.get('created_at'),
            'total_price': str(order.get('total_price', '0')),
            'currency': order.get('currency'),
            'fulfillment_status': order.get('fulfillment_status'),
            'financial_status': order.get('financial_status'),
            'cancelled_at': order.get('cancelled_at'),
            'cancel_reason': order.get('cancel_reason'),
            'shipping_address': order.get('shipping_address'),
            'billing_address': order.get('billing_address'),
            'line_items': [
                {
                    'id': str(item.get('id', '')),
                    'product_id': str(item.get('product_id')) if item.get('product_id') else None,
                    'variant_id': str(item.get('variant_id')) if item.get('variant_id') else None,
                    'sku': item.get('sku'),
                    'ean': self._get_variant_barcode(item.get('variant_id')) if item.get('variant_id') else None,
                    'title': item.get('title'),
                    'quantity': item.get('quantity'),
                    'price': str(item.get('price', '0')),
                    'tags': _line_tags(item),
                }
                for item in order.get('line_items', [])
            ],
            'fulfillments': [
                {
                    'tracking_number': f.get('tracking_number'),
                    'tracking_company': f.get('tracking_company'),
                    'tracking_url': f.get('tracking_url'),
                }
                for f in order.get('fulfillments', [])
            ]
        }
