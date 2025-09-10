# import pymongo
import logging
from typing import Dict, List, Optional, Any
from src.services.database.database_service import MongoDBService
from src.services.database.interface import DatabaseInterface

# from env import *

logger = logging.getLogger(__name__)

class QuizMongoDBService(DatabaseInterface):
    """Service for interacting with MongoDB database for quiz operations."""
    
    def __init__(self, database_name: str = "quiz", collection_name: str = "prod"):
        """Initialize the MongoDB service with credentials from settings."""
        self.db = MongoDBService(database_name)
        self.collection_name = collection_name
    
    # Implementation of abstract methods from DatabaseInterface
    def get_item(self, collection: str, item_id: str) -> Optional[Dict[str, Any]]:
        """
        Get an item by ID from the specified collection.
        
        Args:
            collection: The collection to search in.
            item_id: The ID of the item.
            
        Returns:
            The item document, or None if not found.
        """
        return self.db.get_item(collection, item_id)
    
    def get_items(self, collection: str, query: Dict[str, Any] = {}) -> List[Dict[str, Any]]:
        """
        Get all items from the specified collection that match the query.
        
        Args:
            collection: The collection to search in.
            query: The query to filter items by.
            
        Returns:
            A list of item documents that match the query.
        """
        return self.db.get_items(collection, query)
    
    def get_random_item(self, collection: str) -> Optional[Dict[str, Any]]:
        """
        Get a random item from the specified collection.
        
        Args:
            collection: The collection to search in.
            
        Returns:
            A random item document, or None if no items are found.
        """
        return self.db.get_random_item(collection)
    
    def insert_items(self, collection: str, items: List[Dict[str, Any]]) -> List[str]:
        """
        Insert multiple items into the specified collection.
        
        Args:
            collection: The collection to insert into.
            items: A list of item documents to insert.
            
        Returns:
            A list of IDs of the inserted items.
        """
        return self.db.insert_items(collection, items)
    
    # Quiz operations
    def get_quiz_question(self, question_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a quiz question by ID.
        
        Args:
            question_id: The ID of the question.
            
        Returns:
            The question document, or None if not found.
        """
        return self.db.get_item(self.collection_name, question_id)
    
    def get_random_question(self) -> Optional[Dict[str, Any]]:
        """
        Get a random quiz question from the database.
        
        Returns:
            A random question document, or None if no questions are found.
        """
        return self.db.get_random_item(self.collection_name)
    
    def get_random_question_by_field(self, field: str, value: str) -> Optional[Dict[str, Any]]:
        """
        Get a random quiz question from a specific field value.
        
        Args:
            field: The field to filter questions by.
            value: The value to match.
            
        Returns:
            A random question document that matches the field value, or None if no questions are found.
        """
        return self.db.get_random_item_by_field(field, value, self.collection_name)

    def get_category_questions(self, category: str) -> List[Dict[str, Any]]:
        """
        Get all questions for a specific category.
        
        Args:
            category: The category to filter questions by.
            
        Returns:
            A list of question documents in the specified category.
        """
        return self.db.get_items(self.collection_name, {"categoria": category})
    
    def get_capitolo_questions(self, capitolo: int) -> List[Dict[str, Any]]:
        """
        Get all questions for a specific chapter (capitolo).
        
        Args:
            capitolo: The chapter to filter questions by.
            
        Returns:
            A list of question documents in the specified chapter.
        """
        return self.db.get_items(self.collection_name, {"capitolo.numero": capitolo})
    
    def get_capitolo_category_questions(self, capitolo: str, category: str) -> List[Dict[str, Any]]:
        """
        Get all questions for a specific chapter and category.
        
        Args:
            capitolo: The chapter to filter questions by.
            category: The category to filter questions by.
            
        Returns:
            A list of question documents in the specified chapter and category.
        """
        return self.db.get_items(self.collection_name, {"capitolo": capitolo, "categoria": category})
    
    def get_question_by_capitolo_and_number(self, capitolo: int, numero: int) -> Optional[Dict[str, Any]]:
        """
        Get a specific question by chapter and question number.
        
        Args:
            capitolo: The chapter number.
            numero: The question number.
            
        Returns:
            The question document, or None if not found.
        """
        questions = self.db.get_items(self.collection_name, {"capitolo": capitolo, "numero": numero})
        return questions[0] if questions else None
    
    def search_questions_by_text(self, testo: str) -> List[Dict[str, Any]]:
        """
        Search questions by text using regex pattern matching.
        
        Args:
            testo: The text to search for in question text.
            
        Returns:
            A list of questions that match the text pattern.
        """
        # Converti il testo in minuscolo per una ricerca case-insensitive
        testo_lower = testo.lower().strip()
        
        # Dividi il testo in parole e filtra quelle troppo corte
        parole_chiave = [parola.strip() for parola in testo_lower.split() if len(parola.strip()) > 2]
        
        if not parole_chiave:
            return []
        
        # Crea una query che cerca domande che contengono tutte le parole chiave
        # Usa $regex per ricerca case-insensitive
        query = {
            "$and": [
                {"testo": {"$regex": parola, "$options": "i"}} 
                for parola in parole_chiave
            ]
        }
        
        return self.db.get_items(self.collection_name, query)
    
    def get_all_questions(self) -> List[Dict[str, Any]]:
        """
        Get all quiz questions.
        
        Returns:
            A list of all question documents.
        """
        return self.db.get_items(self.collection_name)
    
    def insert_quiz_questions(self, questions: List[Dict[str, Any]]) -> List[str]:
        """
        Insert multiple quiz questions into the database.
        
        Args:
            questions: A list of question documents to insert.
            
        Returns:
            A list of inserted question IDs.
        """
        return self.db.insert_items(self.collection_name, questions)
    
    def update_quiz_question(self, question_id: str, question_data: Dict[str, Any]) -> bool:
        """
        Update a quiz question by ID.
        
        Args:
            question_id: The ID of the question to update.
            question_data: The updated question data.
            
        Returns:
            True if the update was successful, False otherwise.
        """
        return self.db.update_item(self.collection_name, question_id, question_data)