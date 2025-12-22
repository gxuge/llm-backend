from typing_extensions import TypedDict

from langgraph.graph import END, StateGraph


class ChatState(TypedDict):
    message: str
    history: list[str]


def uppercase(state: ChatState) -> ChatState:
    """
    Simple node that uppercases the incoming message.
    """
    return {"message": state["message"].upper(), "history": state["history"]}


def echo(state: ChatState) -> ChatState:
    """
    Appends the (possibly transformed) message into the conversation history.
    """
    updated_history = [*state["history"], state["message"]]
    return {"message": state["message"], "history": updated_history}


graph = StateGraph(ChatState)
graph.add_node("uppercase", uppercase)
graph.add_node("echo", echo)
graph.add_edge("uppercase", "echo")
graph.add_edge("echo", END)
graph.set_entry_point("uppercase")

# Compile the graph once at startup; reuse across requests.
workflow = graph.compile()
