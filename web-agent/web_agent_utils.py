import json
import time
from typing import List, Dict, Any
import requests
from utils.config import (
    MODEL,
    OPENROUTER_URL,
    get_db_url,
    get_openrouter_headers,
)
from .prompts import (
    REFINE_QUERY_PROMPT
)
from utils.llm_parsing import extract_json_object
from sentence_transformers import SentenceTransformer
from ddgs import DDGS
import trafilatura


db_url = get_db_url()
HEADERS = get_openrouter_headers()
model = SentenceTransformer('all-MiniLM-L6-v2')

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

def process_query(query: str) -> List[Dict[str, Any]]:
    system_prompt = REFINE_QUERY_PROMPT
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": query},
    ]
    response = call_llm_messages(messages)
    clean = extract_json_object(response)
    try:
        parsed = json.loads(clean)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM did not return valid JSON: {clean}") from e
    
    return parsed.get("queries", [])

def search_web(refined_queries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    ddgs_results = []
    for r in refined_queries:
        with DDGS() as ddgs:
            results = list(ddgs.text(r["query"], max_results=5))
            for result in results:
                ddgs_results.append(result)
    remove_duplicates_results = []
    for result in ddgs_results:
        if result not in remove_duplicates_results:
            remove_duplicates_results.append(result) 
    return remove_duplicates_results


def chunk_result(result: Dict[str, Any]) -> List[str]:
    title = result.get("title")
    url = result.get("href")
    ddgs_description = result.get("body")
    print(url)
    html = trafilatura.fetch_url(url)
    text = trafilatura.extract(html)
    print(text)
    return [] 