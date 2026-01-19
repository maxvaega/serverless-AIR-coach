"""
LangGraph tools for the AI Coach API.
Provides quiz question retrieval functionality.
"""
import json
from typing import Optional

from langchain_core.tools import tool
from langchain_core.messages import ToolMessage

from src.services.database.database_quiz_service import QuizMongoDBService

import logging
logger = logging.getLogger("uvicorn")


# Chapter names for reference
CHAPTER_NAMES = {
    1: "Meteorologia applicata al paracadutismo",
    2: "Aerodinamica applicata al corpo in caduta libera",
    3: "Tecnologia degli equipaggiamenti e strumenti in uso",
    4: "Tecnica di direzione di lancio",
    5: "Tecnica di utilizzo dei paracadute plananti",
    6: "Elementi e procedure generali di sicurezza",
    7: "Elementi e procedure di sicurezza nel lavoro relativo in caduta libera",
    8: "Elementi e procedure di sicurezza nel volo in formazione con paracadute planante",
    9: "Procedure in situazioni di emergenza",
    10: "Normativa aeronautica attinente il paracadutismo",
}

MIN_CHAPTER = 1
MAX_CHAPTER = 10


def _normalize_optional_param(value) -> Optional[str]:
    """Normalize parameter: treat empty strings as None."""
    if isinstance(value, str) and not value.strip():
        return None
    return value


def _make_error(message: str) -> dict:
    """Create standardized error response."""
    return {"error": f"Domanda teoria: {message}"}


def _serialize_tool_output(tool_output) -> dict:
    """Serialize tool output to JSON-compatible format."""
    if isinstance(tool_output, ToolMessage):
        content = tool_output.content
        if isinstance(content, str):
            content = _try_parse_json(content)
        return {
            "content": content,
            "tool_call_id": getattr(tool_output, 'tool_call_id', None)
        }

    if isinstance(tool_output, (dict, list, int, float, bool)):
        return tool_output

    if isinstance(tool_output, str):
        parsed = _try_parse_json(tool_output)
        if parsed is not None:
            return parsed
        return {"content": tool_output}

    return {"content": str(tool_output)}


def _try_parse_json(text: str):
    """Try to parse JSON from string, return None if not valid JSON."""
    stripped = text.strip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logger.warning("TOOL - Serialization failed - not valid JSON")
    return None


def _get_quiz_service() -> Optional[QuizMongoDBService]:
    """Create quiz service instance with error handling."""
    try:
        return QuizMongoDBService()
    except Exception as e:
        logger.error(f"TOOL: domanda_teoria - Errore inizializzazione servizio quiz: {e}")
        return None


@tool(return_direct=True)
def domanda_teoria(capitolo: Optional[int] = None, domanda: Optional[int] = None, testo: Optional[str] = None) -> dict:
    """
    Scopo:
        Recupera e presenta all'utente una domanda d'esame per la teoria della licenza di paracadutismo.
        Questo tool gestisce l'interfaccia del quiz; tu devi solo chiamarlo e, se necessario, commentare la risposta dell'utente.

    Quando usarlo:
        Usare SEMPRE questo tool quando l'intento dell'utente è simulare un quiz d'esame, iniziarlo o continuarlo.
        Trigger: "simuliamo quiz di esame", "fammi una domanda di teoria", "domanda sul capitolo 3", "domanda sulla VNE".
        NON usare per rispondere a domande generiche sulla teoria.

    Modalità di Chiamata (Regole di Priorità):
        Il tool ha 4 modalità di chiamata che sono MUTUALMENTE ESCLUSIVE.
        Scegli UNA sola modalità in base alla richiesta dell'utente.

        1. Modalità DOMANDA CASUALE - SIMULAZIONE D'ESAME (Caso d'uso principale)
           - Quando: L'utente vuole ripassare la teoria, simulare l'esame, oppure una domanda casuale.
           - Azione: Chiama il tool senza fornire nessun parametro.
           - Esempio: ()

        2. Modalità DOMANDA CASUALE PER CAPITOLO
           - Quando: L'utente vuole una domanda casuale da un capitolo specifico.
           - Azione: Chiama il tool specificando SOLO il parametro `capitolo`.
           - Esempio: (capitolo=1)

        3. Modalità DOMANDA SPECIFICA
           - Quando: L'utente chiede una domanda esatta specificando il capitolo e il numero (es. "la domanda 5 del capitolo 2").
           - Azione: Chiama il tool specificando SIA `capitolo` CHE `domanda`.
           - Esempio: (capitolo=2, domanda=5)

        4. Modalità RICERCA PER ARGOMENTO O PER TESTO
           - Quando: L'utente vuole una domanda su un argomento specifico (es. "una domanda sulla quota di apertura") oppure conosce il testo della domanda.
           - Azione: Chiama il tool specificando SOLO il parametro `testo`. Lascia gli altri vuoti.
           - Esempio: (testo="quota di apertura")

    Output (Dati ricevuti dall'agente):
        Riceverai un dizionario JSON con i dati della domanda mostrata all'utente.
        Usa 'risposta_corretta' per il tuo workflow logico.
        - 'capitolo': (int) Numero del capitolo.
        - 'capitolo_nome': (str) Nome del capitolo.
        - 'numero': (int) Numero della domanda.
        - 'testo': (str) Testo della domanda.
        - 'opzioni': (list) Lista di opzioni, ciascuna con 'id' e 'testo'.
        - 'risposta_corretta': (str) La lettera (es. 'C') che devi usare per verificare la risposta dell'utente.
    """
    quiz = _get_quiz_service()
    if quiz is None:
        return None

    # Normalize parameters
    capitolo = _normalize_optional_param(capitolo)
    domanda = _normalize_optional_param(domanda)
    testo = _normalize_optional_param(testo)

    try:
        # Mode 4: Search by text
        if testo is not None:
            return _search_by_text(quiz, testo)

        # Mode 2/3: Chapter-based queries
        if capitolo is not None:
            return _get_by_chapter(quiz, capitolo, domanda)

        # Mode 1: Random question from entire database
        return _get_random_question(quiz)

    except Exception as e:
        logger.error(
            f"TOOL: domanda_teoria - Errore estrazione domanda: {e}\n"
            f"Parametri: capitolo={capitolo}, domanda={domanda}, testo={testo}"
        )
        return None


