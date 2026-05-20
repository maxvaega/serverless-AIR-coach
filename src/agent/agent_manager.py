from typing import Optional
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import InMemorySaver
from ..env import (
    FORCED_MODEL,
    HISTORY_LIMIT,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    CACHE_DEBUG_LOGGING,
)
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
        model = FORCED_MODEL
        logger.info(f"Selected LLM model: {model}")

        # DeepSeek via OpenRouter. Headers stabili + nessun pin di provider:
        # OpenRouter applica sticky routing entro la sessione mantenendo caldo
        # il cache prefix-match di DeepSeek (automatico lato provider).
        llm = ChatOpenAI(
            model=model,
            api_key=OPENROUTER_API_KEY,
            base_url=OPENROUTER_BASE_URL,
            temperature=0.7,
            default_headers={
                "HTTP-Referer": "https://github.com/maxvaega/serverless-AIR-coach",
                "X-Title": "AIR Coach",
            },
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
            llm, tools,
            prompt=personalized_prompt,
            pre_model_hook=build_llm_input_window_hook(HISTORY_LIMIT),
            checkpointer=checkpointer,
        )

        if CACHE_DEBUG_LOGGING:
            logger.info(
                "OpenRouter routing: auto (no provider pin). "
                "DeepSeek prefix caching is automatic provider-side."
            )


        # Configurazione thread
        # NB: recursion_limit DEVE essere top-level (LangGraph ignora valori sotto "configurable").
        # Valore 10: con pre_model_hook come nodo separato, ogni ciclo richiede 3 step
        # (pre_model_hook → agent → tool), quindi 10 permette 3 cicli completi.
        config = {
            "recursion_limit": 10,
            "configurable": {
                "thread_id": generate_thread_id(user_id, prompt_version),
            }
        }
        
        return agent_executor, config, prompt_version