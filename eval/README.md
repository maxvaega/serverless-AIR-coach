# Eval Harness — Issue #98 (DeepSeek V4 Flash)

Offline batch harness that runs a list of questions through an AIR Coach-style
LangGraph agent backed by **DeepSeek V4 Flash via OpenRouter, routed to
SiliconFlow**, and writes the answers + per-question metadata to a JSON file.

This is a local-machine tool. It is **not** wired into the FastAPI app, not
deployed to Vercel, and intentionally skips history, checkpointer, Auth0 and
streaming. It reuses the production S3 system prompt loader and registers
`domanda_teoria` so the model sees the same tool spec it sees in prod.

## Requirements

- The project `.venv` with `requirements.txt` installed (which now includes
  `langchain-openai`).
- `OPENROUTER_API_KEY` set (OpenRouter account with credits).
- The existing `AWS_*` / `BUCKET_NAME` env vars needed by the S3 system-prompt
  loader (same ones the prod app uses).
- **No MongoDB needed** for the example questions: they are deliberately
  phrased so the model should answer directly without calling `domanda_teoria`.
  If you add a question that triggers the tool, that row will error out (the
  harness keeps going).

## Usage

```bash
source .venv/bin/activate
export OPENROUTER_API_KEY=sk-or-...
# Plus AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / BUCKET_NAME from .env

python -m eval.harness \
  --in eval/questions.example.json \
  --out eval/runs/$(date +%Y%m%d-%H%M%S).json
```

The harness:

1. Verifies that `siliconflow` is a listed endpoint for
   `deepseek/deepseek-v4-flash` on OpenRouter (fails fast if not).
2. Loads the system prompt from S3 (`ensure_prompt_initialized` →
   `get_prompt`).
3. Builds one `create_react_agent` instance with the `domanda_teoria` tool
   registered but no checkpointer / pre-model hook.
4. Iterates the input list sequentially. Each question is a fresh,
   single-turn `agent.invoke({"messages": [("user", q)]})`.
5. Catches per-question exceptions, records them in `error`, and continues.

## Input format

A JSON array of objects. Required: `question`. Optional: `id`.

```json
[
  { "id": "q1", "question": "Quale è la quota minima di apertura?" }
]
```

## Output format

Same array length, each row:

```json
{
  "id": "q1",
  "question": "...",
  "model": "deepseek/deepseek-v4-flash",
  "provider_requested": "siliconflow",
  "provider_served": "siliconflow",
  "answer": "<final assistant text>",
  "tool_calls": [],
  "latency_s": 2.34,
  "usage": { "input_tokens": 1234, "output_tokens": 89, "total_tokens": 1323 },
  "error": null
}
```

`provider_served` is best-effort: it reads `response_metadata.model_provider`
or `response_metadata.provider` if OpenRouter populates them. Inspect a few
rows to confirm SiliconFlow actually served the requests — with
`allow_fallbacks: False` it should always be `siliconflow` or the request
should fail outright.

## What's intentionally not here

- No automated quality scoring (judge LLM, BLEU, etc.) — comparison is meant
  to be human-eyeballed against the equivalent Gemini run.
- No concurrency. Sequential keeps cost / rate-limit behaviour predictable.
- No A/B routing in prod, no migration of `src/`. Production stays on Gemini
  until a human decides to switch.
