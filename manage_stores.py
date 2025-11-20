"""
Store management script - Add, edit, list, and delete stores
"""
import sys
from models import Store, OrderRouting, get_db, init_db
from datetime import datetime


def list_stores():
    """List all stores"""
    db = get_db()
    stores = db.query(Store).order_by(Store.role, Store.id).all()
    
    if not stores:
        print("No stores configured.")
        return
    
    print("\n" + "=" * 80)
    print("CONFIGURED STORES")
    print("=" * 80)
    
    for store in stores:
        role_label = store.role.upper()
        print(f"\n[{store.id}] {store.name} ({role_label})")
        print(f"    Type: {store.store_type}")
        print(f"    URL: {store.shop_url}")
        print(f"    Access Token: {store.access_token[:10]}..." if len(store.access_token) > 10 else f"    Access Token: {store.access_token}")
        print(f"    Created: {store.created_at}")
    
    print("\n" + "=" * 80)
    db.close()


def add_store():
    """Add a new store"""
    print("\n" + "=" * 80)
    print("ADD NEW STORE")
    print("=" * 80)
    
    # Get store details
    name = input("Store name: ").strip()
    if not name:
        print("Error: Name is required")
        return
    
    print("\nRole:")
    print("  1. Source (orders come FROM here)")
    print("  2. Destination (orders go TO here)")
    role_choice = input("Select role (1 or 2): ").strip()
    
    if role_choice == "1":
        role = "source"
    elif role_choice == "2":
        role = "destination"
    else:
        print("Error: Invalid role")
        return
    
    print("\nStore type:")
    print("  1. Shopify")
    print("  2. WooCommerce (not yet implemented)")
    type_choice = input("Select type (1 or 2): ").strip()
    
    if type_choice == "1":
        store_type = "shopify"
    elif type_choice == "2":
        store_type = "woocommerce"
    else:
        print("Error: Invalid type")
        return
    
    shop_url = input("\nShop URL (e.g., mystore.myshopify.com): ").strip()
    if not shop_url:
        print("Error: Shop URL is required")
        return
    
    access_token = input("Access Token (shpat_xxx): ").strip()
    if not access_token:
        print("Error: Access Token is required")
        return
    
    api_version = input("API Version (default: 2024-01): ").strip() or "2024-01"
    
    # Confirm
    print("\n" + "-" * 80)
    print("CONFIRM DETAILS:")
    print(f"  Name: {name}")
    print(f"  Role: {role}")
    print(f"  Type: {store_type}")
    print(f"  URL: {shop_url}")
    print(f"  Access Token: {access_token[:10]}...")
    print(f"  API Version: {api_version}")
    print("-" * 80)
    
    confirm = input("\nAdd this store? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Cancelled.")
        return
    
    # Save to database
    db = get_db()
    
    store = Store(
        name=name,
        store_type=store_type,
        role=role,
        shop_url=shop_url,
        access_token=access_token,
        api_version=api_version
    )
    
    db.add(store)
    db.commit()
    
    print(f"\n✓ Store '{name}' added successfully (ID: {store.id})")
    db.close()


def delete_store():
    """Delete a store"""
    db = get_db()
    stores = db.query(Store).all()
    
    if not stores:
        print("No stores to delete.")
        db.close()
        return
    
    print("\n" + "=" * 80)
    print("DELETE STORE")
    print("=" * 80)
    
    for store in stores:
        print(f"[{store.id}] {store.name} ({store.role})")
    
    store_id = input("\nEnter store ID to delete (or 'c' to cancel): ").strip()
    
    if store_id.lower() == 'c':
        print("Cancelled.")
        db.close()
        return
    
    try:
        store_id = int(store_id)
    except ValueError:
        print("Error: Invalid ID")
        db.close()
        return
    
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        print(f"Error: Store {store_id} not found")
        db.close()
        return
    
    print(f"\nAre you sure you want to delete '{store.name}'?")
    confirm = input("Type 'DELETE' to confirm: ").strip()
    
    if confirm == "DELETE":
        db.delete(store)
        db.commit()
        print(f"✓ Store '{store.name}' deleted")
    else:
        print("Cancelled.")
    
    db.close()


def list_routing():
    """List routing rules"""
    db = get_db()
    rules = db.query(OrderRouting).order_by(OrderRouting.priority.desc()).all()
    
    if not rules:
        print("\nNo routing rules configured.")
        print("By default, orders will be sent to the first destination store.")
        db.close()
        return
    
    print("\n" + "=" * 80)
    print("ROUTING RULES")
    print("=" * 80)
    
    for rule in rules:
        status = "ACTIVE" if rule.is_active else "INACTIVE"
        print(f"\n[{rule.id}] {rule.source_store.name} → {rule.destination_store.name} ({status})")
        print(f"    Priority: {rule.priority}")
        print(f"    Routing Method: {rule.routing_method}")
        if rule.routing_method_value:
            print(f"    Match Value: {rule.routing_method_value}")
        print(f"    Product Lookup: {rule.lookup_method.upper()}")
        if rule.notes:
            print(f"    Notes: {rule.notes}")
    
    print("\n" + "=" * 80)
    db.close()


