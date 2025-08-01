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
def domande_simulazione_quiz(entity: str, capitolo: int = None) -> str:
    """Restituisce domande e risposte da utilizzare per fare simulazioni del quiz di teoria"""
    logger.info(f"Database lookup for entity: {entity} in capitolo: {capitolo}")
   
    try:
        # Mock database with predefined entities
        db = QuizMongoDBService()
        # Get data based on categoria if none get all questions
        if capitolo:
            question = db.get_random_question_by_field("capitolo", capitolo)
        else:
            question = db.get_random_question()

        question_text = question['domanda']['testo']
        logger.info(f"Selected question: {question['_id']} {question_text}")
        answers_dict = {item['id']: item['testo'] for item in question['domanda']['opzioni']}
        answers_str = "\n".join([f"{k}) {v}" for k, v in answers_dict.items()])
    
        return f"Domanda: {question_text}\nRisposte possibili:\n{answers_str}"
    except Exception as e:
        logger.error(f"Error during database lookup: {e}")

# Dictionary of available tools
AVAILABLE_TOOLS = {
    "get_domande_quiz": domande_simulazione_quiz,
    "database_lookup": database_lookup
}
