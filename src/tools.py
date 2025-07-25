from typing import Optional
import logging
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# Search Tool
@tool
def domanda_quiz_teoria(numero_domanda: Optional[int] = None, numero_capitolo: Optional[int] = None) -> str:
    """Cerca una domanda per il quiz di teoria.
    
    Input: 
    - numero_domanda (int): Il numero della domanda da cercare.
    - numero_capitolo (int): Il numero del capitolo da cui cercare la domanda
    
    Output: Un dizionario con i dettagli della domanda, inclusi testo, opzioni e risposta corretta.
    """

    logger.info(f"Avviato tool domanda_quiz_teoria: numero_domanda={numero_domanda}, numero_capitolo={numero_capitolo}")

    try:
        # Simulate a database call results
        simulated_database = {
            "_id": {
                "$oid": "6877bd505a3058d299a4b0ea"
            },
            "capitolo": {
                "numero": 1,
                "nome": "Meteorologia applicata al paracadutismo"
            },
            "domanda": {
                "numero": 12,
                "testo": "SOPRA UN TERRENO RISCALDATO PER IRRAGGIAMENTO SOLARE, GENERALMENTE SI TROVA:",
                "opzioni": [
                {
                    "id": "A",
                    "testo": "Turbolenza causata dall'aria discendente"
                },
                {
                    "id": "B",
                    "testo": "Vento estivo caldo e debole"
                },
                {
                    "id": "C",
                    "testo": "Turbolenza causata dall'aria ascendente"
                },
                {
                    "id": "D",
                    "testo": "Aria calma"
                }
                ],
                "risposta_corretta": "C"
            }
        }

        return simulated_database
            
    except Exception as e:
        logger.error(f"Errore ricerca domanda: {str(e)}")
        return f"Errore ricerca domanda: {str(e)}"

# Dictionary of available tools
AVAILABLE_TOOLS = {
    "domanda_quiz_teoria": domanda_quiz_teoria
}