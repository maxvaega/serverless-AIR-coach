import pytest
from langchain_core.messages import HumanMessage, AIMessage
from src.history_hooks import build_llm_input_window_hook

pytestmark = pytest.mark.unit


def test_pre_model_hook_returns_llm_input_messages():
    hook = build_llm_input_window_hook(1)
    state = {"messages": [HumanMessage("u1"), AIMessage("a1"), HumanMessage("u2")]}
    update = hook(state)
    assert "llm_input_messages" in update
    msgs = update["llm_input_messages"]
    assert len(msgs) == 1 and isinstance(msgs[0], HumanMessage) and msgs[0].content == "u2"
