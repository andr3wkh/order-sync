# Order Sync System

Simple, modular order synchronization system:
- 1 source store → Multiple destination stores
- Polls orders, stores in database, routes to destinations
- Tracks fulfillment and syncs back to source

## Quick Start

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Configure database:**
```bash
cp .env.example .env
# Edit .env with your DATABASE_URL
```

3. **Initialize database:**
```bash
python setup.py
```

4. **Add stores:**
```bash
python manage_stores.py
```
Follow the prompts to add your source store and destination stores.

5. **Run:**
```bash
python main.py
```

## How It Works

**4 Simple Steps (repeating loop):**

1. **Poll Source Store** - Fetch new orders from Shopify source
2. **Store Orders** - Save to database (orders + order_lines tables)
3. **Route to Destinations** - Send orders based on routing rules
4. **Sync Tracking** - Poll destinations for tracking, update source

## Managing Stores

All store credentials are stored securely in the PostgreSQL database:

**Add/Edit/Delete stores:**
```bash
python manage_stores.py
```

The interactive menu lets you:
- List all configured stores
- Add new source or destination stores
- Delete stores
- Manage routing rules

**Store credentials include:**
- Store name and type (Shopify, WooCommerce, etc.)
- Role (source or destination)
- Shop URL
- API credentials (key and secret)
- API version

## Routing Rules

Routes orders to destinations based on:
- SKU patterns (`PROD-A%`)
- Product IDs
- Priority (higher = checked first)

Configure in `order_routing` table.

## Modular Design

- **connectors/** - Store integrations (Shopify, easily add WooCommerce, etc.)
- **models/** - Database models
- **services/** - Business logic
- Easy to extend with new store types
