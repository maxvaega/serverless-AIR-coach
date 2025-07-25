from langchain_core.tools import tool
# from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
# from langchain_aws import ChatBedrock
# import boto3
from langchain_google_genai import ChatGoogleGenerativeAI

from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import AnyMessage, add_messages
from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableLambda
from langgraph.prebuilt import ToolNode
from langgraph.prebuilt import tools_condition
from langgraph.graph import StateGraph, START
from langgraph.checkpoint.memory import MemorySaver

# from .tools import AVAILABLE_TOOLS, domanda_quiz_teoria
from .logging_config import logger
from .env import *

from typing import Optional
import logging
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

def _print_event(event: dict, _printed: set):
    """
    Helper function to print events from the graph stream in a user-friendly format.
    """
    for node_name, output in event.items():
        if node_name not in _printed:
            _printed.add(node_name)
            if "messages" in output:
                message = output["messages"][-1]
                if message.tool_calls:
                    print(f"--- Calling Tool: {message.tool_calls[0]['name']} ---")
                else:
                    print(f"--- Assistant: ---\n{message.content}")
                    print("--------------------")

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

def handle_tool_error(state) -> dict:
    """
    Function to handle errors that occur during tool execution.
    
    Args:
        state (dict): The current state of the AI agent, which includes messages and tool call details.
    
    Returns:
        dict: A dictionary containing error messages for each tool that encountered an issue.
    """
    # Retrieve the error from the current state
    error = state.get("error")
    
    # Access the tool calls from the last message in the state's message history
    tool_calls = state["messages"][-1].tool_calls
    
    # Return a list of ToolMessages with error details, linked to each tool call ID
    return {
        "messages": [
            ToolMessage(
                content=f"Error: {repr(error)}\n please fix your mistakes.",  # Format the error message for the user
                tool_call_id=tc["id"],  # Associate the error message with the corresponding tool call ID
            )
            for tc in tool_calls  # Iterate over each tool call to produce individual error messages
        ]
    }

def create_tool_node_with_fallback(tools: list) -> dict:
    """
    Function to create a tool node with fallback error handling.
    
    Args:
        tools (list): A list of tools to be included in the node.
    
    Returns:
        dict: A tool node that uses fallback behavior in case of errors.
    """
    # Create a ToolNode with the provided tools and attach a fallback mechanism
    # If an error occurs, it will invoke the handle_tool_error function to manage the error
    return ToolNode(tools).with_fallbacks(
        [RunnableLambda(handle_tool_error)],  # Use a lambda function to wrap the error handler
        exception_key="error"  # Specify that this fallback is for handling errors
    )

class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]

class Assistant:
    def __init__(self, runnable: Runnable):
        # Initialize with the runnable that defines the process for interacting with the tools
        self.runnable = runnable

    def __call__(self, state: State):
        while True:
            # Invoke the runnable with the current state (messages and context)
            result = self.runnable.invoke(state)
            
            # If the tool fails to return valid output, re-prompt the user to clarify or retry
            if not result.tool_calls and (
                not result.content
                or isinstance(result.content, list)
                and not result.content[0].get("text")
            ):
                # Add a message to request a valid response
                messages = state["messages"] + [("user", "Respond with a real output.")]
                state = {**state, "messages": messages}
            else:
                # Break the loop when valid output is obtained
                break

        # Return the final state after processing the runnable
        return {"messages": result}
    
model = "gemini-2.5-flash-lite-preview-06-17" # test only, rimettere "gemini-2.5-flash"
llm = ChatGoogleGenerativeAI(
    model=model,
    temperature=0.7,
    # cache=True,
)

primary_assistant_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            '''Sei un assistente virtuale per prepararsi all'esame.
            Se l'utente desidera avviare una simulazione d'esame, utilizza lo strumento "domanda_quiz_teoria" 
            per ottenere domande dal database delle domande di teoria, e chiedere all'utente di rispondere per fare pratica.
            
            Una volta che l'utente ha risposto, verifica la risposta confrontandola con quella corretta.
            Se la risposta è corretta, rispondi con "Corretto!".
            Se la risposta è errata, rispondi con "Sbagliato! La risposta corretta è: <risposta corretta>".
            ''',
        ),
        ("placeholder", "{messages}"),
    ]
)

# Define the tools the assistant will use
part_1_tools = [
    domanda_quiz_teoria
]

# Bind the tools to the assistant's workflow
part_1_assistant_runnable = primary_assistant_prompt | llm.bind_tools(part_1_tools)

# Nodes
builder = StateGraph(State)
builder.add_node("assistant", Assistant(part_1_assistant_runnable))
builder.add_node("tools", create_tool_node_with_fallback(part_1_tools))

# Edges
builder.add_edge(START, "assistant")  # Start with the assistant
builder.add_conditional_edges("assistant", tools_condition)  # Move to tools after input
builder.add_edge("tools", "assistant")  # Return to assistant after tool execution

memory = MemorySaver()
graph = builder.compile(checkpointer=memory)

# import shutil
import uuid

# Let's create an example conversation a user might have with the assistant
tutorial_questions = [
    'hey',
    'facciamo un quiz di teoria'
]

thread_id = str(uuid.uuid4())

config = {
    "configurable": {
        "thread_id": thread_id,
    }
}

_printed = set()
for question in tutorial_questions:
    events = graph.stream(
        {"messages": ("user", question)}, config, stream_mode="values"
    )
    for event in events:
        _print_event(event, _printed)