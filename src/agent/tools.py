"""
Tool per il quiz di teoria della licenza di paracadutismo.

Questo modulo contiene tool separati per le diverse modalità di recupero delle domande:
- domanda_casuale_esame: domanda casuale per simulazione esame
- domanda_casuale_capitolo: domanda casuale da un capitolo specifico
- domanda_specifica: domanda specifica per capitolo e numero
- ricerca_domanda: ricerca domande per argomento o testo

Ogni tool restituisce lo stesso formato di output per il frontend.
"""

import json
from typing import Optional
from langchain_core.tools import tool
from langchain_core.messages import ToolMessage

import logging

logger = logging.getLogger("uvicorn")


def _serialize_tool_output(tool_output) -> dict:
    """
    Serializza l'output del tool in un formato JSON-compatibile.
    """
    try:
        # Se è un ToolMessage, estrai il contenuto
        if isinstance(tool_output, ToolMessage):
            content = tool_output.content
            # Se il content è una stringa JSON, prova a deserializzarla in oggetto
            if isinstance(content, str):
                stripped = content.strip()
                if stripped.startswith("{") or stripped.startswith("["):
                    try:
                        content = json.loads(content)
                    except Exception:
                        # Se non è JSON valido, lascia la stringa così com'è
                        logger.warning(f"TOOL - Serialization failed - not a valid JSON (or is it already a JSON?)")
                        pass
            return {
                "content": content,
                "tool_call_id": getattr(tool_output, 'tool_call_id', None)
            }
        # Se è già un dict o altro tipo serializzabile
        elif isinstance(tool_output, (dict, list, int, float, bool)):
            return tool_output
        elif isinstance(tool_output, str):
            stripped = tool_output.strip()
            if stripped.startswith("{") or stripped.startswith("["):
                try:
                    return json.loads(tool_output)
                except Exception:
                    return {"content": tool_output}
            return {"content": tool_output}
        # Per altri tipi, converti in stringa
        else:
            return {"content": str(tool_output)}
    except Exception as e:
        logger.error(f"Errore nella serializzazione del tool output: {e}")
        return {"content": str(tool_output), "error": "serialization_failed"}


# Nomi ufficiali dei capitoli disponibili
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


def _get_quiz_service():
    """Helper per ottenere un'istanza del servizio quiz.

    L'import è lazy per permettere il mock nei test senza dipendenze esterne.
    """
    from src.services.database.database_quiz_service import QuizMongoDBService
    return QuizMongoDBService()


@tool(return_direct=True)
def domanda_casuale_esame() -> dict:
    """
    Recupera una domanda casuale per la simulazione dell'esame di teoria.

    Scopo:
        Estrae una domanda casuale dall'intero database delle domande d'esame
        per la licenza di paracadutismo. Ideale per simulare l'esame reale.

    Quando usarlo:
        - L'utente vuole simulare un quiz d'esame
        - L'utente chiede una domanda casuale di teoria
        - L'utente vuole ripassare la teoria senza specificare un argomento
        - Trigger: "simuliamo quiz di esame", "fammi una domanda di teoria",
          "domanda casuale", "iniziamo il quiz"

    Parametri:
        Nessuno - questo tool non richiede parametri.

    Output:
        Dizionario JSON con i dati della domanda:
        - 'capitolo': (int) Numero del capitolo
        - 'capitolo_nome': (str) Nome del capitolo
        - 'numero': (int) Numero della domanda
        - 'testo': (str) Testo della domanda
        - 'opzioni': (list) Lista di opzioni con 'id' e 'testo'
        - 'risposta_corretta': (str) Lettera della risposta corretta (es. 'C')
    """
    try:
        quiz = _get_quiz_service()
    except Exception as e:
        logger.error(f"TOOL: domanda_casuale_esame - Errore inizializzazione servizio: {e}")
        return {"error": "Errore di connessione al database. Riprova tra poco."}

    try:
        logger.info("TOOL: domanda_casuale_esame - Estraggo domanda casuale da tutto il DB...")
        question = quiz.get_random_question()

        if question:
            logger.info(f"TOOL: domanda_casuale_esame - Domanda estratta: cap.{question.get('capitolo')} n.{question.get('numero')}")
            return question
        else:
            logger.warning("TOOL: domanda_casuale_esame - Nessuna domanda trovata nel database")
            return {"error": "Nessuna domanda trovata nel database. Riprova tra poco."}

    except Exception as e:
        logger.error(f"TOOL: domanda_casuale_esame - Errore durante l'estrazione: {e}")
        return {"error": "Errore durante il recupero della domanda. Riprova tra poco."}


