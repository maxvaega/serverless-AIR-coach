import pymongo
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
import uuid
from app.services.database.database_service import MongoDBService

from app.config import settings

logger = logging.getLogger(__name__)

class QuizMongoDBService():
    """Service for interacting with MongoDB database."""
    
    def __init__(self, database_name: str = "quiz"):
        """Initialize the MongoDB service with credentials from settings."""
        self.db = MongoDBService(database_name)
    
    # Quiz operations
    def get_quiz_question(self, question_id: str, collection: str = "dev") -> Optional[Dict[str, Any]]:
        """
        Get a quiz question by ID.
        
        Args:
            question_id: The ID of the question.
            
        Returns:
            The question document, or None if not found.
        """
        return self.db.get_item(collection, question_id)
    
    def get_random_question(self, collection: str = "dev") -> Optional[Dict[str, Any]]:
        """
        Get a random quiz question from the database.
        
        Args:
            collection: The collection to search in.
            
        Returns:
            A random question document, or None if no questions are found.
        """
        return self.db.get_random_item(collection)
    
    def get_random_question_by_field(self, field: str, value: str, collection: str = "dev") -> Optional[Dict[str, Any]]:
        """
        Get a random quiz question from a specific chapter.
        
        Args:
            capitolo: The chapter to filter questions by.
            collection: The collection to search in.
            
        Returns:
            A random question document from the specified chapter, or None if no questions are found.
        """
        return self.db.get_random_item_by_field(field, value, collection)

    def get_category_questions(self, category: str, collection: str = "dev") -> List[Dict[str, Any]]:
        """
        Get all questions for a specific category.
        
        Args:
            category: The category to filter questions by.
            
        Returns:
            A list of question documents in the specified category.
        """
        return self.db.get_items(collection, {"categoria": category})
    
    def get_capitolo_questions(self, capitolo: str, collection: str = "dev") -> List[Dict[str, Any]]:
        """
        Get all questions for a specific chapter (capitolo).
        
        Args:
            capitolo: The chapter to filter questions by.
            
        Returns:
            A list of question documents in the specified chapter.
        """
        return self.db.get_items(collection, {"capitolo": capitolo})
    
    def get_capitolo_category_questions(self, capitolo: str, category: str, collection: str = "dev") -> List[Dict[str, Any]]:
        """
        Get all questions for a specific chapter and category.
        
        Args:
            capitolo: The chapter to filter questions by.
            category: The category to filter questions by.
            
        Returns:
            A list of question documents in the specified chapter and category.
        """
        return self.db.get_items(collection, {"capitolo": capitolo, "categoria": category})
    
    def get_all_questions(self, collection: str = "dev") -> List[Dict[str, Any]]:
        """
        Get all quiz questions.
        
        Returns:
            A list of all question documents.
        """
        return self.db.get_items(collection)
    
    def insert_quiz_questions(self, questions: List[Dict[str, Any]], collection: str = "dev") -> List[str]:
        """
        Insert multiple quiz questions into the database.
        
        Args:
            questions: A list of question documents to insert.
            
        Returns:
            A list of inserted question IDs.
        """
        return self.db.insert_items(collection, questions)
    
    def update_quiz_question(self, question_id: str, question_data: Dict[str, Any], collection: str = "dev") -> bool:
        """
        Update a quiz question by ID.
        
        Args:
            question_id: The ID of the question to update.
            question_data: The updated question data.
            
        Returns:
            True if the update was successful, False otherwise.
        """
        return self.db.update_item(collection, question_id, question_data)