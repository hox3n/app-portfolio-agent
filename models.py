from typing import List, Optional, Dict, Any, Literal
from typing_extensions import Annotated, TypedDict
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, AIMessage


class QueryResult(TypedDict):
    data: List[Dict[str, Any]]
    column_names: List[str]
    row_count: int
    error: Optional[str]


class AgentState(TypedDict):
    messages: Annotated[List[HumanMessage | AIMessage], add_messages]
    sql_query: Optional[str]
    query_result: Optional[QueryResult]
    intent: Optional[Literal["query", "delete", "export", "show_sql", "off_topic"]]
    session_id: Optional[str]