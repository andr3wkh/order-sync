"""
Connector factory - easily add new store types here
"""
from .shopify_connector import ShopifyConnector

# Registry of available connectors
CONNECTORS = {
    'shopify': ShopifyConnector,
    # Add more here:
    # 'woocommerce': WooCommerceConnector,
    # 'bigcommerce': BigCommerceConnector,
}


def get_connector(store_type: str, config: dict):
    """Get connector instance for store type"""
    connector_class = CONNECTORS.get(store_type.lower())
    
    if not connector_class:
        raise ValueError(f"Unsupported store type: {store_type}")
    
    return connector_class(config)
