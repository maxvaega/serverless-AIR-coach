from langchain_pinecone import PineconeVectorStore
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains import create_retrieval_chain
from langchain_core.messages import AIMessageChunk
from .logging_config import logger
import datetime
import os
from dotenv import load_dotenv
import json

load_dotenv()

#Load api keys
PINECONE_API_KEY = os.getenv('PINECONE_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# setup the pinecone environment
PINECONE_ENVIRONMENT = os.getenv('PINECONE_ENVIRONMENT')
PINECONE_INDEX_NAME = os.getenv('PINECONE_INDEX_NAME')
PINECONE_NAMESPACE = os.getenv('PINECONE_NAMESPACE')

# Set Other Environment Variables
ENV = os.getenv("ENV")

# Setup MongoDB environment
DATABASE_NAME = os.getenv("DATABASE_NAME")
COLLECTION_NAME = os.getenv("COLLECTION_NAME")

# Initialize system prompt
system_prompt = """
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
    {context}
"""


embeddings = OpenAIEmbeddings(
    model="text-embedding-3-small"
)
vectorstore = PineconeVectorStore(index_name=PINECONE_INDEX_NAME, embedding=embeddings, namespace=PINECONE_NAMESPACE, pinecone_api_key=PINECONE_API_KEY) #, distance_strategy="DistanceStrategy.COSINE")

llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0,
)

def similar_docs(query, vectorstore, k=5):
    # Perform similarity search
    similar_docs = vectorstore.similarity_search(query, k=k)

    # Extract document details into a JSON-compatible structure
    docs_json = []
    for doc in similar_docs:
        docs_json.append({
            "id": doc.id, 
            "content": doc.page_content,         
            "metadata": doc.metadata             
        })

    # Return the JSON structure
    return json.dumps(docs_json, ensure_ascii=False, indent=2)

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

    messages = []
    # if chat_history:
    #     messages.extend(chat_history)
    # else:
    messages.append(("system", system_prompt))
    messages.append(("human", query))

    retrieval_qa_chat_prompt = ChatPromptTemplate.from_messages(messages)
    combine_docs_chain = create_stuff_documents_chain(
        llm, retrieval_qa_chat_prompt
    )

    retriever = vectorstore.as_retriever(query=query, k=4)
    chain = create_retrieval_chain(retriever, combine_docs_chain)

    # Create a custom prompt template that includes the system prompt
    if not stream:
        return chain.invoke({"input": query})
    else:
        from .database import insert_data
        response_chunks = []

        # Stream the response
        async def stream_response():
            async for event in chain.astream_events(
                {"input": query}, version="v2"
            ):
                try:
                    # Catch events
                    kind = event["event"]
                    if kind == "on_chain_end":
                        if event["name"] == "retrieve_documents":
                            chunk_ids = [document.id for document in event['data']['output']]
                            print(chunk_ids)
                    if kind == "on_chat_model_stream":
                        content = serialize_aimessagechunk(event["data"]["chunk"])
                        response_chunks.append(content)
                        if content:
                            data_dict = {"data": content}
                            data_json = json.dumps(data_dict)
                            yield f"data: {data_json}\n\n"

                except Exception as e:
                    logger.error(f"An error occurred while streaming the events: {e}")

            response = "".join(response_chunks)

            # Insert the data into the MongoDB collection
            try:
                data = {
                    "human": query,
                    "system": response,
                    "userId": user_id,
                    "chunkId" : ''.join(chunk_ids),
                    "timestamp" : datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                insert_data(DATABASE_NAME, COLLECTION_NAME, data)
                logger.info(f"Data inserted into the collection: {COLLECTION_NAME}")
            except Exception as e:
                logger.error(f"An error occurred while inserting the data into the collection: {e}")

        return stream_response()