@tool(return_direct=True)
def domanda_casuale_capitolo(capitolo: int) -> dict:
    """
    Recupera una domanda casuale da un capitolo specifico.

    Scopo:
        Estrae una domanda casuale dal capitolo specificato, permettendo
        all'utente di concentrarsi su un argomento particolare.

    Quando usarlo:
        - L'utente vuole una domanda da un capitolo specifico
        - L'utente vuole ripassare un argomento particolare
        - Trigger: "domanda sul capitolo 3", "fammi una domanda di meteorologia",
          "quiz sul capitolo delle emergenze"

    Parametri:
        capitolo (int): Numero del capitolo da 1 a 10.
            Capitoli disponibili:
            1 - Meteorologia applicata al paracadutismo
            2 - Aerodinamica applicata al corpo in caduta libera
            3 - Tecnologia degli equipaggiamenti e strumenti in uso
            4 - Tecnica di direzione di lancio
            5 - Tecnica di utilizzo dei paracadute plananti
            6 - Elementi e procedure generali di sicurezza
            7 - Elementi e procedure di sicurezza nel lavoro relativo in caduta libera
            8 - Elementi e procedure di sicurezza nel volo in formazione con paracadute planante
            9 - Procedure in situazioni di emergenza
            10 - Normativa aeronautica attinente il paracadutismo

    Output:
        Dizionario JSON con i dati della domanda:
        - 'capitolo': (int) Numero del capitolo
        - 'capitolo_nome': (str) Nome del capitolo
        - 'numero': (int) Numero della domanda
        - 'testo': (str) Testo della domanda
        - 'opzioni': (list) Lista di opzioni con 'id' e 'testo'
        - 'risposta_corretta': (str) Lettera della risposta corretta (es. 'C')
    """
    try:
        quiz = _get_quiz_service()
    except Exception as e:
        logger.error(f"TOOL: domanda_casuale_capitolo - Errore inizializzazione servizio: {e}")
        return {"error": "Errore di connessione al database. Riprova tra poco."}

    # Validazione capitolo
    if capitolo is None or capitolo < 1 or capitolo > 10:
        logger.warning(f"TOOL: domanda_casuale_capitolo - Capitolo {capitolo} non valido")
        return {"error": f"Capitolo {capitolo} non valido. Scegli un capitolo da 1 a 10."}

    try:
        logger.info(f"TOOL: domanda_casuale_capitolo - Estraggo domanda casuale dal capitolo {capitolo}...")
        question = quiz.get_random_question_by_field(field="capitolo", value=capitolo)

        if question:
            logger.info(f"TOOL: domanda_casuale_capitolo - Domanda estratta: cap.{capitolo} n.{question.get('numero')}")
            return question
        else:
            logger.warning(f"TOOL: domanda_casuale_capitolo - Nessuna domanda trovata per capitolo {capitolo}")
            return {"error": f"Nessuna domanda trovata per il capitolo {capitolo}. Riprova tra poco."}

    except Exception as e:
        logger.error(f"TOOL: domanda_casuale_capitolo - Errore durante l'estrazione: {e}")
        return {"error": "Errore durante il recupero della domanda. Riprova tra poco."}


