from typing import List

from langchain_core.messages import BaseMessage, HumanMessage

from .logging_config import logger


def last_n_turns(messages: List[BaseMessage], n_turns: int) -> List[BaseMessage]:
    """
    Restituisce i messaggi appartenenti agli ultimi `n_turns` turni conversazionali.
    Un turno inizia con un HumanMessage e include tutti i messaggi successivi
    fino al prossimo HumanMessage (escluso).

    Note:
    - Il conteggio si basa solo sugli HumanMessage, indipendentemente da messaggi
      di assistente/tool vuoti o assenti.
    - Se non ci sono HumanMessage, ritorna l'intera lista (fail-safe).
    - Se n_turns <= 0, ritorna lista vuota.
    """
    if not messages or n_turns <= 0:
        return []

    human_indices = [i for i, m in enumerate(messages) if isinstance(m, HumanMessage)]
    if not human_indices:
        return messages

    start_human_idx = human_indices[-n_turns] if len(human_indices) >= n_turns else human_indices[0]
    window = messages[start_human_idx:]
    try:
        logger.debug(
            f"HISTORY_WINDOW - total_msgs={len(messages)} start_idx={start_human_idx} "
            f"window_size={len(window)} human_count={len(human_indices)} "
            f"turns_kept={min(n_turns, len(human_indices))}"
        )
    except Exception:
        pass
    return window


