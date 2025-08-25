import random
import json
from typing import Optional
# from winreg import QueryInfoKey
from langchain_core.tools import tool
from langchain_core.messages import ToolMessage

from src.services.database.database_quiz_service import QuizMongoDBService
from .logging_config import logger

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
@tool(return_direct=True)
def domanda_teoria(capitolo: Optional[int] = None, domanda: Optional[int] = None, testo: Optional[str] = None) -> dict:
    """
    Scopo:
        Recupera una domanda d'esame per la simulazione dell'esame di teoria della licenza di paracadutismo.

    Quando usarlo:
        Usare SEMPRE questo tool quando l'utente chiede di fare/simulare/ripassare il quiz teorico
        o chiede domande a scelta multipla su uno o più capitoli.

    Input:
        capitolo: intero opzionale (1-10).
            - Se valorizzato: restituisce una domanda dal capitolo indicato.
            - Se vuoto: restituisce una domanda da tutto il database.
        
        domanda: intero opzionale. Valorizzare solo se si valorizza anche capitolo.
            - Se valorizzato: restituisce la domanda con il numero specificato, dal capitolo specificato.
            - Se domanda è vuoto (e capitolo è valorizzato): restituisce una domanda casuale dal capitolo specificato.
            - Se domanda è vuoto (e capitolo è vuoto): restituisce una domanda casuale da tutto il database.

        testo: stringa opzionale. Utilizzare solo se si desidera filtrare le domande in base al testo. Se si utilizza testo, lasciare vuoti capitolo e domanda.


    Output (schema atteso):
        Un singolo dict con i seguenti campi (struttura piatta):
        - 'capitolo': numero del capitolo
        - 'capitolo_nome': nome del capitolo
        - 'numero': numero della domanda
        - 'testo': testo della domanda
        - 'opzioni': lista di dict con i campi 'id' e 'testo' per ogni opzione
        - 'risposta_corretta': lettera dell'opzione corretta
"""

    try:
        quiz = QuizMongoDBService()
    except Exception as e:
        logger.error(f"TOOL: domanda_teoria - Errore durante l'inizializzazione del servizio quiz: {e}")
        return

    # logger.info(f"capitolo: {capitolo}, domanda: {domanda}, testo: {testo}")

    try:
        if testo is not None:
            # Filtra le domande in base al testo
            logger.info(f"TOOL: domanda_teoria - Ricerca per testo: {testo} ...")
            
            # Usa il metodo specifico per cercare domande per testo
            questions = quiz.search_questions_by_text(testo)
            
            if questions and len(questions) > 0:
                # Restituisci la prima domanda trovata
                question = questions[0]
                logger.info(f"TOOL: domanda_teoria - Domanda trovata per testo '{testo}': \n{question}")
                return question
            else:
                logger.warning(f"TOOL: domanda_teoria - Nessuna domanda trovata per il testo: {testo}")
                return {"error": f"Domanda teoria: Nessuna domanda trovata per il testo '{testo}'. Prova con parole diverse o più specifiche."}

        if capitolo is not None:

            if capitolo > 10 or capitolo < 1:
                logger.warning(f"TOOL: domanda_teoria - capitolo numero {capitolo} inesistente, impossibile procedere")
                return {"error": f"Domanda teoria: capitolo numero {capitolo} inesistente, riprovare con un capitolo da 1 a 10"}

            if domanda is not None:
                # Cerca una domanda specifica da un capitolo specifico
                logger.info(f"TOOL: domanda_teoria - Capitolo richiesto={capitolo}, estraggo domanda richiesta={domanda} ...")
                
                # Usa il metodo specifico per ottenere la domanda
                question = quiz.get_question_by_capitolo_and_number(capitolo=capitolo, numero=domanda)
                
                if question:
                    logger.info(f"TOOL: domanda_teoria - Domanda specifica estratta: \n{question}")
                    return question
                else:
                    logger.warning(f"TOOL: domanda_teoria - Nessuna domanda trovata per capitolo {capitolo}, numero {domanda}")
                    return {"error": f"Domanda teoria: Domanda numero {domanda} non trovata nel capitolo {capitolo}."}
            
            else:
                # Se viene specificato il capitolo ma non la domanda, restituisce una domanda casuale dal capitolo specificato
                logger.info(f"TOOL: domanda_teoria - Capitolo richiesto={capitolo}, estraggo domanda casuale...")
                question = quiz.get_random_question_by_field(field="capitolo", value=capitolo)
                if question:
                    logger.info(f"TOOL: domanda_teoria - Domanda casuale estratta: \n{question}")
                    return question
                else:
                    logger.warning(f"TOOL: domanda_teoria - Nessuna domanda trovata per il capitolo {capitolo}")
                    return {"error": f"Domanda teoria: Nessuna domanda trovata per il capitolo {capitolo}. per favore riprova tra poco"}

        else:
            # Se il capitolo non è specificato, restituisce una domanda casuale da tutto il DB
            logger.info("TOOL: domanda_teoria - Estraggo domanda casuale da tutto il DB...")
            question = quiz.get_random_question()
            if question:
                logger.info(f"TOOL: domanda_teoria - Domanda casuale estratta: \n{question}")
                return question
            else:
                logger.warning("TOOL: domanda_teoria - Nessuna domanda trovata nel database")
                return {"error": "Domanda teoria: Nessuna domanda trovata nel database"}
        
    except Exception as e:
        logger.error(f"TOOL: domanda_teoria - Errore durante l'estrazione della domanda a db: {e} \nParametri= capitolo: {capitolo}\ndomanda: {domanda}\ntesto: {testo}")
        return
    