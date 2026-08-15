# pip install mysql-connector-python langchain-ollama langgraph sqlalchemy chainlit python-dotenv

from typing import TypedDict
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, END
from sqlalchemy import create_engine, text
from langchain_community.utilities import SQLDatabase
import chainlit as cl
from chainlit.types import ThreadDict
from chainlit.data.sql_alchemy import SQLAlchemyDataLayer
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ========================================
# DATABASE & LLM SETUP

# ========================================

# MySQL connection
engine = create_engine("mysql+mysqlconnector://root:h****#***@localhost:3306/hr")
db = SQLDatabase(engine)
db_schema = db.get_context()

# LLM setup
llm = ChatOllama(model="qwen2.5:0.5b")

# System prompt for SQL generation
system_prompt = f"""You are Jarvis, an intelligent SQL assistant.
Your job is to generate VALID SQL queries for SQL databases.
First take a look on database schema and understand it carefully and efficiently.

DATABASE SCHEMA:
{db_schema}

CRITICAL RULES:
1. Output ONLY the SQL query - NO explanations, NO markdown, NO backticks
2. Use ACTUAL table names from schema: employees, departments, jobs, locations, countries, regions, job_history
3. Use ACTUAL column names from tables
4. NEVER use placeholders like 'table_name', 'table1', 'column1', 'condition'
5. Only SELECT queries - no INSERT, UPDATE, DELETE
6. Always use proper MySQL syntax

EXAMPLES FOR COMMON QUERIES:

Q: "highest salary employee"
A: SELECT first_name, last_name, salary FROM employees WHERE salary = (SELECT MAX(salary) FROM employees);

Q: "first 5 employees"
A: SELECT * FROM employees LIMIT 5;

Q: "highest salary by department"
A: SELECT d.department_name, e.first_name, e.last_name, e.salary FROM employees e JOIN departments d ON e.department_id = d.department_id WHERE e.salary IN (SELECT MAX(salary) FROM employees GROUP BY department_id);

Q: "all jobs"
A: SELECT * FROM jobs;

Q: "employees in IT"
A: SELECT first_name, last_name, job_id FROM employees WHERE job_id LIKE 'IT%';

Output ONLY the SQL query!"""


# ========================================
# STATE DEFINITION
# ========================================

class State(TypedDict):
    question: str
    llm_query: str
    query: str
    answer: list
    check: int
    retries: int
    max_retries: int
    error_message: str


# ========================================
# GRAPH NODES
# ========================================

def generate_query(state: State):
    """Generate initial SQL query from user question"""
    print("\n[1] Generating SQL query...")
    question = state["question"]
    
    prompt = [
        SystemMessage(system_prompt),
        HumanMessage(f"User question: {question}\nProduce ONLY a SQL SELECT query.")
    ]
    
    try:
        sql = llm.invoke(prompt).content.strip()
        sql = sql.replace("```sql", "").replace("```", "").strip()
        print(f"[1] Generated: {sql}")
        return {"llm_query": sql}
    except Exception as e:
        print(f"[1] Error: {e}")
        return {"llm_query": "", "error_message": str(e)}


def extract_query(state: State):
    """Clean and extract the SQL query"""
    print("\n[2] Extracting clean query...")
    llm_query = state["llm_query"]
    
    if not llm_query:
        return {"query": "", "error_message": "No query generated"}
    
    prompt = [
        SystemMessage("Extract only the SQL query from the following text. Do not add anything."),
        HumanMessage(llm_query)
    ]
    
    try:
        clean = llm.invoke(prompt).content.strip()
        clean = clean.replace("```sql", "").replace("```", "").strip()
        print(f"[2] Clean query: {clean}")
        return {"query": clean}
    except Exception as e:
        print(f"[2] Error: {e}")
        return {"query": llm_query, "error_message": str(e)}


