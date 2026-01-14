# tools.py - Wrapper functions for SQL and Web agents

from typing import Any, Dict
import importlib

# Import using importlib for hyphenated module names
sql_agent_module = importlib.import_module("sql-agent.sql_agent")
web_agent_module = importlib.import_module("web-agent.web_agent_utils")

run_sql_agent = sql_agent_module.run_sql_agent
format_agent_response = sql_agent_module.format_agent_response
run_web_agent = web_agent_module.run_web_agent


def call_sql_agent(question: str) -> Dict[str, Any]:
    """
    Invoke the SQL agent and return a structured result.
    
    Returns:
        {
            "success": bool,
            "answer": str,
            "steps_taken": int,
            "error": str or None
        }
    """
    try:
        result = run_sql_agent(question, max_steps=10, show_progress=True)
        formatted = format_agent_response(result)
        return {
            "success": True,
            "answer": result.get("final_answer", ""),
            "formatted_response": formatted,
            "steps_taken": len(result.get("history", [])),
            "error": None
        }
    except Exception as e:
        return {
            "success": False,
            "answer": "",
            "formatted_response": "",
            "steps_taken": 0,
            "error": str(e)
        }


def call_web_agent(question: str) -> Dict[str, Any]:
    """
    Invoke the Web agent and return a structured result.
    
    Returns:
        {
            "success": bool,
            "answer": str,
            "sources": List[str],
            "error": str or None
        }
    """
    try:
        result = run_web_agent(question)
        return {
            "success": True,
            "answer": result.get("answer", ""),
            "sources": result.get("sources", []),
            "error": None
        }
    except Exception as e:
        return {
            "success": False,
            "answer": "",
            "sources": [],
            "error": str(e)
        }
