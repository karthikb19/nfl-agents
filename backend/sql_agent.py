# sql_agent.py

import json
import os
import time
from typing import Any, Dict, List, Tuple

import psycopg2
from psycopg2.extras import RealDictCursor
from decimal import Decimal
import requests
from dotenv import load_dotenv, find_dotenv
import re

from prompts import (
    RELEVANT_SCHEMA,
    FIND_APPROPRIATE_SCHEMA_PROMPT,
    SQL_AGENT_SYSTEM_PROMPT,
    NAME_NORMALIZER_SYSTEM_PROMPT,
)

# ----------------------------------------------------
# Setup
# ----------------------------------------------------

load_dotenv(find_dotenv())

# MODEL = "x-ai/grok-4.1-fast:free"
# MODEL = "openai/gpt-4.1-mini"
MODEL = "google/gemini-2.5-flash-lite"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

db_url = os.getenv("SUPABASE_DB_URL")
if not db_url:
    raise RuntimeError("SUPABASE_DB_URL is not set in the environment")

# Strip ?pgbouncer=... for psycopg2 compatibility
if "?pgbouncer=" in db_url:
    db_url = db_url.split("?pgbouncer=")[0]

if not OPENROUTER_API_KEY:
    raise RuntimeError("OPENROUTER_API_KEY is not set in the environment")

HEADERS = {
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    "Content-Type": "application/json",
}

def extract_json_object(raw: str) -> str:
    """
    Try to robustly extract a JSON object from an LLM response that may contain
    prose or Markdown fences.

    Strategy:
      1. If the whole string already looks like JSON (starts with '{' and ends with '}'), use it.
      2. If there is a ```json ... ``` code block, extract the inside.
      3. Otherwise, take the substring between the first '{' and the last '}'.
    """
    s = raw.strip()

    # 1) Pure JSON object
    if s.startswith("{") and s.endswith("}"):
        return s

    # 2) ```json ... ``` or ``` ... ``` block
    fence_match = re.search(r"```(?:json)?(.*?)```", s, re.DOTALL | re.IGNORECASE)
    if fence_match:
        inner = fence_match.group(1).strip()
        # sometimes there's a leading language label on the first line; strip it if needed
        # e.g. "json\n{...}"
        if inner.startswith("{") and inner.endswith("}"):
            return inner

    # 3) Fallback: first '{' to last '}'
    first = s.find("{")
    last = s.rfind("}")
    if first != -1 and last != -1 and first < last:
        return s[first:last + 1].strip()

    # If we can't find anything, just return as-is and let json.loads fail
    return s

def normalize_player_name(question: str) -> Dict[str, Any]:
    """
    Use an LLM to normalize all player names in the question to canonical NFL names.

    Expected LLM output (new format):
      {
        "players": [
          {
            "original": "<exact substring>",
            "normalized": "<canonical name or null>",
            "confidence": "<high|medium|low>",
            "reason": "<short explanation>"
          },
          ...
        ]
      }

    We normalize that into:
      {
        "players": [
          { "original": str|None, "normalized": str|None, "confidence": "high|medium|low", "reason": str },
          ...
        ]
      }

    and also gracefully handle the old single-object format as a fallback.
    """
    raw = call_llm(
        system=NAME_NORMALIZER_SYSTEM_PROMPT,
        user=question,
        model=MODEL,
        temperature=0.0,
    )

    clean = extract_json_object(raw)

    try:
        data = json.loads(clean)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Name normalizer did not return valid JSON.\n"
            f"Raw response:\n{raw}\n\n"
            f"Extracted candidate JSON:\n{clean}"
        ) from e

    def _coerce_player(obj: Dict[str, Any]) -> Dict[str, Any]:
        original = obj.get("original")
        normalized = obj.get("normalized")
        confidence = obj.get("confidence", "low")
        reason = obj.get("reason", "")

        if confidence not in {"high", "medium", "low"}:
            confidence = "low"

        return {
            "original": original if isinstance(original, str) or original is None else str(original),
            "normalized": normalized if isinstance(normalized, str) or normalized is None else str(normalized),
            "confidence": confidence,
            "reason": reason if isinstance(reason, str) else str(reason),
        }

    # NEW: preferred path – array under "players"
    if isinstance(data, dict) and isinstance(data.get("players"), list) and data["players"]:
        players = [_coerce_player(p) for p in data["players"]]
        return {"players": players}

    # FALLBACK: old single-object format
    if isinstance(data, dict):
        player = _coerce_player(data)
        return {"players": [player]}

    # Complete failure – surface a clean error
    raise ValueError(
        f"Name normalizer returned unexpected structure: {data!r}\n"
        f"Raw response:\n{raw}"
    )


