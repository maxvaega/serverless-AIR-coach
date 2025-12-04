"""
Test suite per i tool del quiz di teoria.

Questo modulo testa tutte le funzionalità dei tool quiz separati:
- domanda_casuale_esame: Domande casuali da tutto il database
- domanda_casuale_capitolo: Domande casuali da capitoli specifici
- domanda_specifica: Domande specifiche per numero e capitolo
- ricerca_domanda: Ricerca per testo
"""

import pytest
from unittest.mock import Mock, patch

# Importa i tool da testare dalla nuova posizione
from src.agent.tools import (
    domanda_casuale_esame,
    domanda_casuale_capitolo,
    domanda_specifica,
    ricerca_domanda,
)


class TestDomandaCasualeEsame:
    """Test suite per il tool domanda_casuale_esame."""

    @pytest.fixture
    def mock_quiz_service(self):
        """Mock del servizio quiz per i test."""
        mock_service = Mock()
        mock_service.get_random_question.return_value = {
            "_id": "test_id_1",
            "capitolo": 1,
            "capitolo_nome": "Meteorologia applicata al paracadutismo",
            "numero": 1,
            "testo": "TEST DOMANDA CASUALE",
            "opzioni": [
                {"id": "A", "testo": "Opzione A"},
                {"id": "B", "testo": "Opzione B"},
                {"id": "C", "testo": "Opzione C"},
                {"id": "D", "testo": "Opzione D"}
            ],
            "risposta_corretta": "A"
        }
        return mock_service

    @pytest.fixture
    def mock_quiz_service_empty(self):
        """Mock del servizio quiz che restituisce risultati vuoti."""
        mock_service = Mock()
        mock_service.get_random_question.return_value = None
        return mock_service

    def test_domanda_casuale_success(self, mock_quiz_service):
        """Test: Domanda casuale da tutto il database."""
        with patch('src.agent.tools._get_quiz_service', return_value=mock_quiz_service):
            result = domanda_casuale_esame.invoke({})

            assert result is not None
            assert result["_id"] == "test_id_1"
            assert result["capitolo"] == 1
            assert result["capitolo_nome"] == "Meteorologia applicata al paracadutismo"
            assert result["numero"] == 1
            assert result["testo"] == "TEST DOMANDA CASUALE"
            assert result["risposta_corretta"] == "A"
            assert len(result["opzioni"]) == 4

            # Verifica che sia stato chiamato il metodo corretto
            mock_quiz_service.get_random_question.assert_called_once()

    def test_domanda_casuale_database_vuoto(self, mock_quiz_service_empty):
        """Test: Database vuoto restituisce errore."""
        with patch('src.agent.tools._get_quiz_service', return_value=mock_quiz_service_empty):
            result = domanda_casuale_esame.invoke({})

            assert result is not None
            assert "error" in result
            assert "Nessuna domanda trovata" in result["error"]

    def test_formato_output_consistente(self, mock_quiz_service):
        """Test: Verifica che l'output abbia sempre lo stesso formato."""
        with patch('src.agent.tools._get_quiz_service', return_value=mock_quiz_service):
            result = domanda_casuale_esame.invoke({})

            # Verifica struttura output
            required_fields = ["_id", "capitolo", "capitolo_nome", "numero", "testo", "opzioni", "risposta_corretta"]
            for field in required_fields:
                assert field in result, f"Campo mancante: {field}"

            # Verifica formato opzioni
            assert isinstance(result["opzioni"], list)
            for opzione in result["opzioni"]:
                assert "id" in opzione
                assert "testo" in opzione

    def test_output_e_un_oggetto_non_stringa(self, mock_quiz_service):
        """Test: Verifica esplicita che l'output sia un dict e non una stringa JSON."""
        with patch('src.agent.tools._get_quiz_service', return_value=mock_quiz_service):
            result = domanda_casuale_esame.invoke({})
            assert result is not None
            assert isinstance(result, dict), "L'output del tool deve essere un oggetto (dict), non una stringa"


