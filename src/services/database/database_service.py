import pymongo
import logging
from typing import Dict, List, Optional, Any
import uuid

from src.env import DATABASE_NAME, URI
from src.services.database.interface import DatabaseInterface

logger = logging.getLogger(__name__)

class MongoDBService(DatabaseInterface):
    """Service for interacting with MongoDB database."""
    
    def __init__(self, database_name: str = DATABASE_NAME):
        """Initialize the MongoDB service with credentials from settings."""
        self.client = pymongo.MongoClient(URI)
        self.db = self.client[database_name]

    def get_item(self, collection: str, item_id: str) -> Optional[Dict[str, Any]]:
        """
        Get an item by ID from the specified collection.
        
        Args:
            collection: The collection to search in.
            item_id: The ID of the item.
            
        Returns:
            The item document, or None if not found.
        """
        return self.db[collection].find_one({"_id": item_id})
    
    def get_items(self, collection: str, query: Dict[str, Any] = {}, limit: int = 0) -> List[Dict[str, Any]]:
        """
        Get all items from the specified collection that match the query.
        
        Args:
            collection: The collection to search in.
            query: The query to filter items by.
            limit: Maximum number of results to return.
            
        Returns:
            A list of item documents that match the query.
        """
        return list(self.db[collection].find(query).limit(limit)) if limit > 0 else list(self.db[collection].find(query))
    
    def get_random_item(self, collection: str) -> Optional[Dict[str, Any]]:
        """
        Get a random item from the specified collection.
        
        Args:
            collection: The collection to search in.
            
        Returns:
            A random item document, or None if no items are found.
        """
        try:
            items = list(self.db[collection].aggregate([
                {"$sample": {"size": 1}}
            ]))
            return items[0] if items else None
        except Exception as e:
            logger.error(f"Error getting random item from {collection}: {e}")
            return None

    def get_random_item_by_field(self, field: str, value: Any, collection: str) -> Optional[Dict[str, Any]]:
        """
        Get a random item from the specified collection that matches a field value.
        
        Args:
            field: The field to filter by.
            value: The value to match.
            collection: The collection to search in.
            
        Returns:
            A random item document that matches the field value, or None if no items are found.
        """
        items = list(self.db[collection].aggregate([
            {"$match": {field: value}},
            {"$sample": {"size": 1}}
        ]))
        return items[0] if items else None
    
    def insert_item(self, collection: str, item: Dict[str, Any]) -> str:
        """
        Insert an item into the specified collection.
        
        Args:
            collection: The collection to insert into.
            item: The item document to insert.
            
        Returns:
            The ID of the inserted item.
        """
        if "_id" not in item or not item["_id"]:
            item["_id"] = str(uuid.uuid4())
        
        result = self.db[collection].insert_one(item)
        return str(result.inserted_id)
    
    def insert_items(self, collection: str, items: List[Dict[str, Any]]) -> List[str]:
        """
        Insert multiple items into the specified collection.
        
        Args:
            collection: The collection to insert into.
            items: A list of item documents to insert.
            
        Returns:
            A list of IDs of the inserted items.
        """
        if not items:
            return []
        
        for item in items:
            if "_id" not in item or not item["_id"]:
                item["_id"] = str(uuid.uuid4())
        
        result = self.db[collection].insert_many(items)
        return [str(id) for id in result.inserted_ids]
    
    def update_item(self, collection: str, item_id: str, update_data: Dict[str, Any]) -> bool:
        """
        Update an item in the specified collection.
        
        Args:
            collection: The collection to update in.
            item_id: The ID of the item to update.
            update_data: The data to update the item with.
            
        Returns:
            True if the update was successful, False otherwise.
        """
        result = self.db[collection].update_one({"_id": item_id}, {"$set": update_data})
        return result.modified_count > 0
    
    def delete_item(self, collection: str, item_id: str) -> bool:
        """
        Delete an item from the specified collection.
        
        Args:
            collection: The collection to delete from.
            item_id: The ID of the item to delete.
            
        Returns:
            True if the deletion was successful, False otherwise.
        """
        result = self.db[collection].delete_one({"_id": item_id})
        return result.deleted_count > 0