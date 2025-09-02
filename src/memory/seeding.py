import json
from typing import List, Dict, Any
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from ..env import DATABASE_NAME, COLLECTION_NAME, HISTORY_LIMIT
from ..database import get_data
from ..logging_config import logger


class MemorySeeder:
    """
    Gestisce il seeding della memoria dell'agente con la cronologia da MongoDB.
    """
    
    @staticmethod
    def seed_agent_memory(
        agent_executor, 
        config: Dict[str, Any], 
        user_id: str, 
        chat_history: bool = True
    ) -> bool:
        """
        Effettua il seeding della memoria dell'agente con i dati da MongoDB.
        
        Args:
            agent_executor: L'agente da cui recuperare/aggiornare lo stato
            config: Configurazione dell'agente (thread_id, etc.)
            user_id: ID utente per filtrare la cronologia
            chat_history: Se abilitare il seeding da DB
            
        Returns:
            True se il seeding è avvenuto con successo, False altrimenti
        """
        if not chat_history:
            return False
            
        # Verifica se esiste già memoria volatile
        existing_messages = MemorySeeder._get_existing_messages(agent_executor, config)
        if existing_messages:
            msg_count = len(existing_messages)
            logger.info(f"HISTORY - Recupero lo stato dell'agente. Numero di messaggi in memoria: {msg_count}")
            return False  # Memoria già presente (warm path)
        
        # Cold start: seed da DB
        logger.info("HISTORY - Nessun messaggio trovato in memoria volatile")
        seed_messages = MemorySeeder._build_seed_messages(user_id)
        
        if seed_messages:
            return MemorySeeder._apply_seeding(agent_executor, config, seed_messages)
            
        return False
    
    @staticmethod
    def _get_existing_messages(agent_executor, config: Dict[str, Any]) -> List:
        """Recupera i messaggi esistenti dallo stato dell'agente."""
        try:
            state = agent_executor.get_state(config)
            return state.values.get("messages") if state and hasattr(state, "values") else None
        except Exception as e:
            logger.error(f"Errore nel recuperare lo stato dell'agente: {e}")
            return None
    
    @staticmethod 
    def _build_seed_messages(user_id: str) -> List:
        """Costruisce i messaggi di seeding dalla cronologia MongoDB."""
        seed_messages = []
        
        logger.info("HISTORY - Cerco cronologia conversazione su DB...")
        try:
            history = get_data(
                DATABASE_NAME,
                COLLECTION_NAME,
                filters={"userId": user_id},
                limit=HISTORY_LIMIT,
            )
            
            for msg in history:
                # Aggiungi messaggio umano
                if msg.get("human"):
                    seed_messages.append(HumanMessage(msg["human"]))
                
                # Aggiungi messaggio sistema (AI)
                if msg.get("system"):
                    seed_messages.append(AIMessage(msg["system"]))
                
                # Gestisci tool messages
                tool_entry = msg.get("tool")
                if tool_entry:
                    tool_message = MemorySeeder._create_tool_message(tool_entry, msg)
                    if tool_message:
                        seed_messages.append(tool_message)
            
            if history:
                logger.info(f"HISTORY - Cronologia recuperata da DB: {len(history)} messaggi")
                
        except Exception as e:
            logger.error(f"Errore nel recuperare la chat history: {e}")
            
        return seed_messages
    
    @staticmethod
    def _create_tool_message(tool_entry, msg: Dict) -> ToolMessage:
        """Crea un ToolMessage dalla voce tool nel DB."""
        try:
            # Supporta sia schema vecchio (name/result) sia nuovo (tool_name/data) e anche lista di record
            entry = None
            if isinstance(tool_entry, list) and tool_entry:
                entry = tool_entry[-1]
            elif isinstance(tool_entry, dict):
                entry = tool_entry

            if isinstance(entry, dict):
                tool_name = entry.get("name") or entry.get("tool_name") or "unknown_tool"
                tool_result = entry.get("result") or entry.get("data")
            else:
                tool_name = "unknown_tool"
                tool_result = tool_entry

            if tool_result is None:
                logger.debug("HISTORY DEBUG - tool_result assente, salto creazione ToolMessage")
                return None
            
            content_str = tool_result if isinstance(tool_result, str) else json.dumps(tool_result)
            tool_message = ToolMessage(
                content=content_str,
                tool_call_id=f"call_{tool_name}_{msg.get('timestamp', 'unknown')}"
            )
            
            logger.info(
                f"HISTORY DEBUG - ToolMessage aggiunto al seeding: tool={tool_name}, content_len={len(content_str)}"
            )
            return tool_message
            
        except Exception as te:
            logger.error(f"Errore nella creazione del ToolMessage per il seeding: {te}")
            return None
    
    @staticmethod
    def _apply_seeding(agent_executor, config: Dict[str, Any], seed_messages: List) -> bool:
        """Applica i messaggi di seeding allo stato dell'agente."""
        try:
            agent_executor.update_state(config, {"messages": seed_messages})
            logger.info(f"HISTORY - Seeding completato con {len(seed_messages)} messaggi")
            return True
        except Exception as e:
            logger.error(f"Error seeding agent state: {e}")
            return False