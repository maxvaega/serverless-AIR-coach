from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import AIMessageChunk, HumanMessage, SystemMessage
from .logging_config import logger
import datetime
import os
from dotenv import load_dotenv
import json

load_dotenv()

#Load api keys
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

# Set Other Environment Variables
ENV = os.getenv("ENV")

# Setup MongoDB environment
DATABASE_NAME = os.getenv("DATABASE_NAME")
COLLECTION_NAME = os.getenv("COLLECTION_NAME")

# Read all documents from docs directory
docs_content = []
docs_path = os.path.join(os.path.dirname(__file__), 'docs')

try:
    if not os.path.exists(docs_path):
        raise FileNotFoundError(f"Directory not found: {docs_path}")
        
    for doc_file in os.listdir(docs_path):
        if doc_file.endswith('.md'):  # Only process markdown files
            file_path = os.path.join(docs_path, doc_file)
            try:
                with open(file_path, "r", encoding='utf-8') as file:
                    docs_content.append(file.read())
            except Exception as e:
                logger.error(f"Error reading file {doc_file}: {str(e)}")
                
    # Combine all documents
    combined_docs = "\n\n".join(docs_content)
    print(f"Successfully loaded {len(docs_content)} documents")
    
except Exception as e:
    logger.error(f"Error processing documents: {str(e)}")
    combined_docs = ""

# Initialize system prompt
system_prompt = f"""
Sei AIstruttore, un esperto di paracadutismo Italiano. Rispondi a domande sul paracadutismo con risposte chiare ed esaurienti.

    # Istruzioni Chiave
    -   **Ambito delle risposte**: Rispondi solo a domande relative al paracadutismo. Se la risposta dipende da informazioni personali come il numero di salti o il possesso della licenza, chiedi all'utente di fornire tali dettagli.
    -   **Sicurezza**: La sicurezza è sempre la priorità su tutto. Se l'utente chiede di qualcosa che non dovrebbe fare, spiegalo chiaramente.

    # Stile e Tono
    -   **Chiarezza e completezza**: Usa un linguaggio chiaro e fornisci tutti i dettagli di cui disponi.
    -   **Tono rassicurante e stimolante**: Motiva e rassicura l'utente bilanciando la sicurezza con l'approccio divertente e positivo allo sport.

    # Formato
    Le risposte devono essere in linguaggio naturale, strutturate in paragrafi chiari e con eventuali elenchi puntati per procedure specifiche.

    # Note

    -   Non utilizzare mai le competenze generali del modello o fare inferenze al di fuori del contesto fornito
    -   Incoraggia sempre a ripassare le procedure di sicurezza e proponiti per aiutare l'utente a farlo.
    -   Ricorda di invitare l'utente a rivolgersi sempre a un istruttore di persona quando necessario.

    Utilizza il contesto fornito di seguito per rispondere alla domanda.
    Se non conosci la risposta, di semplicemente che non la conosci e suggerisci di chiedere a un istruttore 
    Contesto: 
    {combined_docs}
"""

model="gemini-2.0-flash"
llm = ChatGoogleGenerativeAI(
    model=model,
    temperature=0,
)

def serialize_aimessagechunk(chunk):
    """
    Custom serializer for AIMessageChunk objects.
    Convert the AIMessageChunk object to a serializable format.
    """
    if isinstance(chunk, AIMessageChunk):
        return chunk.content
    else:
        raise TypeError(
            f"Object of type {type(chunk).__name__} is not correctly formatted for serialization"
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

