from typing import Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import InMemorySaver

from ..env import FORCED_MODEL, HISTORY_LIMIT
from ..tools import domanda_teoria
from ..history_hooks import build_llm_input_window_hook
from ..prompt_personalization import get_personalized_prompt_for_user, generate_thread_id
import logging
logger = logging.getLogger("uvicorn")


class AgentManager:
    """
    Factory per la creazione di agenti LangGraph configurati per-request.
    Gestisce la creazione di LLM, tools e configurazione agente.
    """
    
    @staticmethod
    def create_agent(
        user_id: str,
        token: Optional[str] = None,
        user_data: bool = False,
        checkpointer: Optional[InMemorySaver] = None
    ):
        """
        Crea un agente LangGraph configurato per l'utente specifico.
        
        Args:
            user_id: ID dell'utente per personalizzazione prompt
            token: Token Auth0 per recupero metadata utente  
            user_data: Se recuperare i metadata utente
            checkpointer: Checkpointer per memoria conversazione
            
        Returns:
            Tupla (agent_executor, config, prompt_version)
        """
        # Configurazione LLM
        model = FORCED_MODEL
        logger.info(f"Selected LLM model: {model}")
        
        llm = ChatGoogleGenerativeAI(
            model=model,
            temperature=0.7,
        )
        
        # Tools disponibili
        tools = [domanda_teoria]
        
        # Prompt personalizzato per utente
        personalized_prompt, prompt_version, _ = get_personalized_prompt_for_user(
            user_id=user_id, 
            token=token, 
            fetch_user_data=user_data
        )
        
        # Creazione agente
        agent_executor = create_react_agent(
            llm,
            tools,
            prompt=personalized_prompt,
            pre_model_hook=build_llm_input_window_hook(HISTORY_LIMIT),
            checkpointer=checkpointer,
        )
        
        # Configurazione thread
        config = {
            "configurable": {
                "thread_id": generate_thread_id(user_id, prompt_version), 
                "recursion_limit": 2
            }
        }
        
        return agent_executor, config, prompt_version