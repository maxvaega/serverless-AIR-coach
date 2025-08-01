from typing import Dict, Any, List, Union
from pydantic import BaseModel, Field
import requests
import json
import logging
import re
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

def domande_simulazione_quiz(entity: str, capitolo: Union[str, int] = None) -> str:
    """
    Restituisce una domanda casuale dal quiz, filtrata per capitolo (numero o nome).
    
    Args:
        entity: Ignored in this implementation (kept for tool compatibility).
        capitolo: Numero (int) o nome (str) del capitolo.

    Returns:
        Una stringa con la domanda e le risposte, o un messaggio di errore.
    """
    logger.info(f"Database lookup for entity: {entity} in capitolo: {capitolo}")
    
    try:
        db = QuizMongoDBService()
        question = None

        if capitolo is not None:
            print(f"Looking for questions in chapter: {capitolo}")
            # Try chapter number first (int)
            if isinstance(capitolo, int) or (isinstance(capitolo, str) and capitolo.isdigit()):
                capitolo_num = int(capitolo)
                question = db.get_random_question_by_field("capitolo.numero", capitolo_num)
                 
            else:
                # Try chapter name (str)
                
                if isinstance(capitolo, str) and re.sub(r"\D", "", capitolo):
                    capitolo_num = int(re.sub(r"\D", "", capitolo))
                    question = db.get_random_question_by_field("capitolo.numero", capitolo_num)
                else:
                    question = db.get_random_question_by_field("capitolo.nome", capitolo)
            
            if not question:
                # Fallback: list all available chapter names
                all_questions = db.get_all_questions()
                list_of_capitoli = {
                    (q.get("capitolo", {}).get("numero"), q.get("capitolo", {}).get("nome"))
                    for q in all_questions
                    if q.get("capitolo", {}).get("numero") is not None and q.get("capitolo", {}).get("nome") is not None
                }
                capitoli_str = "\n".join([f"{numero} - {nome}" for numero, nome in sorted(list_of_capitoli)])

                return f"Nessuna domanda trovata per '{capitolo}'. Capitoli disponibili:\n{capitoli_str}"
        
        else:
            # No filter: return a random question
            question = db.get_random_question()

        # Format output
        question_text = question['domanda']['testo']
        logger.info(f"Selected question: {question['_id']} {question_text}")
        answers_dict = {item['id']: item['testo'] for item in question['domanda']['opzioni']}
        answers_str = "\n".join([f"{k}) {v}" for k, v in answers_dict.items()])
    
        return f"Domanda: {question_text}\nRisposte possibili:\n{answers_str}"

    except Exception as e:
        logger.error(f"Error during database lookup: {e}")
        return "Errore durante il recupero della domanda dal database."


# Dictionary of available tools
AVAILABLE_TOOLS = {
    "get_domande_quiz": domande_simulazione_quiz,
    "database_lookup": database_lookup
}
