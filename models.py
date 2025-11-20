from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Numeric, Text, JSON, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime
import config

Base = declarative_base()


class Store(Base):
    """Store configuration (1 source, multiple destinations)"""
    __tablename__ = 'stores'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    store_type = Column(String(50), nullable=False)
    role = Column(String(20), nullable=False)
    shop_url = Column(String(255), nullable=False, unique=True)
    access_token = Column(String(255))
    api_key = Column(String(255))
    api_secret = Column(String(255))    
    api_version = Column(String(50), default='2024-01')
    created_at = Column(DateTime, default=datetime.utcnow)


class Order(Base):
    """Orders synced between stores"""
    __tablename__ = 'orders'
    
    id = Column(Integer, primary_key=True)
    source_store_id = Column(Integer, ForeignKey('stores.id'), nullable=False)
    destination_store_id = Column(Integer, ForeignKey('stores.id'))
    
    # External IDs
    source_order_id = Column(String(255), nullable=False)
    destination_order_id = Column(String(255))
    
    # Order info
    order_number = Column(String(255))
    customer_email = Column(String(255))
    customer_name = Column(String(255))
    customer_phone = Column(String(50))
    total_price = Column(Numeric(10, 2))
    currency = Column(String(3))
    
    # Customer addresses (JSON to store full address objects)
    shipping_address = Column(JSON)
    billing_address = Column(JSON)
    
    # Full order data from source (for reference)
    order_json = Column(JSON)
    
    # Status: 'pending' -> 'synced' -> 'tracking_updated'
    status = Column(String(50), default='pending')
    
    # Tracking
    tracking_number = Column(String(255))
    tracking_company = Column(String(255))
    tracking_url = Column(String(512))
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    synced_at = Column(DateTime)
    tracking_synced_at = Column(DateTime)
    
    # Relationships
    source_store = relationship("Store", foreign_keys=[source_store_id])
    destination_store = relationship("Store", foreign_keys=[destination_store_id])
    order_lines = relationship("OrderLine", back_populates="order", cascade="all, delete-orphan")


class OrderLine(Base):
    """Order line items"""
    __tablename__ = 'order_lines'
    
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey('orders.id'), nullable=False)
    
    # Product details
    sku = Column(String(255))
    ean = Column(String(255))  # EAN/barcode
    product_id = Column(String(255))
    title = Column(String(512))
    quantity = Column(Integer, nullable=False)
    price = Column(Numeric(10, 2))
    tags = Column(Text)  # Order line tags (comma-separated)
    
    # Relationships
    order = relationship("Order", back_populates="order_lines")


class OrderRouting(Base):
    """Routing configuration: which destination gets which orders"""
    __tablename__ = 'order_routing'
    
    id = Column(Integer, primary_key=True)
    source_store_id = Column(Integer, ForeignKey('stores.id'), nullable=False)
    destination_store_id = Column(Integer, ForeignKey('stores.id'), nullable=False)
    
    # How to determine which orders go to this destination
    routing_method = Column(String(50), nullable=False, default='all')  # 'all', 'order_tags', etc.
    
    # Value to match (depends on routing_method)
    # If routing_method = 'order_tags', this is the tag name to match (e.g., 'Zinaps')
    routing_method_value = Column(String(255))
    
    # Product lookup method in destination store: 'sku' or 'ean'
    # This tells the system whether to match products by SKU or EAN/barcode
    lookup_method = Column(String(50), nullable=False, default='sku')
    
    priority = Column(Integer, default=0)  # Higher = checked first
    is_active = Column(Integer, default=1)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    source_store = relationship("Store", foreign_keys=[source_store_id])
    destination_store = relationship("Store", foreign_keys=[destination_store_id])


# Database setup
engine = create_engine(config.DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)


def init_db():
    """Create all tables"""
    Base.metadata.create_all(engine)


def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        return db
    finally:
        pass
