"""
Test suite per il tool domanda_teoria.

Questo modulo testa tutte le funzionalità del tool domanda_teoria:
- Domande casuali da tutto il database
- Domande casuali da capitoli specifici
- Domande specifiche per numero e capitolo
- Ricerca per testo
- Gestione errori e validazione parametri
"""

import pytest
import json
from unittest.mock import Mock, patch
from typing import Dict, Any, Optional

# Importa il tool da testare
from src.tools import domanda_teoria


class TestDomandaTeoria:
    """Test suite per il tool domanda_teoria."""
    
    @pytest.fixture
    def mock_quiz_service(self):
        """Mock del servizio quiz per i test."""
        mock_service = Mock()
        
        # Mock per domanda casuale
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
        
        # Mock per domanda casuale da capitolo
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
        
        # Mock per domanda specifica
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
        
        # Mock per ricerca per testo
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
        mock_service.get_random_question.return_value = None
        mock_service.get_random_question_by_field.return_value = None
        mock_service.get_question_by_capitolo_and_number.return_value = None
        mock_service.search_questions_by_text.return_value = []
        return mock_service

    def test_domanda_casuale_success(self, mock_quiz_service):
        """Test: Domanda casuale da tutto il database."""
        with patch('src.tools.QuizMongoDBService', return_value=mock_quiz_service):
            result = domanda_teoria.invoke({})
            
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

    def test_domanda_casuale_capitolo_success(self, mock_quiz_service):
        """Test: Domanda casuale da capitolo specifico."""
        with patch('src.tools.QuizMongoDBService', return_value=mock_quiz_service):
            result = domanda_teoria.invoke({"capitolo": 2})
            
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

    def test_domanda_specifica_success(self, mock_quiz_service):
        """Test: Domanda specifica per numero e capitolo."""
        with patch('src.tools.QuizMongoDBService', return_value=mock_quiz_service):
            result = domanda_teoria.invoke({"capitolo": 3, "domanda": 10})
            
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

    def test_ricerca_per_testo_success(self, mock_quiz_service):
        """Test: Ricerca per testo."""
        with patch('src.tools.QuizMongoDBService', return_value=mock_quiz_service):
            testo_ricerca = "LA SITUAZIONE DI EQUILIBRIO DI UN PARACADUTISTA IN CADUTA LIBERA"
            result = domanda_teoria.invoke({"testo": testo_ricerca})
            
            assert result is not None
            assert result["_id"] == "test_id_4"
            assert result["capitolo"] == 2
            assert result["numero"] == 20
            assert "EQUILIBRIO" in result["testo"]
            assert result["risposta_corretta"] == "A"
            
            # Verifica che sia stato chiamato il metodo corretto
            mock_quiz_service.search_questions_by_text.assert_called_once_with(testo_ricerca)

    def test_ricerca_testo_troppo_corto(self, mock_quiz_service):
        """Test: Ricerca per testo troppo corto."""
        with patch('src.tools.QuizMongoDBService', return_value=mock_quiz_service):
            # Mock per testo troppo corto
            mock_quiz_service.search_questions_by_text.return_value = []
            
            result = domanda_teoria.invoke({"testo": "AB"})
            
            assert result is not None
            assert "error" in result
            assert "Nessuna domanda trovata per il testo 'AB'" in result["error"]

    def test_validazione_capitoli(self, mock_quiz_service):
        """Test: Validazione capitoli non validi (negativi, zero, > 10)."""
        with patch('src.tools.QuizMongoDBService', return_value=mock_quiz_service):
            # Test capitolo negativo
            result = domanda_teoria.invoke({"capitolo": -1})
            assert result is not None
            assert "error" in result
            assert "capitolo numero -1 inesistente" in result["error"]
            assert "riprovare con un capitolo da 1 a 10" in result["error"]
            
            # Test capitolo zero
            result = domanda_teoria.invoke({"capitolo": 0})
            assert result is not None
            assert "error" in result
            assert "capitolo numero 0 inesistente" in result["error"]
            
            # Test capitolo > 10
            result = domanda_teoria.invoke({"capitolo": 99})
            assert result is not None
            assert "error" in result
            assert "capitolo numero 99 inesistente" in result["error"]
            
            # Verifica che non sia stato chiamato nessun metodo del database
            mock_quiz_service.get_random_question_by_field.assert_not_called()

    def test_capitoli_validi(self, mock_quiz_service):
        """Test: Verifica che i capitoli 1 e 10 siano accettati."""
        with patch('src.tools.QuizMongoDBService', return_value=mock_quiz_service):
            # Test capitolo 1 (limite inferiore)
            result = domanda_teoria.invoke({"capitolo": 1})
            assert result is not None
            assert "error" not in result
            mock_quiz_service.get_random_question_by_field.assert_called_with(field="capitolo", value=1)
            
            # Reset mock
            mock_quiz_service.reset_mock()
            
            # Test capitolo 10 (limite superiore)
            result = domanda_teoria.invoke({"capitolo": 10})
            assert result is not None
            assert "error" not in result
            mock_quiz_service.get_random_question_by_field.assert_called_with(field="capitolo", value=10)

    def test_gestione_risultati_vuoti(self, mock_quiz_service_empty):
        """Test: Gestione di tutti i casi di risultati vuoti."""
        with patch('src.tools.QuizMongoDBService', return_value=mock_quiz_service_empty):
            # Test domanda specifica non trovata
            result = domanda_teoria.invoke({"capitolo": 1, "domanda": 999})
            assert result is not None
            assert "error" in result
            assert "Domanda numero 999 non trovata nel capitolo 1" in result["error"]
            
            # Test capitolo senza domande
            result = domanda_teoria.invoke({"capitolo": 5})
            assert result is not None
            assert "error" in result
            assert "Nessuna domanda trovata per il capitolo 5" in result["error"]
            
            # Test database vuoto
            result = domanda_teoria.invoke({})
            assert result is not None
            assert "error" in result
            assert "Nessuna domanda trovata nel database" in result["error"]
            
            # Test ricerca testo non trovato
            result = domanda_teoria.invoke({"testo": "TESTO INESISTENTE"})
            assert result is not None
            assert "error" in result
            assert "Nessuna domanda trovata per il testo 'TESTO INESISTENTE'" in result["error"]

    def test_parametri_misti(self, mock_quiz_service):
        """Test: Parametri misti (capitolo e testo insieme)."""
        with patch('src.tools.QuizMongoDBService', return_value=mock_quiz_service):
            # Il tool dovrebbe dare priorità al parametro testo
            result = domanda_teoria.invoke({"capitolo": 1, "testo": "TEST"})
            
            # Verifica che sia stata chiamata la ricerca per testo
            mock_quiz_service.search_questions_by_text.assert_called_once_with("TEST")
            mock_quiz_service.get_random_question_by_field.assert_not_called()

    def test_formato_output_consistente(self, mock_quiz_service):
        """Test: Verifica che l'output abbia sempre lo stesso formato."""
        with patch('src.tools.QuizMongoDBService', return_value=mock_quiz_service):
            result = domanda_teoria.invoke({"capitolo": 1})
            
            # Verifica struttura output
            required_fields = ["_id", "capitolo", "capitolo_nome", "numero", "testo", "opzioni", "risposta_corretta"]
            for field in required_fields:
                assert field in result, f"Campo mancante: {field}"
            
            # Verifica formato opzioni
            assert isinstance(result["opzioni"], list)
            for opzione in result["opzioni"]:
                assert "id" in opzione
                assert "testo" in opzione
                assert isinstance(opzione["id"], str)
                assert isinstance(opzione["testo"], str)

    def test_output_e_un_oggetto_non_stringa(self, mock_quiz_service):
        """Test: Verifica esplicita che l'output sia un dict e non una stringa JSON."""
        with patch('src.tools.QuizMongoDBService', return_value=mock_quiz_service):
            result = domanda_teoria.invoke({"capitolo": 1})
            assert result is not None
            assert isinstance(result, dict), "L'output del tool deve essere un oggetto (dict), non una stringa"

    def test_priorita_parametri(self, mock_quiz_service):
        """Test: Verifica la priorità dei parametri."""
        with patch('src.tools.QuizMongoDBService', return_value=mock_quiz_service):
            # Testo ha priorità su capitolo
            result = domanda_teoria.invoke({"capitolo": 1, "testo": "TEST"})
            mock_quiz_service.search_questions_by_text.assert_called_once()
            
            # Reset mock
            mock_quiz_service.reset_mock()
            
            # Capitolo ha priorità su domanda casuale
            result = domanda_teoria.invoke({"capitolo": 1, "domanda": 5})
            mock_quiz_service.get_question_by_capitolo_and_number.assert_called_once()


if __name__ == "__main__":
    # Esegui i test se il file viene eseguito direttamente
    pytest.main([__file__, "-v", "-s"])
