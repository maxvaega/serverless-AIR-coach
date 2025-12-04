"""
Modulo agent per AIR Coach.

Contiene:
- AgentManager: Factory per la creazione di agenti LangGraph
- StreamingHandler: Gestione degli eventi di streaming
- StateManager: Gestione dello stato dell'agente
- Tools: Tool per il quiz di teoria (domanda_casuale_esame, domanda_casuale_capitolo,
  domanda_specifica, ricerca_domanda)

Gli import pesanti (AgentManager, StreamingHandler) sono lazy per permettere
l'import dei tool senza dipendenze esterne durante i test.
"""


def __getattr__(name):
    """Lazy import per evitare di caricare dipendenze pesanti all'import del package."""
    if name == "AgentManager":
        from .agent_manager import AgentManager
        return AgentManager
    elif name == "StreamingHandler":
        from .streaming_handler import StreamingHandler
        return StreamingHandler
    elif name == "StateManager":
        from .state_manager import StateManager
        return StateManager
    elif name == "quiz_tools":
        from .tools import quiz_tools
        return quiz_tools
    elif name == "domanda_casuale_esame":
        from .tools import domanda_casuale_esame
        return domanda_casuale_esame
    elif name == "domanda_casuale_capitolo":
        from .tools import domanda_casuale_capitolo
        return domanda_casuale_capitolo
    elif name == "domanda_specifica":
        from .tools import domanda_specifica
        return domanda_specifica
    elif name == "ricerca_domanda":
        from .tools import ricerca_domanda
        return ricerca_domanda
    elif name == "_serialize_tool_output":
        from .tools import _serialize_tool_output
        return _serialize_tool_output
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "AgentManager",
    "StreamingHandler",
    "StateManager",
    "quiz_tools",
    "domanda_casuale_esame",
    "domanda_casuale_capitolo",
    "domanda_specifica",
    "ricerca_domanda",
    "_serialize_tool_output",
]
