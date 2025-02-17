from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import AIMessageChunk, HumanMessage, SystemMessage
from .logging_config import logger
import datetime
from .env import *
import json
import boto3

s3_client = boto3.client('s3', aws_access_key_id=AWS_ACCESS_KEY_ID, aws_secret_access_key=AWS_SECRET_ACCESS_KEY)
_docs_cache = {
    "content": None,
    "timestamp": None 
}

def fetch_docs_from_s3():
    """
    Downloads Markdown files from the S3 bucket and combines them into a single string.
    """
    try:
        logger.info("Fetching Bucket S3...")
        objects = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix='docs/')
        docs_content = []

        # Itera sugli oggetti nel bucket
        for obj in objects.get('Contents', []):
            if obj['Key'].endswith('.md'):  # Filtra solo i file Markdown
                response = s3_client.get_object(Bucket=BUCKET_NAME, Key=obj['Key'])
                file_content = response['Body'].read().decode('utf-8')
                docs_content.append(file_content)

        # Combina tutti i file in un'unica stringa
        combined_docs = "\n\n".join(docs_content)
        logger.info(f"Found {len(docs_content)} file Markdown from S3.")
        return combined_docs

    except Exception as e:
        logger.error(f"Error while downloading files from S3: {e}")
        return ""

def get_combined_docs():
    """
    Returns the combined content of the Markdown files, using the cache if valid.
    If the cache is expired, reloads the data from S3.
    """
    global _docs_cache
    now = datetime.datetime.utcnow()

    # Controlla se la cache è valida
    if _docs_cache["content"] is None or _docs_cache["timestamp"] is None:
        logger.info("Cache non presente, caricamento iniziale...")
    elif (now - _docs_cache["timestamp"]) > datetime.timedelta(seconds=CACHE_TTL):
        logger.info("Cache scaduta, ricaricamento dei dati da S3...")
    else:
        logger.info("Cache valida, restituzione dei dati dalla cache.")
        return _docs_cache["content"]

    # Ricarica i dati da S3 e aggiorna la cache
    _docs_cache["content"] = fetch_docs_from_s3()
    _docs_cache["timestamp"] = now
    return _docs_cache["content"]

# Load Documents from S3
combined_docs = get_combined_docs()

