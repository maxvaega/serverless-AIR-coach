from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union
import uuid
from datetime import datetime

class DatabaseInterface(ABC):
    """Abstract interface for database operations."""

    @abstractmethod
    def get_item(self, collection: str, item_id: str) -> Optional[Dict[str, Any]]:
        """Get an item by ID from the specified collection."""
        pass

    @abstractmethod
    def get_items(self, collection: str, query: Dict[str, Any] = {}) -> List[Dict[str, Any]]:
        """Get all items from the specified collection that match the query."""
        pass

    @abstractmethod
    def get_random_item(self, collection: str) -> Optional[Dict[str, Any]]:
        """Get a random item from the specified collection."""
        pass

    @abstractmethod
    def insert_items(self, collection: str, items: List[Dict[str, Any]]) -> List[str]:
        """Insert multiple items into the specified collection."""
        pass