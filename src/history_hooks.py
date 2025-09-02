from typing import Any, Dict

from .env import HISTORY_LIMIT
from .logging_config import logger
from .utils_history import last_n_turns


def build_llm_input_window_hook(max_turns: int = HISTORY_LIMIT):
    """
    Crea un pre_model_hook che seleziona gli ultimi `max_turns` turni dalla history
    del grafo e li passa al modello via 'llm_input_messages', senza modificare
    'messages' nello stato del grafo.
    """

    def pre_model_hook(state: Dict[str, Any]) -> Dict[str, Any]:
        messages = state.get("messages", [])
        try:
            window = last_n_turns(messages, max_turns)
            try:
                logger.debug(
                    f"PRE_MODEL_HOOK - total={len(messages)} -> window={len(window)} turns={max_turns}"
                )
            except Exception:
                pass
            return {"llm_input_messages": window}
        except Exception as e:
            logger.error(f"pre_model_hook error: {e}")
            return {"llm_input_messages": messages}

    return pre_model_hook


