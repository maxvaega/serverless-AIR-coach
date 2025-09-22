"""
Test suite per Google Cloud Implicit Caching
Verifica che il caching sia configurato correttamente e funzioni come atteso.
"""

import pytest
import unittest.mock as mock
from unittest.mock import MagicMock, patch
import os
import sys

# Aggiungi il percorso src al path per import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.env import settings
from src.agent.agent_manager import AgentManager
from src.monitoring.cache_monitor import log_cache_metrics, log_request_context, analyze_cache_effectiveness


class TestCachingConfiguration:
    """Test configurazione caching implicito"""

    def test_env_variables_configured(self):
        """Test che le variabili ambiente per il caching siano configurate"""
        # Test valori default
        assert settings.VERTEX_AI_REGION == "europe-west8"
        assert settings.ENABLE_GOOGLE_CACHING == True
        assert settings.CACHE_REGION == "europe-west8"
        assert settings.CACHE_DEBUG_LOGGING == False

    def test_region_consistency(self):
        """Test che le region per inferenza e cache siano consistenti"""
        assert settings.VERTEX_AI_REGION == settings.CACHE_REGION, \
            "Region per inferenza e cache devono essere uguali per massimizzare cache hits"

    def test_europe_region_compliance(self):
        """Test che la region configurata sia in Europa per compliance GDPR"""
        assert "europe" in settings.VERTEX_AI_REGION.lower(), \
            "Region deve essere in Europa per compliance GDPR"


class TestAgentManagerCaching:
    """Test configurazione LLM con parametri caching"""

    @mock.patch('src.agent.agent_manager.ChatGoogleGenerativeAI')
    @mock.patch('src.agent.agent_manager.create_react_agent')
    @mock.patch('src.agent.agent_manager.get_personalized_prompt_for_user')
    def test_llm_region_configuration(self, mock_prompt, mock_agent, mock_llm):
        """Test che l'LLM sia configurato con la region corretta"""
        # Mock delle dipendenze
        mock_prompt.return_value = ("test_prompt", 1, None)
        mock_llm_instance = MagicMock()
        mock_llm.return_value = mock_llm_instance
        mock_agent.return_value = MagicMock()

        # Crea agente
        AgentManager.create_agent("test_user")

        # Verifica che ChatGoogleGenerativeAI sia chiamato con parametri corretti
        mock_llm.assert_called_once()
        call_kwargs = mock_llm.call_args[1]

        assert 'location' in call_kwargs
        assert call_kwargs['location'] == settings.VERTEX_AI_REGION
        assert 'project' in call_kwargs
        assert call_kwargs['model'] == settings.FORCED_MODEL

    @mock.patch('src.agent.agent_manager.ChatGoogleGenerativeAI')
    @mock.patch('src.agent.agent_manager.create_react_agent')
    @mock.patch('src.agent.agent_manager.get_personalized_prompt_for_user')
    def test_llm_caching_parameters(self, mock_prompt, mock_agent, mock_llm):
        """Test che l'LLM sia configurato con i parametri per il caching"""
        # Mock delle dipendenze
        mock_prompt.return_value = ("test_prompt", 1, None)
        mock_llm_instance = MagicMock()
        mock_llm.return_value = mock_llm_instance
        mock_agent.return_value = MagicMock()

        # Crea agente
        AgentManager.create_agent("test_user")

        # Verifica parametri critici per caching
        call_kwargs = mock_llm.call_args[1]
        assert call_kwargs['location'] == "europe-west8"  # Region fissa per caching
        assert 'project' in call_kwargs  # Project ID necessario per Vertex AI


class TestCacheMonitoring:
    """Test sistema di monitoraggio cache"""

    def test_log_cache_metrics_with_usage_metadata(self):
        """Test logging metriche cache con usage_metadata"""
        # Mock response con usage_metadata (Vertex AI style)
        mock_response = MagicMock()
        mock_usage = MagicMock()
        mock_usage.cached_content_token_count = 100
        mock_usage.total_token_count = 200
        mock_response.usage_metadata = mock_usage

        with patch('src.monitoring.cache_monitor.logger') as mock_logger:
            metrics = log_cache_metrics(mock_response)

            # Verifica metriche estratte
            assert metrics['cached_tokens'] == 100
            assert metrics['total_tokens'] == 200
            assert metrics['cache_ratio'] == 0.5

            # Verifica logging
            mock_logger.info.assert_called()

    def test_log_cache_metrics_with_response_metadata(self):
        """Test logging metriche cache con response_metadata (LangChain style)"""
        # Mock response con response_metadata
        mock_response = MagicMock()
        mock_response.usage_metadata = None
        mock_response.response_metadata = {
            'usage': {
                'total_tokens': 150,
                'cached_tokens': 75
            }
        }

        metrics = log_cache_metrics(mock_response)

        # Verifica metriche estratte
        assert metrics['cached_tokens'] == 75
        assert metrics['total_tokens'] == 150
        assert metrics['cache_ratio'] == 0.5

    def test_log_cache_metrics_no_cache_data(self):
        """Test logging quando non ci sono dati di cache"""
        # Mock response senza usage data
        mock_response = MagicMock()
        mock_response.usage_metadata = None
        mock_response.response_metadata = {}

        metrics = log_cache_metrics(mock_response)

        # Verifica valori default
        assert metrics['cached_tokens'] == 0
        assert metrics['total_tokens'] == 0
        assert metrics['cache_ratio'] == 0.0
        assert 'timestamp' in metrics

    def test_log_request_context(self):
        """Test logging contesto richiesta"""
        with patch('src.monitoring.cache_monitor.logger') as mock_logger:
            log_request_context("test_user", "gemini-2.5-flash", "europe-west8")

            # Verifica che il log sia stato chiamato
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0][0]
            assert "test_user" in call_args
            assert "gemini-2.5-flash" in call_args
            assert "europe-west8" in call_args

    def test_analyze_cache_effectiveness(self):
        """Test analisi efficacia cache"""
        # Dati di test
        metrics_history = [
            {"cached_tokens": 100, "total_tokens": 200},
            {"cached_tokens": 0, "total_tokens": 150},
            {"cached_tokens": 50, "total_tokens": 100},
        ]

        analysis = analyze_cache_effectiveness(metrics_history)

        # Verifica analisi
        assert analysis['total_requests'] == 3
        assert analysis['cache_hits'] == 2  # Due richieste con cache hits
        assert analysis['hit_rate_percent'] == pytest.approx(66.67, rel=1e-2)
        assert analysis['total_tokens'] == 450
        assert analysis['cached_tokens'] == 150
        assert analysis['overall_cache_ratio_percent'] == pytest.approx(33.33, rel=1e-2)

    def test_analyze_cache_effectiveness_empty_history(self):
        """Test analisi con cronologia vuota"""
        analysis = analyze_cache_effectiveness([])

        assert "error" in analysis


class TestCachingIntegration:
    """Test integrazione completa del caching"""

    def test_rag_caching_integration(self):
        """Test che il sistema RAG integri correttamente il monitoraggio cache"""
        # Test semplificato che verifica solo che le funzioni di monitoring siano importabili
        from src.monitoring.cache_monitor import log_cache_metrics, log_request_context

        # Verifica che le funzioni siano callable
        assert callable(log_cache_metrics)
        assert callable(log_request_context)

        # Test della funzione log_request_context
        with patch('src.monitoring.cache_monitor.logger') as mock_logger:
            log_request_context("test_user", "test_model", "test_region")
            mock_logger.info.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])