class TestDomandaCasualeCapitolo:
    """Test suite per il tool domanda_casuale_capitolo."""

    @pytest.fixture
    def mock_quiz_service(self):
        """Mock del servizio quiz per i test."""
        mock_service = Mock()
        mock_service.get_random_question_by_field.return_value = {
            "_id": "test_id_2",
            "capitolo": 2,
            "capitolo_nome": "Aerodinamica applicata al corpo in caduta libera",
            "numero": 5,
            "testo": "TEST DOMANDA CAPITOLO 2",
            "opzioni": [
                {"id": "A", "testo": "Opzione A"},
                {"id": "B", "testo": "Opzione B"},
                {"id": "C", "testo": "Opzione C"},
                {"id": "D", "testo": "Opzione D"}
            ],
            "risposta_corretta": "B"
        }
        return mock_service

    @pytest.fixture
    def mock_quiz_service_empty(self):
        """Mock del servizio quiz che restituisce risultati vuoti."""
        mock_service = Mock()
        mock_service.get_random_question_by_field.return_value = None
        return mock_service

    def test_domanda_casuale_capitolo_success(self, mock_quiz_service):
        """Test: Domanda casuale da capitolo specifico."""
        with patch('src.agent.tools._get_quiz_service', return_value=mock_quiz_service):
            result = domanda_casuale_capitolo.invoke({"capitolo": 2})

            assert result is not None
            assert result["_id"] == "test_id_2"
            assert result["capitolo"] == 2
            assert result["capitolo_nome"] == "Aerodinamica applicata al corpo in caduta libera"
            assert result["numero"] == 5
            assert result["testo"] == "TEST DOMANDA CAPITOLO 2"
            assert result["risposta_corretta"] == "B"

            # Verifica che sia stato chiamato il metodo corretto
            mock_quiz_service.get_random_question_by_field.assert_called_once_with(
                field="capitolo", value=2
            )

    def test_validazione_capitolo_negativo(self, mock_quiz_service):
        """Test: Capitolo negativo restituisce errore."""
        with patch('src.agent.tools._get_quiz_service', return_value=mock_quiz_service):
            result = domanda_casuale_capitolo.invoke({"capitolo": -1})

            assert result is not None
            assert "error" in result
            assert "non valido" in result["error"]
            mock_quiz_service.get_random_question_by_field.assert_not_called()

    def test_validazione_capitolo_zero(self, mock_quiz_service):
        """Test: Capitolo zero restituisce errore."""
        with patch('src.agent.tools._get_quiz_service', return_value=mock_quiz_service):
            result = domanda_casuale_capitolo.invoke({"capitolo": 0})

            assert result is not None
            assert "error" in result
            assert "non valido" in result["error"]

    def test_validazione_capitolo_maggiore_10(self, mock_quiz_service):
        """Test: Capitolo > 10 restituisce errore."""
        with patch('src.agent.tools._get_quiz_service', return_value=mock_quiz_service):
            result = domanda_casuale_capitolo.invoke({"capitolo": 99})

            assert result is not None
            assert "error" in result
            assert "non valido" in result["error"]

    def test_capitoli_validi_limiti(self, mock_quiz_service):
        """Test: Verifica che i capitoli 1 e 10 siano accettati."""
        with patch('src.agent.tools._get_quiz_service', return_value=mock_quiz_service):
            # Test capitolo 1 (limite inferiore)
            result = domanda_casuale_capitolo.invoke({"capitolo": 1})
            assert result is not None
            assert "error" not in result
            mock_quiz_service.get_random_question_by_field.assert_called_with(field="capitolo", value=1)

            mock_quiz_service.reset_mock()

            # Test capitolo 10 (limite superiore)
            result = domanda_casuale_capitolo.invoke({"capitolo": 10})
            assert result is not None
            assert "error" not in result
            mock_quiz_service.get_random_question_by_field.assert_called_with(field="capitolo", value=10)

    def test_capitolo_senza_domande(self, mock_quiz_service_empty):
        """Test: Capitolo senza domande restituisce errore."""
        with patch('src.agent.tools._get_quiz_service', return_value=mock_quiz_service_empty):
            result = domanda_casuale_capitolo.invoke({"capitolo": 5})

            assert result is not None
            assert "error" in result
            assert "Nessuna domanda trovata per il capitolo 5" in result["error"]


