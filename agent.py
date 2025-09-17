import os
import uuid
import sqlite3
import hashlib

from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from langsmith import Client
from langchain_core.tracers.langchain import LangChainTracer
from typing import Dict, Any, Optional

from models import QueryResult, AgentState
from utils import clean_sql, format_history, format_query_data

load_dotenv()


class AppPortfolioAgent:

    def __init__(self, db_path: str, ollama_base_url: str = "http://localhost:11434",
                 langsmith_api_key: Optional[str] = None, langsmith_project: Optional[str] = None,
                 enable_caching: bool = True):
        self.db_path = db_path
        self.enable_caching = enable_caching
        self.query_cache = {} if enable_caching else None
        self.states = {}
        self._setup_langsmith(langsmith_api_key, langsmith_project)
        self._initialize_models(ollama_base_url)
        self._setup_schema_and_prompts()
        self.graph = self._build_graph()

    def _setup_langsmith(self, api_key: Optional[str], project: Optional[str]) -> None:
        self.langsmith_enabled = False
        if api_key and project:
            try:
                os.environ["LANGCHAIN_TRACING_V2"] = "true"
                os.environ["LANGSMITH_API_KEY"] = api_key
                os.environ["LANGSMITH_PROJECT"] = project
                self.langsmith_client = Client(api_key=api_key)
                self.langsmith_tracer = LangChainTracer(project_name=project)
                self.langsmith_enabled = True
            except Exception:
                self.langsmith_enabled = False

    def _initialize_models(self, ollama_base_url: str) -> None:
        self.sql_llm = ChatOllama(
            model="duckdb-nsql",
            base_url=ollama_base_url,
            temperature=0,
            num_predict=300,
            top_p=0.9,
            repeat_penalty=1.1
        )
        self.intent_llm = ChatOllama(
            model="llama3:8b",
            base_url=ollama_base_url,
            temperature=0,
            num_predict=10,
            top_p=0.9,
            repeat_penalty=1.1
        )

    def _setup_schema_and_prompts(self) -> None:
        self.schema = """
Table: app_metrics
Columns:
- id: INTEGER PRIMARY KEY AUTOINCREMENT
- app_name: TEXT NOT NULL
- platform: TEXT NOT NULL (values: 'iOS', 'Android')
- date: DATE NOT NULL
- country: TEXT NOT NULL
- installs: INTEGER NOT NULL
- in_app_revenue: REAL NOT NULL
- ads_revenue: REAL NOT NULL
- ua_cost: REAL NOT NULL
Constraints:
- UNIQUE(app_name, platform, date, country)
"""
        self.intent_prompt = ChatPromptTemplate.from_messages([
            ("system", "Classify the user's intent as one of: 'query', 'delete', 'export', 'show_sql', or 'off_topic'."),
            ("human", "Conversation history:\n{history}\n\nCurrent question: {question}")
        ])
        self.sql_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an expert SQL generator for SQLite. Use the schema:\n{schema}\n"
                       "Always sum in_app_revenue and ads_revenue for revenue questions.\n"
                       "Return only the SQL query."),
            ("human", "Conversation history:\n{history}\n\nCurrent question: {question}")
        ])

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(AgentState)
        graph.add_node("classify_intent", self.classify_intent)
        graph.add_node("generate_sql", self.generate_sql)
        graph.add_node("execute_sql", self.execute_sql)
        graph.add_node("format_response", self.format_response)
        graph.add_node("handle_export", self.handle_export)
        graph.add_node("handle_off_topic", self.handle_off_topic)

        graph.set_entry_point("classify_intent")

        graph.add_conditional_edges(
            "classify_intent",
            self._route_intent,
            {
                "query": "generate_sql",
                "delete": "generate_sql",
                "export": "handle_export",
                "show_sql": "format_response",
                "off_topic": "handle_off_topic",
            }
        )

        graph.add_edge("generate_sql", "execute_sql")
        graph.add_edge("execute_sql", "format_response")
        graph.add_edge("format_response", END)
        graph.add_edge("handle_export", END)
        graph.add_edge("handle_off_topic", END)

        return graph.compile()

    def _log_to_langsmith(self, event_name: str, inputs: Dict[str, Any], outputs: Dict[str, Any],
                          session_id: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        if not self.langsmith_enabled:
            return
        try:
            self.langsmith_client.create_run(
                name=event_name,
                inputs=inputs,
                outputs=outputs,
                run_type="chain",
                session_name=session_id,
                extra=metadata or {}
            )
        except Exception:
            pass

    def classify_intent(self, state: AgentState) -> AgentState:
        session_id = state.get("session_id", str(uuid.uuid4()))
        if not state.get("messages"):
            return {"intent": "off_topic", "session_id": session_id}

        question = state["messages"][-1].content.lower().strip()

        if any(keyword in question for keyword in ["export", "download", "csv"]):
            return {"intent": "export", "session_id": session_id}
        elif any(keyword in question for keyword in ["query", "sql", "what query"]):
            return {"intent": "show_sql", "session_id": session_id}
        elif any(keyword in question for keyword in ["delete", "remove"]):
            return {"intent": "delete", "session_id": session_id}
        elif any(keyword in question for keyword in ["app", "revenue", "install", "country", "platform", "how many", "list", "show"]):
            return {"intent": "query", "session_id": session_id}

        history = format_history(state)
        config = self._get_langsmith_config(session_id, "intent_classification", question)
        intent_chain = self.intent_prompt | self.intent_llm
        raw_intent = intent_chain.invoke(
            {"question": question, "history": history}, config
        ).content.strip().lower()

        allowed = {"query", "delete", "export", "show_sql", "off_topic"}
        intent = next((label for label in allowed if label in raw_intent), "off_topic")

        self._log_to_langsmith(
            "intent_classification",
            {"question": question, "history": history[:200]},
            {"intent": intent, "raw_intent": raw_intent, "used_patterns": True},
            session_id,
            {"step": "classify_intent"}
        )

        return {"intent": intent, "session_id": session_id}

    def generate_sql(self, state: AgentState) -> AgentState:
        session_id = state.get("session_id", str(uuid.uuid4()))
        if not state.get("messages"):
            return {"sql_query": None, "session_id": session_id}

        question = state["messages"][-1].content
        history = format_history(state)
        config = self._get_langsmith_config(session_id, "sql_generation", question)
        sql_chain = self.sql_prompt | self.sql_llm
        sql_query = sql_chain.invoke(
            {"question": question, "history": history, "schema": self.schema}, config
        ).content.strip()
        sql_query = clean_sql(sql_query)

        self._log_to_langsmith(
            "sql_generation",
            {"question": question, "history": history[:200], "schema": self.schema},
            {"sql_query": sql_query},
            session_id,
            {"step": "generate_sql"}
        )

        return {"sql_query": sql_query, "session_id": session_id}

    def execute_sql(self, state: AgentState) -> AgentState:
        session_id = state.get("session_id", str(uuid.uuid4()))
        sql_query = state.get("sql_query")
        if not sql_query:
            query_result = {"data": [], "column_names": [], "row_count": 0, "error": "No SQL query to execute"}
            return {"query_result": query_result, "session_id": session_id}

        cache_key = hashlib.sha256(sql_query.encode()).hexdigest() if self.enable_caching else None
        if cache_key and cache_key in self.query_cache:
            cached_result = self.query_cache[cache_key]
            return {"query_result": cached_result, "session_id": session_id}

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(sql_query)
                rows = cursor.fetchall()
                column_names = [description[0] for description in cursor.description] if rows else []
                query_result: QueryResult = {
                    "data": [dict(row) for row in rows],
                    "column_names": column_names,
                    "row_count": len(rows),
                    "error": None,
                }
            if cache_key and self.enable_caching:
                self.query_cache[cache_key] = query_result
            success = True
            error_msg = None
        except Exception as e:
            query_result = {"data": [], "column_names": [], "row_count": 0, "error": str(e)}
            success = False
            error_msg = str(e)

        return {"query_result": query_result, "session_id": session_id}

    def format_response(self, state: AgentState) -> AgentState:
        session_id = state.get("session_id", str(uuid.uuid4()))
        query_result = state.get("query_result")
        intent = state.get("intent")
        messages = state.get("messages", [])
        sql_query = state.get("sql_query", "").lower()
        is_follow_up = len([msg for msg in messages if isinstance(msg, HumanMessage)]) > 1

        if intent == "show_sql":
            prev_sql = state.get("sql_query")
            response = f"*Previous SQL Query:*\n```sql\n{prev_sql}\n```" if is_follow_up and prev_sql else "*No previous SQL query available.*"
        elif query_result:
            if query_result.get("error"):
                response = f"Error: {query_result['error']}"
            elif query_result.get("data"):
                lower_sql = sql_query.replace(" ", "")
                if "count(" in lower_sql:
                    first_row = query_result["data"][0]
                    count_value = list(first_row.values())[0]
                    response = str(count_value)
                else:
                    response = format_query_data(query_result, is_follow_up)
            else:
                response = "Query executed successfully but returned no data."
        else:
            response = "No query result available."

        messages.append(AIMessage(content=response))
        return {"messages": messages, "session_id": session_id}

    def handle_export(self, state: AgentState) -> AgentState:
        session_id = state.get("session_id", str(uuid.uuid4()))
        query_result = state.get("query_result")
        if not query_result or not query_result["data"]:
            response = "No data available to export from previous query."
        else:
            response = "Preparing CSV export..."
        messages = state["messages"]
        messages.append(AIMessage(content=response))
        return {"messages": messages, "session_id": session_id}

    def handle_off_topic(self, state: AgentState) -> AgentState:
        session_id = state.get("session_id", str(uuid.uuid4()))
        response = "Sorry, I can only answer questions about the app portfolio analytics."
        messages = state["messages"]
        messages.append(AIMessage(content=response))
        return {"messages": messages, "session_id": session_id}

    def _route_intent(self, state: AgentState) -> str:
        return state.get("intent", "off_topic")

    def _get_langsmith_config(self, session_id: str, step: str, question: str) -> Dict[str, Any]:
        if not self.langsmith_enabled:
            return {}
        return {
            "callbacks": [self.langsmith_tracer],
            "tags": [step, f"session_{session_id}"],
            "metadata": {"step": step, "question": question[:100]}
        }

    def run(self, question: str, state: Optional[AgentState] = None) -> tuple[str, AgentState]:
        if state is None:
            session_id = str(uuid.uuid4())
            state = {
                "messages": [],
                "sql_query": None,
                "query_result": None,
                "intent": None,
                "session_id": session_id
            }
        else:
            session_id = state.get("session_id", str(uuid.uuid4()))
            state["session_id"] = session_id

        state["messages"].append(HumanMessage(content=question))

        try:
            config = {"configurable": {"thread_id": session_id}}
            if self.langsmith_enabled:
                config["callbacks"] = [self.langsmith_tracer]
                config["tags"] = [f"session_{session_id}", "full_run"]
                config["metadata"] = {"question": question[:100], "session_id": session_id}

            new_state = self.graph.invoke(state, config=config)
            ai_messages = [msg for msg in new_state["messages"] if isinstance(msg, AIMessage)]
            response = ai_messages[-1].content if ai_messages else "No response generated."
            return response, new_state
        except Exception as e:
            error_msg = f"Error: {e}"
            state["messages"].append(AIMessage(content=error_msg))
            return error_msg, state