# ----------------------------------------------------
# LLM helpers
# ----------------------------------------------------

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
    time.sleep(5)

    llm_start = time.time()
    resp = requests.post(
        OPENROUTER_URL,
        headers=HEADERS,
        json=payload,
        timeout=40,
    )
    resp.raise_for_status()
    data = resp.json()
    llm_duration = time.time() - llm_start

    try:
        choice = data["choices"][0]
        print(f"  🤖 OpenRouter round trip time: {llm_duration:.3f}s (finish_reason: {choice.get('finish_reason')})")
        content = choice["message"]["content"].strip()
        return content
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"Unexpected LLM response format: {data}") from e


def call_llm(system: str | None, user: str, **kwargs) -> str:
    """
    Backwards-compatible wrapper for simple system+user calls.
    """
    messages: List[Dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user})
    return call_llm_messages(messages, **kwargs)


# ----------------------------------------------------
# Schema narrowing
# ----------------------------------------------------

def choose_schema_for_query(user_query: str) -> dict:
    """
    Ask the schema-retrieval model which tables/columns are relevant.
    """
    system_prompt = FIND_APPROPRIATE_SCHEMA_PROMPT.replace(
        "{{RELEVANT_SCHEMA}}", RELEVANT_SCHEMA
    )

    raw = call_llm(
        system=system_prompt,
        user=user_query,
        model=MODEL,
        temperature=0.0,
    )

    try:
        schema_selection = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM did not return valid JSON: {raw}") from e

    if "tables" not in schema_selection or not isinstance(
        schema_selection["tables"], dict
    ):
        schema_selection = {"tables": {}}

    return schema_selection


def build_reduced_schema(schema_selection: dict) -> str:
    """
    Build a reduced schema JSON string containing only the selected
    tables/columns. Falls back to full schema if selection is empty.
    """
    full_schema = json.loads(RELEVANT_SCHEMA)
    tables = schema_selection.get("tables", {})

    reduced: Dict[str, Any] = {}
    for table_name, cols in tables.items():
        if table_name not in full_schema:
            continue

        table_def = full_schema[table_name]
        filtered_cols = {
            col: table_def["columns"][col]
            for col in cols
            if col in table_def["columns"]
        }

        if not filtered_cols:
            continue

        reduced[table_name] = {
            "pk": table_def.get("pk", []),
            "columns": filtered_cols,
            "fks": {
                col: target
                for col, target in table_def.get("fks", {}).items()
                if col in filtered_cols
            },
            "unique": table_def.get("unique", []),
        }

    if not reduced:
        reduced = full_schema

    return json.dumps(reduced, indent=2)


# ----------------------------------------------------
# SQL guardrails + execution
# ----------------------------------------------------

BANNED_SQL_KEYWORDS = [
    "insert",
    "update",
    "delete",
    "alter",
    "drop",
    "truncate",
    "create",
    "grant",
    "revoke",
    "merge",
    "call",
    "execute",
]


def validate_sql_readonly(sql: str) -> None:
    """
    Ensure SQL is read-only and looks like a SELECT/WITH query.
    Conservative on purpose: any sketchy pattern is rejected.
    """
    s = sql.strip().lower()

    # must start with select or with
    if not (s.startswith("select") or s.startswith("with")):
        raise ValueError(f"Rejected SQL (must be SELECT/WITH): {sql!r}")

    # simple blacklist
    for kw in BANNED_SQL_KEYWORDS:
        if kw in s:
            raise ValueError(f"Rejected SQL (banned keyword {kw}): {sql!r}")


