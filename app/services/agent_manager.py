import logging
from typing import Dict, List, Optional, Any, Union, cast, Iterable
import uuid
import re
from collections import Counter
from pydantic import SecretStr
from datetime import datetime
import asyncio
from app.database import get_data, insert_data
from app.services.database.database_service import MongoDBService

from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.tools import BaseTool
from langchain_google_genai import ChatGoogleGenerativeAI
# from langchain_openai import ChatOpenAI

from app.config import settings
from app.tools import AVAILABLE_TOOLS
import threading
from app.s3_utils import fetch_docs_from_s3, create_prompt_file

logger = logging.getLogger("uvicorn")

_docs_cache = {
    "content": None,
    "docs_meta": None,
    "timestamp": None 
}
update_docs_lock = threading.Lock()  # Lock per sincronizzare gli aggiornamenti manuali

def get_combined_docs():
    """
    Restituisce il contenuto combinato dei file Markdown usando la cache se disponibile.
    Aggiorna anche i metadati se la cache è vuota.
    """
    global _docs_cache
    if (_docs_cache["content"] is None) or (_docs_cache["docs_meta"] is None):
        logger.info("Docs: cache is empty. Fetching from S3...")
        now = datetime.utcnow()
        result = fetch_docs_from_s3()
        _docs_cache["content"] = result["combined_docs"]
        _docs_cache["docs_meta"] = result["docs_meta"]
        _docs_cache["timestamp"] = now
    else:
        logger.info("Docs: found valid cache in use. no update triggered.")
    return _docs_cache["content"]

def build_system_prompt(combined_docs: str) -> str:
    """
    Costruisce e restituisce il system_prompt utilizzando il contenuto combinato dei documenti.
    """
    return f"""{combined_docs}"""
    return """ Sei un assistente che aiuta l'utente a ripassare per prepararsi al quiz di teoria per la licenza di paracadutismo.
    Se l'utente ti chiede di fare una domanda o una simulazione del quiz:
    1. utilizza il tool domande_simulazione_quiz per ottenere una domanda casuale.
    2. proponi la domanda all'utente.
    3. Se l'utente risponde, fagli sapere la risposta corretta"""
    

def update_docs():
    """
    Forza l'aggiornamento della cache dei documenti da S3 e rigenera il system_prompt.
    Aggiorna anche i metadati dei file e restituisce, nella response, il numero di documenti e per ognuno:
    il titolo e la data di ultima modifica.
    """
    global _docs_cache, combined_docs, system_prompt
    with update_docs_lock:
        logger.info("Docs: manual update in progress...")
        now = datetime.datetime.utcnow()
        result = fetch_docs_from_s3()
        _docs_cache["content"] = result["combined_docs"]
        _docs_cache["docs_meta"] = result["docs_meta"]
        _docs_cache["timestamp"] = now
        combined_docs = _docs_cache["content"]
        system_prompt = build_system_prompt(combined_docs)
        logger.info("Docs Cache and system_prompt updated successfully.")

        # Prepara i dati da ritornare: numero di documenti e metadati
        docs_count = len(result["docs_meta"])
        docs_details = result["docs_meta"]

        return {
            "message": "Document cache and system prompt updated successfully.",
            "docs_count": docs_count,
            "docs_details": docs_details,
            "system_prompt": system_prompt
        }

# Load Documents from S3 on load to build prompt
combined_docs = get_combined_docs()
system_prompt = build_system_prompt(combined_docs)

