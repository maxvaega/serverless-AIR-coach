"""Batch evaluation harness for issue #98.

Reads a JSON array of {id, question} entries, asks each to an AIR Coach-style
LangGraph agent backed by DeepSeek V4 Flash on OpenRouter (SiliconFlow), and
writes the answers + metadata to another JSON file.

Designed to run on a local machine. Skips history, checkpointer, Auth0 and
streaming. Re-uses the production S3 system prompt loader and registers
``domanda_teoria`` so the model sees the same tool spec it would in prod,
but the input questions are expected not to invoke it.
"""
import argparse
import json
import time
from pathlib import Path
from typing import Any

from langgraph.prebuilt import create_react_agent

from src.tools import domanda_teoria
from src.utils import ensure_prompt_initialized, get_prompt

from eval.llm_router import MODEL, PROVIDER, build_llm


def _tool_calls_from_messages(messages: list) -> list[dict]:
    calls = []
    for m in messages:
        if getattr(m, "type", "") == "tool":
            calls.append({
                "name": getattr(m, "name", None),
                "output": getattr(m, "content", None),
            })
    return calls


def _provider_from_metadata(meta: dict | None) -> str | None:
    if not meta:
        return None
    return meta.get("model_provider") or meta.get("provider")


def run_question(agent, question_text: str) -> dict[str, Any]:
    t0 = time.time()
    state = agent.invoke({"messages": [("user", question_text)]})
    latency = time.time() - t0
    messages = state["messages"]
    final = messages[-1]
    return {
        "answer": getattr(final, "content", ""),
        "tool_calls": _tool_calls_from_messages(messages),
        "latency_s": round(latency, 3),
        "usage": getattr(final, "usage_metadata", None) or {},
        "provider_served": _provider_from_metadata(getattr(final, "response_metadata", None)),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="DeepSeek V4 Flash eval harness (issue #98)")
    ap.add_argument("--in", dest="inp", required=True, help="Path to questions JSON")
    ap.add_argument("--out", dest="out", required=True, help="Path to write answers JSON")
    args = ap.parse_args()

    inp_path = Path(args.inp)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    ensure_prompt_initialized()
    system_prompt = get_prompt()
    if not system_prompt:
        raise RuntimeError("System prompt is empty after initialization")

    llm = build_llm()
    agent = create_react_agent(llm, [domanda_teoria], prompt=system_prompt)

    with inp_path.open() as f:
        questions = json.load(f)
    if not isinstance(questions, list):
        raise ValueError(f"Expected a JSON array in {inp_path}, got {type(questions).__name__}")

    results: list[dict[str, Any]] = []
    for q in questions:
        qid = q.get("id")
        qtext = q["question"]
        row: dict[str, Any] = {
            "id": qid,
            "question": qtext,
            "model": MODEL,
            "provider_requested": PROVIDER,
        }
        try:
            row.update(run_question(agent, qtext))
            row["error"] = None
            status = "OK"
        except Exception as e:
            row["error"] = repr(e)
            status = "ERR"
        results.append(row)
        print(f"[{qid}] {status} ({row.get('latency_s', 0)}s)")

    with out_path.open("w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"Wrote {len(results)} results to {out_path}")


if __name__ == "__main__":
    main()