def _convert_decimals(obj: Any) -> Any:
    """
    Recursively convert Decimal objects to float for JSON serialization.
    """
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, list):
        return [_convert_decimals(item) for item in obj]
    elif isinstance(obj, dict):
        return {key: _convert_decimals(value) for key, value in obj.items()}
    return obj


def execute_sql(sql: str) -> Tuple[List[str], List[List[Any]]]:
    """
    Execute a read-only SQL query and return (columns, rows).
    """
    validate_sql_readonly(sql)

    conn = psycopg2.connect(db_url)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql)
            records = cur.fetchall()
            if not records:
                return [], []
            columns = list(records[0].keys())
            rows = [[_convert_decimals(row[col]) for col in columns] for row in records]
            return columns, rows
    finally:
        conn.close()


# ----------------------------------------------------
# Progress bar helper
# ----------------------------------------------------

def _print_progress(step: int, max_steps: int, action: str, thought: str | None = None) -> None:
    bar_len = 20
    filled = int(bar_len * step / max_steps)
    bar = "[" + "#" * filled + "-" * (bar_len - filled) + "]"
    suffix = f" {action}"
    if thought:
        suffix += f" – {thought[:min(len(thought), 100)]}"
    print(f"{bar} Step {step}/{max_steps}{suffix}")


# ----------------------------------------------------
# Agent loop
# ----------------------------------------------------

def run_sql_agent(
    question: str,
    max_steps: int = 10,
    show_progress: bool = True,
) -> Dict[str, Any]:
    """
    Full pipeline:
      1) Narrow schema.
      2) Run an agent loop where the LLM:
         - Requests SQL via {"action": "CALL_SQL", ...}
         - Receives DB observations
         - Eventually returns {"action": "FINISH", "final_answer": "..."}.

    Returns:
      {
        "final_answer": str,
        "history": [ ... step dicts ... ]
      }
    """
    # 1) Name normalization step
    print("\n" + "="*60)
    print("Normalizing player names...") 
    name_norm = normalize_player_name(question)
    print("="*60 + "\n")

    # 2) Schema selection with timing
    # print("\n" + "="*60)
    # print("Getting relevant schema...")
    # schema_start = time.time()
    # schema_selection = choose_schema_for_query(question)
    # reduced_schema_str = build_reduced_schema(schema_selection)
    # reduced_schema_obj = json.loads(reduced_schema_str)
    # schema_duration = time.time() - schema_start
    # print(f"✓ Schema retrieval completed in {schema_duration:.3f}s")
    # print("="*60 + "\n")

    history: List[Dict[str, Any]] = []

    for step in range(1, max_steps + 1):
        context = {
            "question": question,
            # "schema": reduced_schema_obj,
            "history": history,
            "name_normalization": name_norm,  # NEW
        }

        system_prompt = SQL_AGENT_SYSTEM_PROMPT #.replace("{{SCHEMA}}", reduced_schema_str)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(context, indent=2)},
        ]

        raw = call_llm_messages(
            messages=messages,
            model=MODEL,
            max_tokens=2048,
            temperature=0.0,
        )

        clean = extract_json_object(raw)
        try:
            parsed = json.loads(clean)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Agent did not return valid JSON at step {step}.\n"
                f"Raw response:\n{raw}\n\n"
                f"Extracted candidate JSON:\n{clean}"
            ) from e

        action = parsed.get("action")

        if action == "FINISH":
            final_answer = parsed.get("final_answer", "").strip()
            if not final_answer:
                raise ValueError(f"FINISH action missing final_answer: {parsed}")
            if show_progress:
                _print_progress(step, max_steps, "FINISH")
            return {
                "final_answer": final_answer,
                "history": history,
                "name_normalization": name_norm
            }

        if action == "CALL_SQL":
            sql = parsed.get("sql", "")
            if not sql:
                raise ValueError(f"CALL_SQL action missing 'sql': {parsed}")

            thought = parsed.get("thought", "")

            if show_progress:
                _print_progress(step, max_steps, "CALL_SQL", thought)

            # Time the SQL execution
            sql_start = time.time()
            try:
                columns, rows = execute_sql(sql)
                sql_duration = time.time() - sql_start
                print(f"  ⏱️  SQL execution time: {sql_duration:.3f}s")
                
                observation = {
                    "row_count": len(rows),
                    "columns": columns,
                    "rows": rows,
                }
                history.append(
                    {
                        "step": step,
                        "action": "CALL_SQL",
                        "thought": thought,
                        "sql": sql,
                        "observation": observation,
                        # make sql_duration 3 decimal
                        "duration_seconds": f"{sql_duration:.3f}",
                    }
                )
            except Exception as e:
                sql_duration = time.time() - sql_start
                print(f"  ⏱️  SQL execution time (failed): {sql_duration:.3f}s")
                print(f"  ❌ Error: {str(e)}")
                # Surface DB errors back into history so LLM can react
                history.append(
                    {
                        "step": step,
                        "action": "CALL_SQL",
                        "thought": thought,
                        "sql": sql,
                        "error": str(e),
                        "duration_seconds": f"{sql_duration:.3f}",
                    }
                )
            continue

        raise ValueError(f"Unexpected agent action at step {step}: {parsed}")

    # If we get here, the agent never finished
    return {
        "final_answer": "I was not able to confidently answer this question within the step limit.",
        "history": history,
        "name_normalization": name_norm
    }


