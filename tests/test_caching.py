"""
Test suite per il monitoraggio cache con DeepSeek via OpenRouter.

Il prefix-caching di DeepSeek è automatico lato provider e non richiede
configurazione client-side. Questi test verificano:
  - che l'LLM venga costruito con base_url OpenRouter e gli header stabili
    richiesti per lo sticky routing;
  - che cache_monitor estragga correttamente i cached tokens dallo schema
    OpenAI-compat (``usage_metadata.input_token_details.cache_read`` o
    ``response_metadata.usage.prompt_tokens_details.cached_tokens``).
"""

import pytest
import unittest.mock as mock
from unittest.mock import MagicMock, patch
import os
import sys

# Mark all tests in this file as unit tests (fast, mocked)
pytestmark = pytest.mark.unit

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.env import settings
from src.agent.agent_manager import AgentManager
from src.monitoring.cache_monitor import (
    log_cache_metrics,
    log_request_context,
    analyze_cache_effectiveness,
)


class TestOpenRouterConfiguration:
    """Configurazione env OpenRouter."""

    def test_openrouter_base_url_default(self):
        assert settings.OPENROUTER_BASE_URL == "https://openrouter.ai/api/v1"

    def test_source_default_targets_deepseek(self):
        """env.py deve dichiarare DeepSeek come default (env var può fare override)."""
        import inspect
        import src.env as env_mod
        source = inspect.getsource(env_mod)
        assert 'FORCED_MODEL' in source
        assert '"deepseek/deepseek-v4-flash"' in source, (
            "Il default literal di FORCED_MODEL in src/env.py deve essere DeepSeek"
        )


class TestAgentManagerLLM:
    """Verifica che AgentManager costruisca ChatOpenAI verso OpenRouter."""

    @mock.patch('src.agent.agent_manager.ChatOpenAI')
    @mock.patch('src.agent.agent_manager.create_react_agent')
    @mock.patch('src.agent.agent_manager.get_personalized_prompt_for_user')
    def test_llm_built_against_openrouter(self, mock_prompt, mock_agent, mock_llm):
        mock_prompt.return_value = ("test_prompt", 1, None)
        mock_llm.return_value = MagicMock()
        mock_agent.return_value = MagicMock()

        AgentManager.create_agent("test_user")

        mock_llm.assert_called_once()
        kwargs = mock_llm.call_args[1]
        assert kwargs["base_url"] == "https://openrouter.ai/api/v1"
        assert kwargs["model"] == settings.FORCED_MODEL
        assert "api_key" in kwargs
        # Header stabili → OpenRouter sticky routing (cache caldo)
        headers = kwargs["default_headers"]
        assert "HTTP-Referer" in headers
        assert "X-Title" in headers

    @mock.patch('src.agent.agent_manager.ChatOpenAI')
    @mock.patch('src.agent.agent_manager.create_react_agent')
    @mock.patch('src.agent.agent_manager.get_personalized_prompt_for_user')
    def test_no_provider_pin(self, mock_prompt, mock_agent, mock_llm):
        """Verifica che NON sia impostato un pin di provider (auto-routing)."""
        mock_prompt.return_value = ("test_prompt", 1, None)
        mock_llm.return_value = MagicMock()
        mock_agent.return_value = MagicMock()

        AgentManager.create_agent("test_user")

        kwargs = mock_llm.call_args[1]
        extra_body = kwargs.get("extra_body") or {}
        provider = extra_body.get("provider") if isinstance(extra_body, dict) else None
        assert not provider, "OpenRouter deve restare in auto-routing per resilienza"


class TestCacheMonitoring:
    """Test estrazione metriche cache con schema OpenAI-compat."""

    def test_cache_read_from_input_token_details(self):
        """LangChain ChatOpenAI mette i cached tokens in input_token_details.cache_read."""
        mock_response = MagicMock()
        mock_response.usage_metadata = {
            "input_tokens": 200,
            "output_tokens": 50,
            "total_tokens": 250,
            "input_token_details": {"cache_read": 120},
        }

        with patch('src.monitoring.cache_monitor.logger') as mock_logger:
            metrics = log_cache_metrics(mock_response)

            assert metrics['cached_tokens'] == 120
            assert metrics['total_tokens'] == 250
            assert metrics['cache_ratio'] == pytest.approx(120 / 250)
            mock_logger.info.assert_called()

    def test_cache_from_response_metadata_openai_shape(self):
        """Fallback: response_metadata.usage.prompt_tokens_details.cached_tokens."""
        mock_response = MagicMock()
        mock_response.usage_metadata = None
        mock_response.response_metadata = {
            'usage': {
                'total_tokens': 300,
                'prompt_tokens_details': {'cached_tokens': 90},
            }
        }

        metrics = log_cache_metrics(mock_response)

        assert metrics['cached_tokens'] == 90
        assert metrics['total_tokens'] == 300
        assert metrics['cache_ratio'] == pytest.approx(90 / 300)

    def test_no_cache_data_returns_zero(self):
        mock_response = MagicMock()
        mock_response.usage_metadata = None
        mock_response.response_metadata = {}

        metrics = log_cache_metrics(mock_response)

        assert metrics['cached_tokens'] == 0
        assert metrics['total_tokens'] == 0
        assert metrics['cache_ratio'] == 0.0
        assert 'timestamp' in metrics

    def test_log_request_context(self):
        with patch('src.monitoring.cache_monitor.logger') as mock_logger:
            log_request_context("test_user", "deepseek/deepseek-v4-flash")

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0][0]
            assert "test_user" in call_args
            assert "deepseek/deepseek-v4-flash" in call_args

    def test_analyze_cache_effectiveness(self):
        metrics_history = [
            {"cached_tokens": 100, "total_tokens": 200},
            {"cached_tokens": 0, "total_tokens": 150},
            {"cached_tokens": 50, "total_tokens": 100},
        ]

        analysis = analyze_cache_effectiveness(metrics_history)

        assert analysis['total_requests'] == 3
        assert analysis['cache_hits'] == 2
        assert analysis['hit_rate_percent'] == pytest.approx(66.67, rel=1e-2)
        assert analysis['total_tokens'] == 450
        assert analysis['cached_tokens'] == 150
        assert analysis['overall_cache_ratio_percent'] == pytest.approx(33.33, rel=1e-2)

    def test_analyze_cache_effectiveness_empty_history(self):
        analysis = analyze_cache_effectiveness([])
        assert "error" in analysis


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
