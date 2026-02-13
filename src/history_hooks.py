from typing import Awaitable, Callable

from langchain.agents.middleware import wrap_model_call, ModelRequest, ModelResponse

from .env import HISTORY_LIMIT
import logging
logger = logging.getLogger("uvicorn")
from .utils_history import last_n_turns


def build_rolling_window_middleware(max_turns: int = HISTORY_LIMIT):
    """
    Crea un middleware che seleziona gli ultimi `max_turns` turni dalla history
    e li passa al modello, senza modificare 'messages' nello stato del grafo.
    """

    @wrap_model_call
    async def rolling_window_middleware(
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        messages = request.messages
        try:
            window = last_n_turns(messages, max_turns)
            logger.debug(
                f"ROLLING_WINDOW_MW - total={len(messages)} -> window={len(window)} turns={max_turns}"
            )
            return await handler(request.override(messages=window))
        except Exception as e:
            logger.error(f"rolling_window_middleware error: {e}")
            return await handler(request)

    return rolling_window_middleware