# ----------------------------------------------------
# Formatting the final output with steps
# ----------------------------------------------------

def format_agent_response(result: Dict[str, Any]) -> str:
    """
    Turn {final_answer, history} into a textual answer plus
    a human-readable summary of steps.
    """
    final_answer = result.get("final_answer", "")
    history = result.get("history", [])
    name_norm = result.get("name_normalization", {})

    lines: List[str] = []

    lines.append("Answer:")
    lines.append(final_answer)
    lines.append("")

    if name_norm:
        players = name_norm.get("players") or []
        if players:
            lines.append("Name normalization:")
            for p in players:
                orig = p.get("original")
                norm = p.get("normalized")
                conf = p.get("confidence")
                reason = p.get("reason")

                lines.append(f"  original:   {orig!r}")
                lines.append(f"  normalized: {norm!r}")
                if conf:
                    lines.append(f"  confidence: {conf!r}")
                if reason:
                    lines.append(f"  reason:     {reason}")
                lines.append("")  # blank line between players


    lines.append("Steps taken:")
    if not history:
        lines.append("  (No SQL steps were executed.)")
        return "\n".join(lines)

    for h in history:
        step = h.get("step")
        action = h.get("action")
        thought = h.get("thought", "")
        sql = h.get("sql", "")
        error = h.get("error")
        obs = h.get("observation")
        duration = h.get("duration_seconds")

        lines.append(f"  Step {step}: {action}")
        if duration is not None:
            lines.append(f"    Duration: {duration}s")
        if thought:
            lines.append(f"    Thought: {thought}")
        if sql:
            lines.append("    SQL:")
            lines.append("      " + sql.replace("\n", "\n      "))

        if error:
            lines.append(f"    Error: {error}")
        elif obs:
            row_count = obs.get("row_count", 0)
            columns = obs.get("columns", [])
            rows = obs.get("rows", [])

            lines.append(f"    Observation: {row_count} row(s)")
            if row_count > 0:
                lines.append(f"      Columns: {columns}")
                for i, r in enumerate(rows[:3]):
                    lines.append(f"      Row {i+1}: {r}")

        lines.append("")

    return "\n".join(lines)


def main():
    example_query = "what team in what season won by the most on average? how mcuh did they lose by?"

    result = run_sql_agent(example_query, max_steps=15, show_progress=True)
    pretty = format_agent_response(result)
    print()
    print(pretty)


if __name__ == "__main__":
    main()