def execute_query(state: State):
    """Execute the SQL query"""
    print("\n[3] Executing SQL query...")
    query = state.get("query", "")
    check = state.get("check", 0)
    retries = state.get("retries", 0)
    
    if not query:
        return {"answer": [], "check": check + 1, "retries": retries + 1, "error_message": "Empty query"}
    
    print(f"[3] Query: {query}")
    
    try:
        with engine.connect() as conn:
            result = conn.execute(text(query))
            rows = result.mappings().all()
            
        if not rows or len(rows) == 0:
            print("[3] Query returned 0 rows")
            return {"answer": [], "check": check + 1, "retries": retries + 1, "error_message": "No rows returned"}
        
        print(f"[3] Success: {len(rows)} rows")
        return {"answer": rows, "check": 0, "retries": retries, "error_message": ""}
        
    except Exception as e:
        print(f"[3] SQL Error: {e}")
        return {"answer": [], "check": check + 1, "retries": retries + 1, "error_message": str(e)}


def check_result(state: State):
    """Regenerate query after failure"""
    print("\n[4] Regenerating query...")
    query = state.get("query", "")
    question = state.get("question", "")
    error_msg = state.get("error_message", "")
    
    prompt = [
        SystemMessage(system_prompt),
        HumanMessage(
            f"The previous SQL query failed or returned no rows:\n{query}\n"
            f"Error: {error_msg}\n"
            f"User question: {question}\n"
            f"Database schema: {db_schema}\n"
            "Please output ONLY a corrected SELECT SQL query (no explanation)."
        )
    ]
    
    try:
        new_q = llm.invoke(prompt).content.strip()
        new_q = new_q.replace("```sql", "").replace("```", "").strip()
        print(f"[4] New query: {new_q}")
        return {"query": new_q, "check": 0}
    except Exception as e:
        print(f"[4] Error: {e}")
        return {"check": 1, "error_message": str(e)}


def handle_max_retries(state: State):
    """Handle max retries reached"""
    print("\n[5] Max retries reached")
    return {"answer": [], "check": 1, "error_message": "Maximum retries exceeded"}


# ========================================
# ROUTING FUNCTION
# ========================================

def route_execute(state: State) -> str:
    """Route based on execution result"""
    retries = state.get("retries", 0)
    max_retries = state.get("max_retries", 3)
    answer = state.get("answer", [])
    check = state.get("check", 0)
    
    # Success case
    if answer and len(answer) > 0 and check == 0:
        return "success"
    
    # Max retries reached
    if retries >= max_retries:
        return "max_retries"
    
    # Retry needed
    return "retry"


# ========================================
# BUILD LANGGRAPH
# ========================================

graph = StateGraph(State)

# Add nodes
graph.add_node("generate_query", generate_query)
graph.add_node("extract_query", extract_query)
graph.add_node("execute_query", execute_query)
graph.add_node("check_result", check_result)
graph.add_node("handle_max_retries", handle_max_retries)

# Set entry point
graph.set_entry_point("generate_query")

# Add edges
graph.add_edge("generate_query", "extract_query")
graph.add_edge("extract_query", "execute_query")

# Conditional routing from execute_query
graph.add_conditional_edges(
    "execute_query",
    route_execute,
    {
        "success": END,
        "retry": "check_result",
        "max_retries": "handle_max_retries"
    }
)

# After check_result, go back to execute_query
graph.add_edge("check_result", "execute_query")
graph.add_edge("handle_max_retries", END)

# Compile the graph
app = graph.compile()


# ========================================
# CHAINLIT AUTHENTICATION
# ========================================

@cl.password_auth_callback
def auth_callback(username: str, password: str):
    """Simple authentication"""
    if (username, password) == ("admin", "admin"):
        return cl.User(
            identifier="admin",
            metadata={"role": "admin", "provider": "credentials"}
        )
    return None


# ========================================
# CHAINLIT DATA LAYER
# ========================================

@cl.data_layer
def get_data_layer():
    """Initialize database layer for chat persistence"""
    conninfo = os.getenv("DATABASE_URL")
    
    if not conninfo:
        print("⚠️ DATABASE_URL not set - chat persistence disabled")
        return None
    
    try:
        return SQLAlchemyDataLayer(conninfo=conninfo)
    except Exception as e:
        print(f"❌ SQLAlchemyDataLayer error: {e}")
        return None


