import random
from langchain_core.tools import tool
from .utils import get_combined_docs

# Mock database of questions
mock_db = [
    {
        "_id": {"$oid": "6877bd505a3058d299a4b0df"},
        "capitolo": {"numero": {"$numberInt": "1"}, "nome": "Meteorologia applicata al paracadutismo"},
        "domanda": {
            "numero": {"$numberInt": "1"},
            "testo": "UNA ZONA CON PRESSIONE ATMOSFERICA DI 1030 HPA È CARATTERIZZATA DA:",
            "opzioni": [
                {"id": "A", "testo": "Maltempo"},
                {"id": "B", "testo": "Vento forte"},
                {"id": "C", "testo": "Bel tempo"},
                {"id": "D", "testo": "Temporali"}
            ],
            "risposta_corretta": "C"
        }
    },
    {
        "_id": {"$oid": "6877bd505a3058d299a4b0e0"},
        "capitolo": {"numero": {"$numberInt": "1"}, "nome": "Meteorologia applicata al paracadutismo"},
        "domanda": {
            "numero": {"$numberInt": "2"},
            "testo": "UNA ZONA DI BASSA PRESSIONE È CARATTERIZZATA DA:",
            "opzioni": [
                {"id": "A", "testo": "In generale cattive condizioni meteorologiche"},
                {"id": "B", "testo": "Nubi basse ed elevata pressione"},
                {"id": "C", "testo": "In generale buone condizioni meteorologiche"},
                {"id": "D", "testo": "Vento che soffia in senso orario"}
            ],
            "risposta_corretta": "A"
        }
    },
    {
        "_id": {"$oid": "6877be6b5a3058d299a4b13f"},
        "capitolo": {"numero": {"$numberInt": "2"}, "nome": "Aerodinamica applicata al corpo in caduta libera"},
        "domanda": {
            "numero": {"$numberInt": "13"},
            "testo": "QUAL È LA VELOCITÀ TERMINALE MEDIA, A 2.000 M DI QUOTA, DI UN PARACADUTISTA IN BOX POSITION (PIATTO), USCITO DALL'AEREO A 4000 M?",
            "opzioni": [
                {"id": "A", "testo": "Circa 30 m/s"},
                {"id": "B", "testo": "Circa 50 m/s"},
                {"id": "C", "testo": "Circa 75 m/s"},
                {"id": "D", "testo": "Circa 100 m/s"}
            ],
            "risposta_corretta": "B"
        }
    },
    {
        "_id": {"$oid": "6877be6b5a3058d299a4b140"},
        "capitolo": {"numero": {"$numberInt": "2"}, "nome": "Aerodinamica applicata al corpo in caduta libera"},
        "domanda": {
            "numero": {"$numberInt": "14"},
            "testo": "UNA POSIZIONE \"INCASSATA\" PERMETTE AD UN PARACADUTISTA DI DIMINUIRE LA PROPRIA VELOCITÀ IN CADUTA LIBERA, PERCHÉ:",
            "opzioni": [
                {"id": "A", "testo": "Aumenta la resistenza aerodinamica, modificando la forma e la superficie del proprio corpo"},
                {"id": "B", "testo": "Il suo baricentro è posto più in alto"},
                {"id": "C", "testo": "La forza di gravità aumenta"},
                {"id": "D", "testo": "Spinge sull'aria con maggior forza"}
            ],
            "risposta_corretta": "A"
        }
    }
]

@tool
def test_licenza(capitoli: list[int] = None) -> dict:
    """
    Estrae delle domande per l'esame teorico della licenza di paracadutismo.
    Restituisce una domanda casuale per ognuno dei capitoli richiesti.
    Se nessun capitolo è specificato, restituisce una domanda casuale per ogni capitolo disponibile.
    """
    questions = {}

    # Group questions by chapter number
    chapters = {}
    for item in mock_db:
        chapter_num_str = item["capitolo"]["numero"]["$numberInt"]
        chapter_num = int(chapter_num_str)
        if chapter_num not in chapters:
            chapters[chapter_num] = []
        chapters[chapter_num].append(item)

    target_chapters = capitoli if capitoli else chapters.keys()

    for chapter_num in target_chapters:
        if chapter_num in chapters:
            # Select a random question from the chapter
            random_question = random.choice(chapters[chapter_num])
            questions[f"capitolo_{chapter_num}"] = random_question

    return questions

@tool
def reperire_documentazione_air_coach(query: str) -> str:
    """
    Questo tool serve a rispondere a domande di carattere generale sull'attività di AIR Coach,
    sui corsi, sul paracadutismo e argomenti correlati.
    Utilizza la documentazione ufficiale per fornire risposte accurate.
    Da usare per tutte le domande che non riguardano la simulazione d'esame.
    """
    # This tool wraps the existing RAG functionality.
    # The 'query' parameter is implicitly used by the chain, but the main purpose
    # is to retrieve the context documents.
    return get_combined_docs()