def add_routing_rule():
    """Add a routing rule"""
    db = get_db()
    
    # First, select source store
    sources = db.query(Store).filter(Store.role == 'source').all()
    if not sources:
        print("\nError: No source stores configured. Add a source store first.")
        db.close()
        return
    
    print("\n" + "=" * 80)
    print("ADD ROUTING RULE")
    print("=" * 80)
    print("\nAvailable source stores:")
    
    for src in sources:
        print(f"  [{src.id}] {src.name}")
    
    source_id = input("\nSelect source store ID: ").strip()
    try:
        source_id = int(source_id)
    except ValueError:
        print("Error: Invalid ID")
        db.close()
        return
    
    source = db.query(Store).filter(Store.id == source_id, Store.role == 'source').first()
    if not source:
        print("Error: Invalid source store")
        db.close()
        return
    
    # Now select destination
    destinations = db.query(Store).filter(Store.role == 'destination').all()
    if not destinations:
        print("\nError: No destination stores configured. Add a destination store first.")
        db.close()
        return
    
    print("\nAvailable destination stores:")
    
    for dest in destinations:
        print(f"  [{dest.id}] {dest.name}")
    
    dest_id = input("\nSelect destination ID: ").strip()
    try:
        dest_id = int(dest_id)
    except ValueError:
        print("Error: Invalid ID")
        db.close()
        return
    
    dest = db.query(Store).filter(Store.id == dest_id, Store.role == 'destination').first()
    if not dest:
        print("Error: Invalid destination")
        db.close()
        return
    
    print("\nRouting method (how to determine which orders go here):")
    print("  1. All - Send ALL orders to this destination")
    print("  2. Order Tags - Send orders with specific line item tag")
    routing_choice = input("Select routing method (1 or 2): ").strip()
    
    routing_method = 'all' if routing_choice == '1' else 'order_tags' if routing_choice == '2' else None
    if not routing_method:
        print("Error: Invalid routing method")
        db.close()
        return
    
    routing_method_value = None
    if routing_method == 'order_tags':
        routing_method_value = input("Tag to match (e.g., 'Zinaps'): ").strip()
        if not routing_method_value:
            print("Error: Tag value is required for order_tags routing")
            db.close()
            return
    
    print("\nProduct lookup method in destination store:")
    print("  1. SKU - Match products by SKU")
    print("  2. EAN - Match products by EAN/barcode")
    lookup_choice = input("Select lookup method (1 or 2): ").strip()
    
    lookup_method = 'sku' if lookup_choice == '1' else 'ean' if lookup_choice == '2' else None
    if not lookup_method:
        print("Error: Invalid lookup method")
        db.close()
        return
    
    priority = input("\nPriority (higher = checked first, default: 0): ").strip()
    try:
        priority = int(priority) if priority else 0
    except ValueError:
        priority = 0
    
    notes = input("Notes (optional): ").strip() or None
    
    # Confirm
    print("\n" + "-" * 80)
    print("ROUTING RULE SUMMARY:")
    print(f"  Source: {source.name}")
    print(f"  Destination: {dest.name}")
    print(f"  Routing Method: {routing_method}")
    if routing_method_value:
        print(f"  Match Value: {routing_method_value}")
    print(f"  Product Lookup: {lookup_method.upper()}")
    print(f"  Priority: {priority}")
    if notes:
        print(f"  Notes: {notes}")
    print("-" * 80)
    
    confirm = input("\nAdd this routing rule? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Cancelled.")
        db.close()
        return
    
    rule = OrderRouting(
        source_store_id=source_id,
        destination_store_id=dest_id,
        routing_method=routing_method,
        routing_method_value=routing_method_value,
        lookup_method=lookup_method,
        priority=priority,
        notes=notes
    )
    
    db.add(rule)
    db.commit()
    
    print(f"\n✓ Routing rule added (ID: {rule.id})")
    db.close()


def main_menu():
    """Main menu"""
    # Initialize database
    init_db()
    
    while True:
        print("\n" + "=" * 80)
        print("STORE MANAGEMENT")
        print("=" * 80)
        print("\n1. List stores")
        print("2. Add store")
        print("3. Delete store")
        print("4. List routing rules")
        print("5. Add routing rule")
        print("6. Exit")
        
        choice = input("\nSelect option: ").strip()
        
        if choice == "1":
            list_stores()
        elif choice == "2":
            add_store()
        elif choice == "3":
            delete_store()
        elif choice == "4":
            list_routing()
        elif choice == "5":
            add_routing_rule()
        elif choice == "6":
            print("\nGoodbye!")
            break
        else:
            print("Invalid option")


if __name__ == '__main__':
    try:
        main_menu()
    except KeyboardInterrupt:
        print("\n\nInterrupted.")
        sys.exit(0)