# Initialize system prompt
system_prompt = f"""
Sei AIR Coach, un esperto di paracadutismo Italiano. Rispondi a domande sul paracadutismo con risposte chiare ed esaurienti.

    # Istruzioni Chiave
    -   **Ambito delle risposte**: Rispondi solo a domande relative al paracadutismo. 
    -   Se la risposta dipende da informazioni personali come il numero di salti o il possesso della licenza, chiedi all'utente di fornire tali dettagli.
    -   **Sicurezza**: La sicurezza è sempre la priorità su tutto. Invita sempre l'utente a riflettere e chiedere agli istruttori prima di provare cose che potrebbero essere pericolose. 
    -   Se, sulla base delle informazioni che hai, valuti che l'utente sta chiedendo di qualcosa che non dovrebbe fare, spiegalo in modo chiaro e deciso.
    -   Incoraggia sempre a ripassare le procedure di sicurezza e proponiti per aiutare l'utente a farlo.
    -   Ricorda di invitare l'utente a rivolgersi sempre a un istruttore di persona quando necessario.

    # Stile e Tono
    -   **Chiarezza e Impostazione**: Usa un linguaggio chiaro e descrivi con completezza gli argomenti chiesti. Motiva e rassicura l'utente bilanciando la sicurezza con l'approccio positivo allo sport.
    -   Concentrati sulla domanda dell'utente e cerca di non generare risposte più lunghe di 1200 caratteri circa.

    # Utilizzo del contesto:
    -   Seleziona dal contesto fornito di seguito le informazioni utili e utilizzale per rispondere alle domande.
    -   Non utilizzare mai le competenze generali del modello o fare inferenze al di fuori del contesto fornito
    -   Se non conosci la risposta, di semplicemente che non la conosci e suggerisci di riformulare la richiesta o chiedere a un istruttore
    -   Il contesto è organizzato per capitoli, identificabili da uno o più caratteri # seguiti dal titolo del capitolo.
    
    # Formato
    -   Utilizza elenchi puntati per elencare i passaggi delle procedure
    -   Quando descrivi una procedura, non riassumere le azioni da fare e mantienile sempre complete. non aggregare più procedure tra loro.
    -   Rispondi alle domande in modo esaustivo includendo eventuali punti di attenzione utili per la sicurezza
    -   Ad eccezione di istruzioni utili per la sicurezza, rimuovi le informazioni non necessarie a quanto richiesto dall'utente
    -   Se la domanda è vaga o ambigua, chiedi all'utente di fornire ulteriori dettagli per poter rispondere in modo più preciso.

    # Citazioni dal contesto:
    -   Quando componi la risposta riporta alla fine del blocco di testo le citazioni dei titoli che hai usato, racchiusi tra parentesi quadre: [titolo]
    -   il contesto usa questo formato per i titoli:
            ## Titolo del contesto
            contenuto del contesto
            altro contenuto del contesto

    -   Ecco un esempio di contenuto del contesto
            ## Introduzione al paracadutismo
            Testo di introduzione al paracadutismo 
            Altro testo di introduzione al paracadutismo 
            (...)

    -   Ecco un esempio di citazione dal contesto
            Testo di introduzione al paracadutismo 
            Altro testo di introduzione al paracadutismo
            (...)
            [Introduzione al paracadutismo]

    -   Utilizza i nomi dei capitoli corrispondenti al contesto che hai utilizzato
    -   Non riportare citazioni di capitoli che non riguardano quello che hai scritto
        
    Contesto: 
    {combined_docs}
"""

# Define LLM Model
model = "gemini-2.0-flash"
llm = ChatGoogleGenerativeAI(
    model=model,
    temperature=1,
)

def ask(query, user_id, chat_history=None, stream=False):
    """
    Processes a user query and returns a response, optionally streaming the response.

    This function uses a combination of retrieval and chain mechanisms to process the query
    and generates a response. If chat history is provided, it extends the messages with the
    chat history and appends the new query. The function supports both synchronous and
    asynchronous streaming of responses. In streaming mode, it yields chunks of data and
    inserts the final response into a MongoDB collection.

    :param query: The user query to process.
    :param user_id: The ID of the user making the query.
    :param chat_history: Optional; A list of previous chat messages to include in the context.
    :param stream: Optional; If True, streams the response asynchronously.
    :return: The response to the query, either as a single result or a generator for streaming.
    """
    messages = [SystemMessage(system_prompt)]

    if chat_history:
        messages = messages.append(chat_history)

    messages.append(HumanMessage(query))

    # Create a custom prompt template that includes the system prompt
    if not stream:
        return llm.invoke(messages)
    else:
        from .database import insert_data
        response_chunks = []

        # Stream the response
        async def stream_response():
            for event in llm.stream(input=messages):
                try:
                    # Catch events
                    content = event.content
                    response_chunks.append(content)
                    data_dict = {"data": content}
                    data_json = json.dumps(data_dict)
                    yield f"data: {data_json}\n\n"

                except Exception as e:
                    logger.error(f"An error occurred while streaming the events: {e}")

            # Insert the data into the MongoDB collection
            response = "".join(response_chunks)

            # Insert the data into the MongoDB collection
            try:
                data = {
                    "human": query,
                    "system": response,
                    "userId": user_id,
                    "llm": model,
                    "timestamp" : datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                insert_data(DATABASE_NAME, COLLECTION_NAME, data)
                logger.info(f"Data inserted into the collection: {COLLECTION_NAME}")
            except Exception as e:
                logger.error(f"An error occurred while inserting the data into the collection: {e}")

        return stream_response()

