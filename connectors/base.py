"""
Base connector interface - easy to add new store types
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from datetime import datetime


class StoreConnector(ABC):
    """Base class for all store connectors"""
    
    def __init__(self, config: Dict):
        self.config = config
    
    @abstractmethod
    def fetch_orders(self, since: datetime) -> List[Dict]:
        """Fetch orders from store since datetime"""
        pass
    
    @abstractmethod
    def create_order(self, order_data: Dict) -> Dict:
        """Create order in store, return created order with ID"""
        pass
    
    @abstractmethod
    def get_order(self, order_id: str) -> Optional[Dict]:
        """Get specific order by ID"""
        pass
    
    @abstractmethod
    def update_tracking(self, order_id: str, tracking: Dict) -> bool:
        """Update order with tracking info"""
        pass
    
    @abstractmethod
    def tag_order(self, order_id: str, tag: str) -> bool:
        """Add a tag to an order"""
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: str, reason: str = 'other') -> bool:
        """Cancel an order"""
        pass