class TestDomandaSpecifica:
    """Test suite per il tool domanda_specifica."""

    @pytest.fixture
    def mock_quiz_service(self):
        """Mock del servizio quiz per i test."""
        mock_service = Mock()
        mock_service.get_question_by_capitolo_and_number.return_value = {
            "_id": "test_id_3",
            "capitolo": 3,
            "capitolo_nome": "Tecnologia degli equipaggiamenti e strumenti in uso",
            "numero": 10,
            "testo": "TEST DOMANDA SPECIFICA CAPITOLO 3 NUMERO 10",
            "opzioni": [
                {"id": "A", "testo": "Opzione A"},
                {"id": "B", "testo": "Opzione B"},
                {"id": "C", "testo": "Opzione C"},
                {"id": "D", "testo": "Opzione D"}
            ],
            "risposta_corretta": "C"
        }
        return mock_service

    @pytest.fixture
    def mock_quiz_service_empty(self):
        """Mock del servizio quiz che restituisce risultati vuoti."""
        mock_service = Mock()
        mock_service.get_question_by_capitolo_and_number.return_value = None
        return mock_service

    def test_domanda_specifica_success(self, mock_quiz_service):
        """Test: Domanda specifica per numero e capitolo."""
        with patch('src.agent.tools._get_quiz_service', return_value=mock_quiz_service):
            result = domanda_specifica.invoke({"capitolo": 3, "numero": 10})

            assert result is not None
            assert result["_id"] == "test_id_3"
            assert result["capitolo"] == 3
            assert result["capitolo_nome"] == "Tecnologia degli equipaggiamenti e strumenti in uso"
            assert result["numero"] == 10
            assert result["testo"] == "TEST DOMANDA SPECIFICA CAPITOLO 3 NUMERO 10"
            assert result["risposta_corretta"] == "C"

            # Verifica che sia stato chiamato il metodo corretto
            mock_quiz_service.get_question_by_capitolo_and_number.assert_called_once_with(
                capitolo=3, numero=10
            )

    def test_domanda_specifica_non_trovata(self, mock_quiz_service_empty):
        """Test: Domanda specifica non trovata."""
        with patch('src.agent.tools._get_quiz_service', return_value=mock_quiz_service_empty):
            result = domanda_specifica.invoke({"capitolo": 1, "numero": 999})

            assert result is not None
            assert "error" in result
            assert "Domanda numero 999 non trovata nel capitolo 1" in result["error"]

    def test_validazione_capitolo_non_valido(self, mock_quiz_service):
        """Test: Capitolo non valido restituisce errore."""
        with patch('src.agent.tools._get_quiz_service', return_value=mock_quiz_service):
            result = domanda_specifica.invoke({"capitolo": 15, "numero": 5})

            assert result is not None
            assert "error" in result
            assert "non valido" in result["error"]
            mock_quiz_service.get_question_by_capitolo_and_number.assert_not_called()

    def test_validazione_numero_non_valido(self, mock_quiz_service):
        """Test: Numero domanda non valido restituisce errore."""
        with patch('src.agent.tools._get_quiz_service', return_value=mock_quiz_service):
            result = domanda_specifica.invoke({"capitolo": 3, "numero": 0})

            assert result is not None
            assert "error" in result
            assert "non valido" in result["error"]
            mock_quiz_service.get_question_by_capitolo_and_number.assert_not_called()

    def test_validazione_numero_negativo(self, mock_quiz_service):
        """Test: Numero domanda negativo restituisce errore."""
        with patch('src.agent.tools._get_quiz_service', return_value=mock_quiz_service):
            result = domanda_specifica.invoke({"capitolo": 3, "numero": -5})

            assert result is not None
            assert "error" in result
            assert "non valido" in result["error"]


