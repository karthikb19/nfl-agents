# unified_agent.py - Main orchestrator agent

import json
import time
from typing import Any, Dict, List

from utils.config import MODEL, OPENROUTER_URL, get_openrouter_headers
from utils.llm_parsing import extract_json_object
from .prompts import UNIFIED_AGENT_SYSTEM_PROMPT
from .tools import call_sql_agent, call_web_agent

import requests


HEADERS = get_openrouter_headers()


def call_llm_messages(
    messages: List[Dict[str, str]],
    model: str = MODEL,
    max_tokens: int = 2048,
    temperature: float = 0.0,
) -> str:
    """
    Call OpenRouter with an explicit messages list.
    Returns the assistant's text content.
    """
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": messages,
    }
    time.sleep(3)  # Rate limiting

    llm_start = time.time()
    resp = requests.post(
        OPENROUTER_URL,
        headers=HEADERS,
        json=payload,
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    llm_duration = time.time() - llm_start

    try:
        choice = data["choices"][0]
        print(f"  🤖 Orchestrator LLM: {llm_duration:.3f}s (finish_reason: {choice.get('finish_reason')})")
        content = choice["message"]["content"].strip()
        return content
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"Unexpected LLM response format: {data}") from e


def _print_progress(step: int, max_steps: int, action: str, thought: str | None = None) -> None:
    bar_len = 20
    filled = int(bar_len * step / max_steps)
    bar = "[" + "█" * filled + "░" * (bar_len - filled) + "]"
    suffix = f" {action}"
    if thought:
        suffix += f" – {thought[:60]}..."
    print(f"{bar} Step {step}/{max_steps}{suffix}")


def run_unified_agent(
    question: str,
    max_steps: int = 5,
    show_progress: bool = True,
) -> Dict[str, Any]:
    """
    Main orchestrator loop:
      1) Present question + history to LLM
      2) LLM decides: CALL_SQL_AGENT, CALL_WEB_AGENT, or FINISH
      3) Execute chosen tool, add result to history
      4) Repeat until FINISH or max_steps

    Returns:
        {
            "final_answer": str,
            "history": List[Dict],
        }
    """
    print("\n" + "=" * 60)
    print("🏈 Unified NFL Agent - Processing your question...")
    print("=" * 60 + "\n")

    history: List[Dict[str, Any]] = []

    for step in range(1, max_steps + 1):
        context = {
            "question": question,
            "history": history,
        }

        messages = [
            {"role": "system", "content": UNIFIED_AGENT_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(context, indent=2)},
        ]

        raw = call_llm_messages(messages, model=MODEL)
        clean = extract_json_object(raw)

        try:
            parsed = json.loads(clean)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Orchestrator did not return valid JSON at step {step}.\n"
                f"Raw response:\n{raw}\n\n"
                f"Extracted candidate JSON:\n{clean}"
            ) from e

        action = parsed.get("action")
        thought = parsed.get("thought", "")

        if action == "FINISH":
            final_answer = parsed.get("final_answer", "").strip()
            if show_progress:
                _print_progress(step, max_steps, "FINISH ✓")
            return {
                "final_answer": final_answer,
                "history": history,
            }

        if action == "CALL_SQL_AGENT":
            sub_question = parsed.get("question", question)
            if show_progress:
                _print_progress(step, max_steps, "CALL_SQL_AGENT", thought)

            print(f"\n  📊 Calling SQL Agent: \"{sub_question[:80]}...\"")
            tool_start = time.time()
            result = call_sql_agent(sub_question)
            tool_duration = time.time() - tool_start
            print(f"  ⏱️  SQL Agent completed in {tool_duration:.1f}s")

            history.append({
                "step": step,
                "action": "CALL_SQL_AGENT",
                "thought": thought,
                "question": sub_question,
                "result": result,
            })
            continue

        if action == "CALL_WEB_AGENT":
            sub_question = parsed.get("question", question)
            if show_progress:
                _print_progress(step, max_steps, "CALL_WEB_AGENT", thought)

            print(f"\n  🌐 Calling Web Agent: \"{sub_question[:80]}...\"")
            tool_start = time.time()
            result = call_web_agent(sub_question)
            tool_duration = time.time() - tool_start
            print(f"  ⏱️  Web Agent completed in {tool_duration:.1f}s")

            history.append({
                "step": step,
                "action": "CALL_WEB_AGENT",
                "thought": thought,
                "question": sub_question,
                "result": result,
            })
            continue

        raise ValueError(f"Unexpected orchestrator action at step {step}: {parsed}")

    # If we get here, max_steps reached without FINISH
    return {
        "final_answer": "I was not able to complete the analysis within the step limit.",
        "history": history,
    }


def format_unified_response(result: Dict[str, Any]) -> str:
    """
    Format the unified agent result for display - Claude Code style.
    """
    lines = []
    
    # Clean answer display
    answer = result.get("final_answer", "")
    lines.append("")
    lines.append(answer)
    lines.append("")

    # Compact tool summary
    history = result.get("history", [])
    if history:
        tools_used = []
        for h in history:
            action = h.get("action", "").replace("CALL_", "").replace("_AGENT", "").lower()
            success = h.get("result", {}).get("success", False)
            icon = "✓" if success else "✗"
            tools_used.append(f"{icon} {action}")
        lines.append(f"  \033[2m[{' → '.join(tools_used)}]\033[0m")
        lines.append("")

    return "\n".join(lines)


def _clear_line():
    """Clear current line in terminal."""
    print("\033[2K\033[1G", end="", flush=True)


def _dim(text: str) -> str:
    """Return dimmed text."""
    return f"\033[2m{text}\033[0m"


def _bold(text: str) -> str:
    """Return bold text."""
    return f"\033[1m{text}\033[0m"


def _green(text: str) -> str:
    """Return green text."""
    return f"\033[32m{text}\033[0m"


def _blue(text: str) -> str:
    """Return blue text."""
    return f"\033[34m{text}\033[0m"


def main():
    import os
    
    # Clean header
    print()
    print(_bold("  NFL Agent"))
    print(_dim("  sql + web search for NFL questions"))
    print()
    print(_dim("  commands: /quit, /clear"))
    print()
    
    while True:
        try:
            # Clean prompt
            query = input(_blue("❯ ")).strip()
        except (EOFError, KeyboardInterrupt):
            print("\n")
            break

        if not query:
            continue

        # Commands
        if query.lower() in ["/q", "/quit", "/exit", "quit", "exit"]:
            print()
            break
        
        if query.lower() in ["/clear", "/c"]:
            os.system("clear" if os.name != "nt" else "cls")
            print()
            print(_bold("  NFL Agent"))
            print()
            continue

        # Processing indicator
        print()
        print(_dim("  thinking..."))
        
        # Run the agent
        result = run_unified_agent(query, max_steps=5, show_progress=False)
        
        # Clear "thinking..." and show response
        print("\033[1A\033[2K", end="")  # Move up and clear line
        formatted = format_unified_response(result)
        print(formatted)


if __name__ == "__main__":
    main()