def _search_by_text(quiz: QuizMongoDBService, testo: str) -> dict:
    """Search questions by text content."""
    logger.info(f"TOOL: domanda_teoria - Ricerca per testo: {testo}")
    questions = quiz.search_questions_by_text(testo)

    if not questions:
        logger.warning(f"TOOL: domanda_teoria - Nessuna domanda trovata per: {testo}")
        return _make_error(f"Nessuna domanda trovata per il testo '{testo}'. Prova con parole diverse.")

    question = questions[0]
    logger.info(f"TOOL: domanda_teoria - Domanda trovata per '{testo}': {question}")
    return question


def _get_by_chapter(quiz: QuizMongoDBService, capitolo: int, domanda: Optional[int]) -> dict:
    """Get question by chapter, optionally by specific question number."""
    if capitolo < MIN_CHAPTER or capitolo > MAX_CHAPTER:
        logger.warning(f"TOOL: domanda_teoria - Capitolo {capitolo} non valido")
        return _make_error(f"capitolo numero {capitolo} inesistente, riprovare con un capitolo da 1 a 10")

    # Mode 3: Specific question from chapter
    if domanda is not None:
        logger.info(f"TOOL: domanda_teoria - Capitolo={capitolo}, domanda={domanda}")
        question = quiz.get_question_by_capitolo_and_number(capitolo=capitolo, numero=domanda)

        if not question:
            logger.warning(f"TOOL: domanda_teoria - Domanda {domanda} non trovata nel capitolo {capitolo}")
            return _make_error(f"Domanda numero {domanda} non trovata nel capitolo {capitolo}.")

        logger.info(f"TOOL: domanda_teoria - Domanda estratta: {question}")
        return question

    # Mode 2: Random question from chapter
    logger.info(f"TOOL: domanda_teoria - Capitolo={capitolo}, domanda casuale")
    question = quiz.get_random_question_by_field(field="capitolo", value=capitolo)

    if not question:
        logger.warning(f"TOOL: domanda_teoria - Nessuna domanda nel capitolo {capitolo}")
        return _make_error(f"Nessuna domanda trovata per il capitolo {capitolo}. per favore riprova tra poco")

    logger.info(f"TOOL: domanda_teoria - Domanda casuale estratta: {question}")
    return question


def _get_random_question(quiz: QuizMongoDBService) -> dict:
    """Get random question from entire database."""
    logger.info("TOOL: domanda_teoria - Estraggo domanda casuale dal DB")
    question = quiz.get_random_question()

    if not question:
        logger.warning("TOOL: domanda_teoria - Nessuna domanda nel database")
        return _make_error("Nessuna domanda trovata nel database")

    logger.info(f"TOOL: domanda_teoria - Domanda casuale: {question}")
    return question
