# pip install -U "langchain[gemini]"
# pip install -U langchain-google-vertexai

from typing import Annotated

from .logging_config import logger
from .env import *

from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

# from langchain.chat_models import init_chat_model
from langchain_google_genai import ChatGoogleGenerativeAI


class State(TypedDict):
    # Messages have the type "list". The `add_messages` function
    # in the annotation defines how this state key should be updated
    # (in this case, it appends messages to the list, rather than overwriting them)
    messages: Annotated[list, add_messages]


graph_builder = StateGraph(State)

print(f"Graph builder initialized. \n{graph_builder}")

model = "gemini-2.5-flash-lite-preview-06-17" # test only, rimettere "gemini-2.5-flash"
llm = ChatGoogleGenerativeAI(
    model=model,
    temperature=0.7,
    # cache=True, # Cache is not supported in the current version of langchain_google_genai
    google_api_key=GOOGLE_API_KEY
)
# llm = init_chat_model("gemini:gemini-2.5-flash-lite-preview-06-17", temperature=0.7, cache=True)


def chatbot(state: State):
    return {"messages": [llm.invoke(state["messages"])]}

# The first argument is the unique node name
# The second argument is the function or object that will be called whenever
# the node is used.
graph_builder.add_node("chatbot", chatbot)

graph_builder.add_edge(START, "chatbot")
graph_builder.add_edge("chatbot", END)
graph = graph_builder.compile()

print(f"Graph compiled. \n{graph}")

def stream_graph_updates(user_input: str):
    for event in graph.stream({"messages": [{"role": "user", "content": user_input}]}):
        for value in event.values():
            print("Assistant:", value["messages"][-1].content)


while True:
    try:
        user_input = input("User: ")
        if user_input.lower() in ["quit", "exit", "q"]:
            print("Goodbye!")
            break
        stream_graph_updates(user_input)
    except:
        # fallback if input() is not available
        user_input = "What do you know about LangGraph?"
        print("User: " + user_input)
        stream_graph_updates(user_input)
        break