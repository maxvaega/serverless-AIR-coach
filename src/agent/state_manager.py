from typing import Optional
from langgraph.checkpoint.memory import InMemorySaver

import logging
logger = logging.getLogger("uvicorn")


class AgentStateManager:
    """
    Gestisce il checkpointer condiviso e lo stato degli agenti.
    Utilizza pattern singleton per garantire un checkpointer per processo.
    """
    
    _instance: Optional['AgentStateManager'] = None
    _checkpointer: Optional[InMemorySaver] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AgentStateManager, cls).__new__(cls)
        return cls._instance
    
    def get_checkpointer(self) -> InMemorySaver:
        """
        Ritorna un checkpointer condiviso a livello di processo (thread-safe best-effort).
        InMemorySaver non dipende dall'event loop, quindi è sicuro riutilizzarlo tra richieste
        per mantenere la memoria volatile dei thread (per `thread_id`).
        """
        if self._checkpointer is None:
            self._checkpointer = InMemorySaver()
            logger.debug("AgentStateManager: nuovo checkpointer creato")
        return self._checkpointer
    
    def clear_checkpointer(self):
        """Resetta il checkpointer (utile per test)."""
        self._checkpointer = None
        logger.debug("AgentStateManager: checkpointer resettato")


# Instance globale per compatibilità con codice esistente
def _get_checkpointer() -> InMemorySaver:
    """Funzione di compatibilità per il codice esistente."""
    return AgentStateManager().get_checkpointer()