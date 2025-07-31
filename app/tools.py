from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
import requests
import json
import logging
import random as rd
from langchain_core.tools import tool
from app.config import settings
from app.services.database.database_quiz_service import QuizMongoDBService

logger = logging.getLogger("uvicorn")

# Search Tool
# Database Lookup Tool
@tool
def database_lookup(entity: str) -> str:
    """Look up information in the database."""
    logger.info(f"Database lookup for entity: {entity}")
    # This is a mock database lookup tool
    if not entity:
        return "Error: No entity specified for lookup."
    
    # Mock database with predefined entities
    mock_db = {
        "weather_api": "API for accessing weather data. Endpoint: /api/weather?location={location}",
        "user_profile": "User profile schema includes: id, name, email, created_at",
        "products": "Product catalog with categories: electronics, clothing, home goods",
        "pricing": "Pricing tiers: Basic ($10/mo), Pro ($25/mo), Enterprise ($100/mo)"
    }
    
    if entity.lower() in mock_db:
        return f"Database lookup result for '{entity}':\n{mock_db[entity.lower()]}"
    else:
        return f"No information found in database for '{entity}'."

# Database Lookup Tool
@tool
def domande_simulazione_quiz(entity: str, categoria: str = None) -> str:
    """Restituisce domande e risposte da utilizzare per fare simulazioni del quiz di teoria"""
    logger.info(f"Database lookup for entity: {entity} in categoria: {categoria}")
   
    try:
        # Mock database with predefined entities
        db = QuizMongoDBService()
        # Get data based on categoria if none get all questions
        if categoria:
            question = db.get_random_question_by_field("categoria", categoria)
        else:
            question = db.get_random_question()

        logger.info(f"Selected question: {question['_id']} {question['content']}")
        answers_dict = question["possible_answers"]
        answers_str = "\n".join([f"{k}) {v}" for k, v in answers_dict.items()])
    
        return f"Domanda: {question['content']}\nRisposte possibili:\n{answers_str}"
    except Exception as e:
        logger.error(f"Error during database lookup: {e}")

# Dictionary of available tools
AVAILABLE_TOOLS = {
    "domande_simulazione_quiz": domande_simulazione_quiz,
    "database_lookup": database_lookup
}

if __name__ == "__main__":
    quiz_entity = "domanda"
    categoria = "generale"
    print(domande_simulazione_quiz(quiz_entity, categoria))