# ========================================
# CHAINLIT CHAT HANDLERS
# ========================================

@cl.on_chat_start
async def on_chat_start():
    """Initialize chat session"""
    cl.user_session.set("chat_history", [])
    await cl.Message(
        content="👋 **Hello! I'm Jarvis, your SQL assistant.**\n\n"
                "Ask me questions about your HR database and I'll generate SQL queries to find the answers!\n\n"
                "Examples:\n"
                "- Show me the top 5 highest paid employees\n"
                "- List all departments\n"
                "- Who works in the IT department?"
    ).send()


@cl.on_message
async def on_message(msg: cl.Message):
    """Handle incoming user messages"""
    try:
        # Show processing message
        processing_msg = cl.Message(content="🔍 Analyzing your question and generating SQL query...")
        await processing_msg.send()
        
        # Prepare initial state
        initial_state = {
            "question": msg.content,
            "llm_query": "",
            "query": "",
            "answer": [],
            "check": 0,
            "retries": 0,
            "max_retries": 3,
            "error_message": ""
        }
        
        # Execute the graph
        result = app.invoke(initial_state)
        
        # Remove processing message
        await processing_msg.remove()
        
        # Extract results
        answer = result.get("answer", [])
        query = result.get("query", "")
        error_msg = result.get("error_message", "")
        retries = result.get("retries", 0)
        
        # Format output
        if answer and len(answer) > 0:
            output = f"### ✅ Query Successful\n\n"
            output += f"**SQL Query:**\n```sql\n{query}\n```\n\n"
            output += f"**Results ({len(answer)} rows):**\n\n"
            
            # Format results as table
            for i, row in enumerate(answer, 1):
                row_dict = dict(row)
                output += f"**Row {i}:**\n"
                for key, value in row_dict.items():
                    output += f"- **{key}:** {value}\n"
                output += "\n"
                
                # Limit display to 10 rows
                if i >= 10:
                    output += f"*... and {len(answer) - 10} more rows*\n"
                    break
        else:
            output = f"### ❌ Query Failed\n\n"
            if error_msg:
                output += f"**Error:** {error_msg}\n\n"
            output += f"**Last Query Attempted:**\n```sql\n{query}\n```\n\n"
            output += f"**Retries:** {retries}\n\n"
            output += "💡 Try rephrasing your question or ask about available tables."
        
        # Send response
        await cl.Message(content=output).send()
        
        # Store in chat history
        history = cl.user_session.get("chat_history", [])
        history.append({"user": msg.content, "assistant": output})
        cl.user_session.set("chat_history", history)
        
    except Exception as e:
        await cl.Message(
            content=f"### ❌ System Error\n\n{str(e)}\n\nPlease try again or contact support."
        ).send()
        print(f"Error in on_message: {e}")


@cl.on_chat_resume
async def on_chat_resume(thread: ThreadDict):
    """Resume previous chat session"""
    try:
        print(f"\n🔄 Resuming thread: {thread.get('id')}")
        
        steps = thread.get("steps", [])
        restored_history = []
        
        for step in steps:
            step_type = step.get("type")
            user_text = step.get("input", "")
            ai_text = step.get("output", "")
            
            if step_type == "user_message" and user_text:
                restored_history.append({"user": user_text.strip()})
            
            if step_type == "assistant_message" and ai_text:
                if restored_history:
                    restored_history[-1]["assistant"] = ai_text.strip()
        
        cl.user_session.set("chat_history", restored_history)
        
        print(f"✅ Restored {len(restored_history)} conversation turns")
        await cl.Message(content="💬 **Chat resumed!** Feel free to continue asking questions.").send()
        
    except Exception as e:
        print(f"❌ Error in on_chat_resume: {e}")
        cl.user_session.set("chat_history", [])
        await cl.Message(content="⚠️ Could not restore chat history. Starting fresh.").send()


# ========================================
# MAIN ENTRY POINT
# ========================================

if __name__ == "__main__":
    print("🚀 Starting Jarvis SQL Assistant...")
    print("📊 Database schema loaded")
    print("🤖 LLM initialized")
    print("✅ Ready to serve!")