class TestRicercaDomanda:
    """Test suite per il tool ricerca_domanda."""

    @pytest.fixture
    def mock_quiz_service(self):
        """Mock del servizio quiz per i test."""
        mock_service = Mock()
        mock_service.search_questions_by_text.return_value = [
            {
                "_id": "test_id_4",
                "capitolo": 2,
                "capitolo_nome": "Aerodinamica applicata al corpo in caduta libera",
                "numero": 20,
                "testo": "QUAL È LA SITUAZIONE DI EQUILIBRIO DI UN PARACADUTISTA IN CADUTA LIBERA",
                "opzioni": [
                    {"id": "A", "testo": "Instabile"},
                    {"id": "B", "testo": "Indifferente"},
                    {"id": "C", "testo": "Normale"},
                    {"id": "D", "testo": "Stabile"}
                ],
                "risposta_corretta": "A"
            }
        ]
        return mock_service

    @pytest.fixture
    def mock_quiz_service_empty(self):
        """Mock del servizio quiz che restituisce risultati vuoti."""
        mock_service = Mock()
        mock_service.search_questions_by_text.return_value = []
        return mock_service

    def test_ricerca_per_testo_success(self, mock_quiz_service):
        """Test: Ricerca per testo."""
        with patch('src.agent.tools._get_quiz_service', return_value=mock_quiz_service):
            testo_ricerca = "EQUILIBRIO PARACADUTISTA CADUTA LIBERA"
            result = ricerca_domanda.invoke({"testo": testo_ricerca})

            assert result is not None
            assert result["_id"] == "test_id_4"
            assert result["capitolo"] == 2
            assert result["numero"] == 20
            assert "EQUILIBRIO" in result["testo"]
            assert result["risposta_corretta"] == "A"

            # Verifica che sia stato chiamato il metodo corretto
            mock_quiz_service.search_questions_by_text.assert_called_once_with(testo_ricerca)

    def test_ricerca_testo_non_trovato(self, mock_quiz_service_empty):
        """Test: Ricerca per testo non trovato."""
        with patch('src.agent.tools._get_quiz_service', return_value=mock_quiz_service_empty):
            result = ricerca_domanda.invoke({"testo": "TESTO INESISTENTE"})

            assert result is not None
            assert "error" in result
            assert "Nessuna domanda trovata per 'TESTO INESISTENTE'" in result["error"]

    def test_ricerca_testo_vuoto(self, mock_quiz_service):
        """Test: Ricerca con testo vuoto restituisce errore."""
        with patch('src.agent.tools._get_quiz_service', return_value=mock_quiz_service):
            result = ricerca_domanda.invoke({"testo": ""})

            assert result is not None
            assert "error" in result
            assert "Specifica un argomento" in result["error"]
            mock_quiz_service.search_questions_by_text.assert_not_called()

    def test_ricerca_testo_solo_spazi(self, mock_quiz_service):
        """Test: Ricerca con solo spazi restituisce errore."""
        with patch('src.agent.tools._get_quiz_service', return_value=mock_quiz_service):
            result = ricerca_domanda.invoke({"testo": "   "})

            assert result is not None
            assert "error" in result
            assert "Specifica un argomento" in result["error"]


class TestOutputConsistency:
    """Test per verificare la consistenza dell'output tra tutti i tool."""

    @pytest.fixture
    def mock_question(self):
        """Domanda mock standard."""
        return {
            "_id": "test_id",
            "capitolo": 1,
            "capitolo_nome": "Test Capitolo",
            "numero": 1,
            "testo": "Test domanda",
            "opzioni": [
                {"id": "A", "testo": "Opzione A"},
                {"id": "B", "testo": "Opzione B"},
                {"id": "C", "testo": "Opzione C"},
                {"id": "D", "testo": "Opzione D"}
            ],
            "risposta_corretta": "A"
        }

    def test_tutti_i_tool_restituiscono_stesso_formato(self, mock_question):
        """Test: Tutti i tool restituiscono lo stesso formato output."""
        mock_service = Mock()
        mock_service.get_random_question.return_value = mock_question
        mock_service.get_random_question_by_field.return_value = mock_question
        mock_service.get_question_by_capitolo_and_number.return_value = mock_question
        mock_service.search_questions_by_text.return_value = [mock_question]

        required_fields = ["_id", "capitolo", "capitolo_nome", "numero", "testo", "opzioni", "risposta_corretta"]

        with patch('src.agent.tools._get_quiz_service', return_value=mock_service):
            # Test domanda_casuale_esame
            result1 = domanda_casuale_esame.invoke({})
            for field in required_fields:
                assert field in result1, f"domanda_casuale_esame: campo mancante {field}"

            # Test domanda_casuale_capitolo
            result2 = domanda_casuale_capitolo.invoke({"capitolo": 1})
            for field in required_fields:
                assert field in result2, f"domanda_casuale_capitolo: campo mancante {field}"

            # Test domanda_specifica
            result3 = domanda_specifica.invoke({"capitolo": 1, "numero": 1})
            for field in required_fields:
                assert field in result3, f"domanda_specifica: campo mancante {field}"

            # Test ricerca_domanda
            result4 = ricerca_domanda.invoke({"testo": "test"})
            for field in required_fields:
                assert field in result4, f"ricerca_domanda: campo mancante {field}"


if __name__ == "__main__":
    # Esegui i test se il file viene eseguito direttamente
    pytest.main([__file__, "-v", "-s"])
