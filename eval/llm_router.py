"""Builder for the OpenRouter-backed ChatOpenAI used by the eval harness.

Pins routing to SiliconFlow and refuses fallbacks so the evaluation always
reflects that specific provider's served behavior.
"""
import os
from typing import Set

import httpx
from langchain_openai import ChatOpenAI

MODEL = "deepseek/deepseek-v4-flash"
PROVIDER = "siliconflow"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def _collect_provider_slugs(payload: dict) -> Set[str]:
    """Best-effort extraction of provider slugs from the /endpoints response.

    OpenRouter's schema has shifted over time; tolerate both top-level and
    nested-data shapes and both ``provider_name`` and ``tag`` keys.
    """
    data = payload.get("data", payload)
    endpoints = data.get("endpoints", []) if isinstance(data, dict) else []
    slugs: Set[str] = set()
    for ep in endpoints:
        if not isinstance(ep, dict):
            continue
        for key in ("provider_name", "tag", "name", "slug"):
            value = ep.get(key)
            if isinstance(value, str) and value:
                slugs.add(value.lower())
    return slugs


def _verify_provider_available() -> None:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")

    url = f"{OPENROUTER_BASE_URL}/models/{MODEL}/endpoints"
    resp = httpx.get(
        url,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=10,
    )
    resp.raise_for_status()
    slugs = _collect_provider_slugs(resp.json())
    if PROVIDER not in slugs:
        raise RuntimeError(
            f"Provider '{PROVIDER}' not in endpoints for {MODEL}. "
            f"Found: {sorted(slugs) or '<empty>'}"
        )


def build_llm(skip_verification: bool = False) -> ChatOpenAI:
    """Construct a ChatOpenAI bound to OpenRouter, pinned to SiliconFlow.

    Set ``skip_verification=True`` only for offline tests that don't reach the
    network. The default fails fast if the provider isn't listed for the model.
    """
    if not skip_verification:
        _verify_provider_available()

    return ChatOpenAI(
        model=MODEL,
        api_key=os.environ["OPENROUTER_API_KEY"],
        base_url=OPENROUTER_BASE_URL,
        temperature=0.7,
        extra_body={
            "provider": {
                "only": [PROVIDER],
                "allow_fallbacks": False,
            }
        },
        default_headers={
            "HTTP-Referer": "https://github.com/maxvaega/serverless-AIR-coach",
            "X-Title": "AIR Coach eval harness",
        },
    )
