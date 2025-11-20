# Order Sync System - Project Structure

```
order-sync/
├── config.py              # Configuration (loads from .env)
├── models.py              # Database models (stores, orders, order_lines, routing)
├── service.py             # Core business logic (4-step sync process)
├── main.py                # Application entry point (main loop)
├── setup.py               # Database initialization script
│
├── connectors/            # Store integrations (modular)
│   ├── __init__.py       # Connector factory
│   ├── base.py           # Abstract base class
│   └── shopify_connector.py  # Shopify implementation
│
├── requirements.txt       # Dependencies
├── .env.example          # Configuration template
└── README.md             # Documentation
```

## How It Works

### Simple 4-Step Process (Loops Forever):

1. **Poll Source** - Fetch new orders from THE source Shopify store
2. **Route Orders** - Send to appropriate destination store (based on routing rules)
3. **Poll Tracking** - Check destinations for fulfillment/tracking
4. **Sync Back** - Update source store with tracking info

### Database Schema

**stores** - Store configurations (1 source, N destinations)
**orders** - Orders being synced
**order_lines** - Line items in orders
**order_routing** - Rules for routing orders to destinations

### Modular Design

- **Easy to add new store types**: Just implement `StoreConnector` interface
- **Flexible routing**: Match by SKU pattern, product ID, or add custom logic
- **Simple architecture**: No frameworks, no complexity
- **Direct API calls**: Uses `requests` library for full control over API interactions
- **No SDK lock-in**: Platform-agnostic design makes it easy to add WooCommerce, BigCommerce, etc.

## Usage

```bash
# 1. Setup environment
cp .env.example .env
# Edit .env with DATABASE_URL

# 2. Initialize database
python setup.py

# 3. Add stores (credentials stored in database)
python manage_stores.py

# 4. Run
python main.py
```

That's it!
