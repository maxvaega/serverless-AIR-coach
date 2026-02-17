from typing import Any, Dict
from .env import HISTORY_LIMIT
import logging
logger = logging.getLogger("uvicorn")
from .utils_history import last_n_turns


def build_llm_input_window_hook(max_turns: int = HISTORY_LIMIT):
    def pre_model_hook(state: Dict[str, Any]) -> Dict[str, Any]:
        messages = state.get("messages", [])
        try:
            window = last_n_turns(messages, max_turns)
            logger.debug(f"PRE_MODEL_HOOK - total={len(messages)} -> window={len(window)} turns={max_turns}")
            return {"llm_input_messages": window}
        except Exception as e:
            logger.error(f"pre_model_hook error: {e}")
            return {"llm_input_messages": messages}
    return pre_model_hook
