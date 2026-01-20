import pytest
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from src.utils_history import last_n_turns

# Mark all tests in this file as unit tests (fast, mocked)
pytestmark = pytest.mark.unit


def test_last_n_turns_basic():
    msgs = [
        HumanMessage("u1"), AIMessage("a1"),
        HumanMessage("u2"), ToolMessage("tool2", tool_call_id="t2"), AIMessage("a2"),
        HumanMessage("u3"),
    ]
    win = last_n_turns(msgs, 2)
    assert [type(m).__name__ for m in win] == ["HumanMessage", "ToolMessage", "AIMessage", "HumanMessage"]
    assert win[0].content == "u2"


def test_last_n_turns_with_empty_assistant_and_tool():
    msgs = [
        HumanMessage("u1"), AIMessage("")
    ]
    msgs += [HumanMessage("u2"), ToolMessage("", tool_call_id="t")]
    msgs += [HumanMessage("u3"), AIMessage("a3")]
    win = last_n_turns(msgs, 1)
    assert [type(m).__name__ for m in win] == ["HumanMessage", "AIMessage"]
    assert win[0].content == "u3"


def test_last_n_turns_no_human():
    msgs = [AIMessage("a"), ToolMessage("t", tool_call_id="x")]
    win = last_n_turns(msgs, 2)
    assert win == msgs


def test_last_n_turns_zero():
    msgs = [HumanMessage("u1"), AIMessage("a1")]
    assert last_n_turns(msgs, 0) == []