@tool(return_direct=True)
def domanda_specifica(capitolo: int, numero: int) -> dict:
    """
    Recupera una domanda specifica dato il capitolo e il numero.

    Scopo:
        Recupera una domanda esatta identificata dal suo capitolo e numero,
        utile quando l'utente conosce esattamente quale domanda vuole vedere.

    Quando usarlo:
        - L'utente chiede una domanda specifica per numero
        - L'utente vuole rivedere una domanda particolare
        - Trigger: "la domanda 5 del capitolo 2", "mostrami la domanda numero 10 del cap 3",
          "voglio vedere la domanda 7 del capitolo 1"

    Parametri:
        capitolo (int): Numero del capitolo da 1 a 10.
        numero (int): Numero della domanda all'interno del capitolo.

    Output:
        Dizionario JSON con i dati della domanda:
        - 'capitolo': (int) Numero del capitolo
        - 'capitolo_nome': (str) Nome del capitolo
        - 'numero': (int) Numero della domanda
        - 'testo': (str) Testo della domanda
        - 'opzioni': (list) Lista di opzioni con 'id' e 'testo'
        - 'risposta_corretta': (str) Lettera della risposta corretta (es. 'C')
    """
    try:
        quiz = _get_quiz_service()
    except Exception as e:
        logger.error(f"TOOL: domanda_specifica - Errore inizializzazione servizio: {e}")
        return {"error": "Errore di connessione al database. Riprova tra poco."}

    # Validazione capitolo
    if capitolo is None or capitolo < 1 or capitolo > 10:
        logger.warning(f"TOOL: domanda_specifica - Capitolo {capitolo} non valido")
        return {"error": f"Capitolo {capitolo} non valido. Scegli un capitolo da 1 a 10."}

    # Validazione numero domanda
    if numero is None or numero < 1:
        logger.warning(f"TOOL: domanda_specifica - Numero domanda {numero} non valido")
        return {"error": f"Numero domanda {numero} non valido. Deve essere un numero positivo."}

    try:
        logger.info(f"TOOL: domanda_specifica - Cerco domanda {numero} del capitolo {capitolo}...")
        question = quiz.get_question_by_capitolo_and_number(capitolo=capitolo, numero=numero)

        if question:
            logger.info(f"TOOL: domanda_specifica - Domanda trovata: cap.{capitolo} n.{numero}")
            return question
        else:
            logger.warning(f"TOOL: domanda_specifica - Domanda {numero} non trovata nel capitolo {capitolo}")
            return {"error": f"Domanda numero {numero} non trovata nel capitolo {capitolo}."}

    except Exception as e:
        logger.error(f"TOOL: domanda_specifica - Errore durante la ricerca: {e}")
        return {"error": "Errore durante il recupero della domanda. Riprova tra poco."}


@tool(return_direct=True)
def ricerca_domanda(testo: str) -> dict:
    """
    Cerca una domanda per argomento o testo contenuto.

    Scopo:
        Cerca nel database domande che contengono le parole chiave specificate,
        utile quando l'utente vuole esercitarsi su un argomento particolare
        o ricorda parte del testo di una domanda.

    Quando usarlo:
        - L'utente vuole una domanda su un argomento specifico
        - L'utente ricorda parte del testo della domanda
        - L'utente cerca domande su un concetto particolare
        - Trigger: "domanda sulla quota di apertura", "una domanda sulla VNE",
          "cerca domande sull'altimetro", "domanda che parla di emergenza"

    Parametri:
        testo (str): Parole chiave da cercare nel testo delle domande.
            Usa parole significative dell'argomento desiderato.
            Esempi: "quota apertura", "VNE", "altimetro", "emergenza principale"

    Output:
        Dizionario JSON con i dati della domanda trovata:
        - 'capitolo': (int) Numero del capitolo
        - 'capitolo_nome': (str) Nome del capitolo
        - 'numero': (int) Numero della domanda
        - 'testo': (str) Testo della domanda
        - 'opzioni': (list) Lista di opzioni con 'id' e 'testo'
        - 'risposta_corretta': (str) Lettera della risposta corretta (es. 'C')
    """
    try:
        quiz = _get_quiz_service()
    except Exception as e:
        logger.error(f"TOOL: ricerca_domanda - Errore inizializzazione servizio: {e}")
        return {"error": "Errore di connessione al database. Riprova tra poco."}

    # Normalizza input
    if testo is None or (isinstance(testo, str) and testo.strip() == ""):
        logger.warning("TOOL: ricerca_domanda - Testo di ricerca vuoto")
        return {"error": "Specifica un argomento o delle parole chiave per la ricerca."}

    testo = testo.strip()

    try:
        logger.info(f"TOOL: ricerca_domanda - Ricerca per testo: '{testo}'...")
        questions = quiz.search_questions_by_text(testo)

        if questions and len(questions) > 0:
            question = questions[0]
            logger.info(f"TOOL: ricerca_domanda - Trovata domanda per '{testo}': cap.{question.get('capitolo')} n.{question.get('numero')}")
            return question
        else:
            logger.warning(f"TOOL: ricerca_domanda - Nessuna domanda trovata per '{testo}'")
            return {"error": f"Nessuna domanda trovata per '{testo}'. Prova con parole diverse o più specifiche."}

    except Exception as e:
        logger.error(f"TOOL: ricerca_domanda - Errore durante la ricerca: {e}")
        return {"error": "Errore durante la ricerca. Riprova tra poco."}


# Lista di tutti i tool disponibili per export
quiz_tools = [
    domanda_casuale_esame,
    domanda_casuale_capitolo,
    domanda_specifica,
    ricerca_domanda,
]