class AgentManager:
    # Store agent graphs and their checkpointers
    agents = {}
    checkpointers = {}
    # Store agent metadata for selection
    agent_metadata = {}
    # Store additional information for agents
    agent_additional_query = {}

    @staticmethod
    def create_agent(
        agent_id: str, 
        name: str,
        prompt: str, 
        model_name: str,
        tool_names: List[str],
        additional_query: Dict[str, Any] = {}
    ):
        # Check if agent already exists in memory
        if agent_id in AgentManager.agents:
            raise ValueError(f"Agent with ID '{agent_id}' already exists in memory.")
        
        # If agent doesn't exist, create a new one
        model_name = settings.FORCED_MODEL
        logger.info(f"Creating agent with ID: {agent_id}, name: {name}, model: {model_name}")
        model = ChatGoogleGenerativeAI(
            model=model_name,
            temperature=0,
            api_key=settings.GOOGLE_API_KEY
        )
        
        # Get the requested tools
        tool_names= ["get_domande_quiz"]
        tools = []
        for tool_name in tool_names:
            if tool_name in AVAILABLE_TOOLS:
                tools.append(AVAILABLE_TOOLS[tool_name])
        
        # Initialize memory to persist state between graph runs
        checkpointer = MemorySaver()
        
        # Create the agent using LangGraph's prebuilt function
        agent_graph = create_react_agent(
            model=model, 
            tools=tools, 
            checkpointer=checkpointer,
            prompt=prompt
        )
        
        # Store the agent and its checkpointer
        AgentManager.agents[agent_id] = agent_graph
        AgentManager.checkpointers[agent_id] = checkpointer
        
        # Store agent metadata for selection
        AgentManager.agent_metadata[agent_id] = {
            "name": name,
            "prompt": prompt
        }
        
        # Store additional information
        AgentManager.agent_additional_query[agent_id] = additional_query
        
        return {
            "agent_id": agent_id,
            "name": name,
            "prompt": prompt,
            "model_name": model_name,
            "tools": tool_names
        }
    
    @staticmethod
    def get_agent(agent_id: str):
        # Check if agent is already loaded
        if agent_id not in AgentManager.agents:
            # Get database service
            # Try to load from database or S3
     
            # Recreate the agent
            AgentManager.create_agent(
                "air-coach",
                "air-coach",
                system_prompt,
                "gemini-2.5-flash",
                ["get_quiz_domande"]
            )
        
        return {
            "agent": AgentManager.agents[agent_id],
            "checkpointer": AgentManager.checkpointers[agent_id],
            "metadata": AgentManager.agent_metadata[agent_id]
        }

    @staticmethod
    def load_agents_from_db():
        # Get database service
        
        # Get all agents from database
        AgentManager.create_agent(
                        "air-coach",
                        "air-coach",
                        system_prompt,
                        "gemini-2.5-flash",
                        ["get_quiz_domande"]
                    )
    
        logger.info(f"Loaded agent from storage")
    
    @staticmethod
    async def process_chat(
        query: str,
        agent_id: Optional[str],
        thread_id: str,
        user_id: Optional[str] = None,
        include_history: bool = False
    ):
        """
        Process a chat query using the appropriate agent.
        If agent_id is provided, that specific agent will be used.
        If not, the system will select the most appropriate agent based on the query.
        
        Args:
            query: The user's query
            agent_id: Optional ID of the agent to use
            thread_id: ID of the conversation thread
            user_id: Optional ID of the user
            user_info: Optional additional information about the user
            additional_prompts: Optional additional_prompts for the agent (language, units, etc.)
            include_history: Whether to include chat history in the context
            include_documents: Whether to include document content in context
        """
        # If no agent_id provided, select the most appropriate agent
        logger.info(f"Processing chat with query: {query}, agent_id: {agent_id}, thread_id: {thread_id}, user_id: {user_id}")
        # Get the agent
        agent_info = AgentManager.get_agent(agent_id)
        logger.info(f"Using agent: {agent_info['metadata']['name']} with ID: {agent_id}")
        agent = agent_info["agent"]
        metadata = agent_info["metadata"]
        
        # Get current date and time
        current_date = datetime.now().strftime("%Y-%m-%d")
        current_time = datetime.now().strftime("%H:%M:%S")
        
        # Add document content if available and requested

        # Create input for the agent with context
        agent_input = {
            "messages": [
            ]
        }
        
        history_limit = 10

        try:
            if include_history:
                db = MongoDBService(settings.DATABASE_NAME)
                history = db.get_items(
                    collection=settings.COLLECTION_NAME,
                    query={"userId": user_id},
                    limit=history_limit
                )
                previous_messages = []
                for msg in history:
                    previous_messages.append({"role": "human", "content": msg["human"]})
                    previous_messages.append({"role": "assistant", "content": msg["system"]})

                # Add previous messages to the input
                if previous_messages:
                    agent_input["messages"].extend(previous_messages)

        except Exception as e:
            logger.error(f"An error occurred while retrieving chat history: {e}")
            return f"data: {{'error': 'An error occurred while retrieving chat history: {str(e)}'}}\n\n"

        # Add the current query
        agent_input["messages"].append({"role": "user", "content": query })
        logger.info(f"Agent input updated with user query: {query}")
        
        # Invoke the agent with the thread_id for state persistence
        final_state = agent.invoke(
            agent_input,
            config={"configurable": {"thread_id": thread_id}}
        )
        
        # Extract the response
        response = final_state["messages"][-1].content

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"Response completed at {timestamp}: {response}")
        data = {}
        try:
            data = {
                "human": query,
                "system": response,
                "userId": user_id,
                "agentId": agent_id,
                "timestamp": timestamp
            }
            db.insert_items(
                collection=settings.COLLECTION_NAME,
                items=[data]
            )
            logger.info(f"Response inserted into the collection: {settings.COLLECTION_NAME} ")
        except Exception as e:
            logger.error(f"An error occurred while inserting the data into the collection: {e}")

        return data