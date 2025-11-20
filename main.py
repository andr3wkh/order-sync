"""
Main application - simple 4-step loop
"""
import time
from datetime import datetime, timedelta, timezone
from service import OrderSyncService
import config

print("=" * 60)
print("ORDER SYNC SYSTEM")
print("=" * 60)
print()


def main():
    """Main loop"""
    
    while True:
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting sync cycle")
        print("-" * 60)
        
        service = OrderSyncService()
        
        try:
            # Step 1: Poll source for orders (since yesterday, excluding tagged orders)
            since = datetime.now(timezone.utc) - timedelta(days=2)
            print("\n1. POLLING SOURCE STORE")
            print(f"   Looking for orders since {since.strftime('%Y-%m-%d %H:%M:%S')} (not tagged 'synced')")
            synced = service.poll_source_orders(since)
            print(f"   Result: {synced} new orders")
            
            # Step 2: Route pending orders to destinations
            print("\n2. ROUTING TO DESTINATIONS")
            sent = service.route_pending_orders()
            print(f"   Result: {sent} orders sent")
            
            # Step 3: Check for cancellations in destination
            print("\n3. CHECKING FOR CANCELLATIONS")
            cancelled = service.poll_cancellations()
            print(f"   Result: {cancelled} orders cancelled")
            
            # Step 4: Poll for tracking and sync back
            print("\n4. SYNCING TRACKING INFO")
            tracked = service.poll_tracking()
            print(f"   Result: {tracked} tracking updates")
            
            print("\n" + "=" * 60)
            print(f"Cycle complete. Waiting {config.POLL_INTERVAL} seconds...")
            print("=" * 60)
            
        except KeyboardInterrupt:
            print("\n\nShutting down...")
            service.close()
            break
        except Exception as e:
            print(f"\nERROR: {e}")
        finally:
            service.close()
        
        # Wait before next cycle
        time.sleep(config.POLL_INTERVAL)


if __name__ == '__main__':
    main()
