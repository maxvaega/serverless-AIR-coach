import random
import json
from typing import Optional
from langchain_core.tools import tool
from langchain_core.messages import ToolMessage
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
                        logger.warning(f"TOOL - Serialization failed - not a valid JSON: {content}")
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
# Mock database of questions (struttura piatta per facilità di lettura da parte dell'LLM)
mock_db = [
    {
        "capitolo": 1,
        "capitolo_nome": CHAPTER_NAMES[1],
        "numero": 1,
        "testo": "UNA ZONA CON PRESSIONE ATMOSFERICA DI 1030 HPA È CARATTERIZZATA DA:",
        "opzioni": [
            {"id": "A", "testo": "Maltempo"},
            {"id": "B", "testo": "Vento forte"},
            {"id": "C", "testo": "Bel tempo"},
            {"id": "D", "testo": "Temporali"}
        ],
        "risposta_corretta": "C",
    },
    {
        "capitolo": 1,
        "capitolo_nome": CHAPTER_NAMES[1],
        "numero": 2,
        "testo": "UNA ZONA DI BASSA PRESSIONE È CARATTERIZZATA DA:",
        "opzioni": [
            {"id": "A", "testo": "In generale cattive condizioni meteorologiche"},
            {"id": "B", "testo": "Nubi basse ed elevata pressione"},
            {"id": "C", "testo": "In generale buone condizioni meteorologiche"},
            {"id": "D", "testo": "Vento che soffia in senso orario"}
        ],
        "risposta_corretta": "A",
    },
    {
        "capitolo": 2,
        "capitolo_nome": CHAPTER_NAMES[2],
        "numero": 13,
        "testo": "QUAL È LA VELOCITÀ TERMINALE MEDIA, A 2.000 M DI QUOTA, DI UN PARACADUTISTA IN BOX POSITION (PIATTO), USCITO DALL'AEREO A 4000 M?",
        "opzioni": [
            {"id": "A", "testo": "Circa 30 m/s"},
            {"id": "B", "testo": "Circa 50 m/s"},
            {"id": "C", "testo": "Circa 75 m/s"},
            {"id": "D", "testo": "Circa 100 m/s"}
        ],
        "risposta_corretta": "B",
    },
    {
        "capitolo": 2,
        "capitolo_nome": CHAPTER_NAMES[2],
        "numero": 14,
        "testo": "UNA POSIZIONE \"INCASSATA\" PERMETTE AD UN PARACADUTISTA DI DIMINUIRE LA PROPRIA VELOCITÀ IN CADUTA LIBERA, PERCHÉ:",
        "opzioni": [
            {"id": "A", "testo": "Aumenta la resistenza aerodinamica, modificando la forma e la superficie del proprio corpo"},
            {"id": "B", "testo": "Il suo baricentro è posto più in alto"},
            {"id": "C", "testo": "La forza di gravità aumenta"},
            {"id": "D", "testo": "Spinge sull'aria con maggior forza"}
        ],
        "risposta_corretta": "A",
    },
]

@tool(return_direct=True)
def test_licenza(capitolo: Optional[int] = None) -> dict:
    """
    Scopo:
        Recupera una domanda d'esame casuale per i capitoli di teoria della licenza di paracadutismo.

    Quando usarlo:
        Usare SEMPRE questo tool quando l'utente chiede di fare/simulare/ripassare il quiz teorico
        o chiede domande a scelta multipla su uno o più capitoli.

    Input:
        capitolo: intero opzionale (1-10).
                  - Se valorizzato: restituisce una domanda casuale dal capitolo indicato.
                  - Se None: restituisce una domanda casuale da tutto il DB mockato.

    Output (schema atteso):
        Un singolo dict con i seguenti campi (struttura piatta):
        - 'capitolo': numero del capitolo
        - 'capitolo_nome': nome del capitolo
        - 'numero': numero della domanda
        - 'testo': testo della domanda
        - 'opzioni': lista di dict con i campi 'id' e 'testo' per ogni opzione
        - 'risposta_corretta': lettera dell'opzione corretta

    Note:
        - Il modello NON deve modificare testo o opzioni. Deve limitarsi a presentare fedelmente in linguaggio naturale i contenuti restituiti.
    """

    #   - Nota: poiché il DB mock contiene solo i capitoli 1 e 2, se viene richiesto
    #     un capitolo > 2, il tool utilizza il capitolo 2.
    # Raggruppa le domande per capitolo nel mock DB piatto
    chapters: dict[int, list[dict]] = {}
    for item in mock_db:
        chapter_num = int(item["capitolo"])  # già int
        if chapter_num not in chapters:
            chapters[chapter_num] = []
        chapters[chapter_num].append(item)

    if capitolo is not None:
        # Normalizza il capitolo richiesto: se >2 (DB mock), usa 2
        effective_chapter = 2 if capitolo > 2 else capitolo
        # Se per qualche motivo il capitolo non esiste nel mock, fallback all'intero DB
        if effective_chapter in chapters and chapters[effective_chapter]:
            random_question = random.choice(chapters[effective_chapter])
        else:
            random_question = random.choice(mock_db)
    else:
        # Da tutto il DB mockato
        random_question = random.choice(mock_db)

    # Restituisce l'intera domanda in formato piatto
    logger.info(
        "TOOL: Test licenza - Capitolo richiesto=%s, usato=%s, Domanda n.=%s",
        str(capitolo),
        str(random_question.get("capitolo")),
        str(random_question.get("numero")),
    )
    return random_question

# @tool
# def reperire_documentazione_air_coach(query: str) -> str:
#     """
#     Questo tool serve a rispondere a domande di carattere generale sull'attività di AIR Coach,
#     sui corsi, sul paracadutismo e argomenti correlati.
#     Utilizza la documentazione ufficiale per fornire risposte accurate.
#     Da usare per tutte le domande che non riguardano la simulazione d'esame.
#     """
#     # This tool wraps the existing RAG functionality.
#     # The 'query' parameter is implicitly used by the chain, but the main purpose
#     # is to retrieve the context documents.
#     return get_combined_docs()
