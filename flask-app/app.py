# Flask Chat Interface for NFL Unified Agent
# Provides a clean, premium UI with dynamic thinking updates

import json
import sys
import os
import importlib
from flask import Flask, render_template, request, Response, jsonify, session
from typing import Generator

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import unified agent
unified_agent_module = importlib.import_module("unified-agent.unified_agent")
run_unified_agent = unified_agent_module.run_unified_agent

app = Flask(__name__)
app.secret_key = os.urandom(24)

# In-memory conversation store (per-session would need session storage)
conversations = {}


def get_conversation_id():
    """Get or create a conversation ID for the current session."""
    if 'conversation_id' not in session:
        session['conversation_id'] = os.urandom(8).hex()
    return session['conversation_id']


def get_conversation_history(conv_id: str) -> list:
    """Get conversation history for a given ID."""
    if conv_id not in conversations:
        conversations[conv_id] = []
    return conversations[conv_id]


def add_to_history(conv_id: str, role: str, content: str):
    """Add a message to conversation history."""
    history = get_conversation_history(conv_id)
    history.append({"role": role, "content": content})
    # Keep last 20 messages for context
    if len(history) > 20:
        conversations[conv_id] = history[-20:]


def format_context_prompt(history: list, current_question: str) -> str:
    """Format conversation history into context for the agent."""
    if not history:
        return current_question
    
    context_parts = ["Previous conversation:"]
    for msg in history[-10:]:  # Last 10 messages for context
        role = "User" if msg["role"] == "user" else "Assistant"
        context_parts.append(f"{role}: {msg['content']}")
    
    context_parts.append(f"\nCurrent question: {current_question}")
    return "\n".join(context_parts)


@app.route("/")
def index():
    """Serve the chat interface."""
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    """Handle chat messages and stream responses."""
    data = request.get_json()
    message = data.get("message", "").strip()
    
    if not message:
        return jsonify({"error": "No message provided"}), 400
    
    conv_id = get_conversation_id()
    history = get_conversation_history(conv_id)
    
    # Add user message to history
    add_to_history(conv_id, "user", message)
    
    # Format with context
    contextual_prompt = format_context_prompt(history[:-1], message)
    
    def generate() -> Generator[str, None, None]:
        """Generate SSE events for the chat response."""
        try:
            # Send thinking indicator
            yield f"data: {json.dumps({'type': 'thinking', 'content': 'Analyzing your question...'})}\n\n"
            
            # Run the unified agent
            result = run_unified_agent(contextual_prompt, max_steps=5, show_progress=False)
            
            # Send step updates from history
            agent_history = result.get("history", [])
            for step in agent_history:
                action = step.get("action", "").replace("CALL_", "").replace("_AGENT", "")
                thought = step.get("thought", "")[:100]
                step_msg = {
                    "type": "step",
                    "action": action.lower(),
                    "thought": thought,
                    "success": step.get("result", {}).get("success", False)
                }
                yield f"data: {json.dumps(step_msg)}\n\n"
            
            # Send final answer
            final_answer = result.get("final_answer", "I wasn't able to find an answer.")
            
            # Add assistant response to history
            add_to_history(conv_id, "assistant", final_answer)
            
            yield f"data: {json.dumps({'type': 'answer', 'content': final_answer})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            
        except Exception as e:
            error_msg = f"An error occurred: {str(e)}"
            yield f"data: {json.dumps({'type': 'error', 'content': error_msg})}\n\n"
    
    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )


@app.route("/clear", methods=["POST"])
def clear_history():
    """Clear conversation history."""
    conv_id = get_conversation_id()
    if conv_id in conversations:
        conversations[conv_id] = []
    return jsonify({"status": "cleared"})


@app.route("/history", methods=["GET"])
def get_history():
    """Get current conversation history."""
    conv_id = get_conversation_id()
    history = get_conversation_history(conv_id)
    return jsonify({"history": history})


if __name__ == "__main__":
    app.run(debug=True, port=5001, threaded=True)
