import datetime
from typing import List, Dict, Optional, Any

from ..env import DATABASE_NAME, COLLECTION_NAME
from ..database import insert_data
import logging
logger = logging.getLogger("uvicorn")


class ConversationPersistence:
    """
    Gestisce la persistenza delle conversazioni su MongoDB.
    """
    
    @staticmethod
    def save_conversation(
        query: str,
        response: str,
        user_id: str, 
        tool_records: Optional[List[Dict]] = None
    ) -> bool:
        """
        Salva una conversazione (query + response) su MongoDB.
        
        Args:
            query: La query dell'utente
            response: La risposta dell'agente
            user_id: ID dell'utente
            tool_records: Lista dei tool eseguiti durante la conversazione
            
        Returns:
            True se il salvataggio è avvenuto con successo, False altrimenti
        """
        if not response and not tool_records:
            logger.warning("DB - Nessuna risposta o tool da salvare, skip persistenza")
            return False
            
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        data = {
            "human": query,
            "system": response,
            "userId": user_id,
            "timestamp": timestamp,
        }
        
        # Aggiungi tool record se presente (solo l'ultimo)
        if tool_records:
            data["tool"] = tool_records[-1]
        
        try:
            insert_data(DATABASE_NAME, COLLECTION_NAME, data)
            logger.info(f"DB - Risposta inserita nella collection: {DATABASE_NAME} - {COLLECTION_NAME}")
            return True
            
        except Exception as e:
            logger.error(f"DB - Errore nell'inserire i dati nella collection: {e}")
            return False
    
    @staticmethod
    def log_run_completion(
        response: str, 
        tool_records: List[Dict], 
        serialized_output: Any = None
    ):
        """
        Logga il completamento di una run con dettagli su risposta e tool.
        
        Args:
            response: La risposta finale dell'agente
            tool_records: Lista dei tool eseguiti
            serialized_output: Output serializzato dell'ultimo tool
        """
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        logger.info(
            f"RUN TERMINATA alle {timestamp}: "
            f"response_len={len(response)} tool_records={len(tool_records)}"
        )
        logger.info(f"RUN - Risposta LLM:\n{response}")
        
        if serialized_output is not None:
            logger.info(f"RUN - Risposta Tool:\n{serialized_output}")