from typing import Dict
import datetime
import re

def format_user_metadata(user_metadata: Dict) -> str:
    """
    Formatta i metadata dell'utente in una stringa leggibile.

    :param user_metadata: Dizionario contenente i metadata dell'utente.
    :return: Stringa formattata con le informazioni dell'utente.
    """
    if not user_metadata:
        date = datetime.datetime.now().strftime("%Y-%m-%d")
        if date:
            formatted_data = f"\nOggi è il {date}\n"
    
        return formatted_data
    
    formatted_data = "I dati che l’utente ti ha fornito su di sè sono:\n"
    
    # Date of Birth
    date_of_birth = user_metadata.get("date_of_birth")
    if date_of_birth:
        formatted_data += f"Data di Nascita: {date_of_birth}\n"
    
    # Jumps
    jumps = user_metadata.get("jumps")
    if jumps:
        formatted_data += f"Numero di salti: {jumps}\n"
    
    # Preferred Dropzone
    preferred_dropzone = user_metadata.get("preferred_dropzone")
    if preferred_dropzone:
        formatted_data += f"Dropzone preferita: {preferred_dropzone}\n"
    
    # Qualifications
    qualifications = user_metadata.get("qualifications")
    qualifications_mapping = {
        "1allievo": "qualifica: Allievo",
        "2licenziato": "qualifica: possiede la licenza di paracadutismo",
        "3DL": "qualifica: possiede la licenza di paracadutismo e la qualifica Direttore di lancio",
        "4IP": "qualifica: possiede la licenza di paracadutismo, la qualifica Direttore di lancio e Istruttore"
    }
    qualifica_formattata = qualifications_mapping.get(qualifications, "")
    if qualifica_formattata:
        formatted_data += f"{qualifica_formattata}\n"
    
    # Name
    name = user_metadata.get("name")
    if name:
        formatted_data += f"Nome: {name}\n"
    
    # Surname
    surname = user_metadata.get("surname")
    if surname:
        formatted_data += f"Cognome: {surname}\n"
    
    # Sex
    sex = user_metadata.get("sex")
    if sex:
        formatted_data += f"Sesso: {sex}\n"

    date = datetime.datetime.now().strftime("%Y-%m-%d")
    if date:
        formatted_data += f"\nOggi è il {date}\n"
    
    return formatted_data

# controlli per autenticazione user_id
def validate_user_id(user_id):
    # Regex per auth0
    auth0_pattern = r'^auth0\|[0-9a-fA-F]{24}$'

    # Regex per google-oauth2
    google_pattern = r'^google-oauth2\|[0-9]{15,25}$'

    # Controlla se il campo corrisponde a uno dei due pattern
    if re.match(auth0_pattern, user_id):
        return True
    elif re.match(google_pattern, user_id):
        return True
    else:
        return False