import json
import time
from typing import List, Dict, Tuple, Any, Optional
import requests
from utils.config import (
    MODEL,
    OPENROUTER_URL,
    get_db_url,
    get_openrouter_headers,
)
from .prompts import (
    REFINE_QUERY_PROMPT,
    WEB_AGENT_PROMPT
)
from utils.llm_parsing import extract_json_object
from sentence_transformers import SentenceTransformer
from ddgs import DDGS
import numpy as np
import trafilatura

import psycopg2
from psycopg2.extras import execute_values


CHUNK_DIM = 384
CHUNK_SIZE = 512
CHUNK_OVERLAP = 64 


HEADERS = get_openrouter_headers()

def _format_embedding_for_sql(embedding: np.ndarray) -> str:
    """
    Format a 1D embedding array as a pgvector literal, e.g. '[0.1,0.2,...]'.
    """
    emb_list = embedding.astype(float).tolist()
    return "[" + ",".join(f"{float(x):.7f}" for x in emb_list) + "]"

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


def process_text_into_chunks_with_embeddings(tokenizer, model, result: Dict[str, Any]) -> Tuple[str, List[str], np.ndarray]:
    url = result.get("href")
    html = trafilatura.fetch_url(url)
    text = trafilatura.extract(html)
    print(f"Text for {url}: {text}")
    if text is None:
        print(f"No text found for {url} into 0 chunks")
        return url, [], np.array([])

    encoded_input = tokenizer(text=text, return_offsets_mapping=True, add_special_tokens=False, return_attention_mask=False, return_token_type_ids=False)
    offsets: List[Tuple[int, int]] = encoded_input.get("offset_mapping", [])
    chunks = []
    start_idx, end_idx = 0, len(offsets) - 1
    while True:
        l_start = offsets[start_idx][0]
        r_idx = min(end_idx, start_idx + CHUNK_SIZE - 1)
        r_end = offsets[r_idx][1]
        chunks.append(text[l_start:r_end])
        if r_idx == end_idx:
            break
        start_idx = min(end_idx, start_idx + (CHUNK_SIZE - CHUNK_OVERLAP))
    print(f"Chunked {url} into {len(chunks)} chunks")
    embeddings = _generate_embeddings_per_chunk(tokenizer, model, chunks)
    return url, chunks, embeddings

def _generate_embeddings_per_chunk(tokenizer, model, chunks: List[str]) -> np.ndarray:
    embeddings = model.encode(chunks)
    return embeddings


def insert_embeddings_into_db(url: str, chunks: List[str], embeddings: np.ndarray):
    assert embeddings.shape[1] == CHUNK_DIM, f"expected dim {CHUNK_DIM}, got {embeddings.shape[1]}"
    assert len(chunks) == embeddings.shape[0], "chunks and embeddings length mismatch"

    db_url = get_db_url()
    if '?pgbouncer=' in db_url:
        db_url = db_url.split('?pgbouncer=')[0]
    
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()
    try:
        records = []
        for idx, (chunk_text, embed) in enumerate(zip(chunks, embeddings)):
            emb_list = embed.tolist()
            emb_str = "[" + ",".join(f"{float(x):.7f}" for x in emb_list) + "]"
            records.append((url, idx, chunk_text, emb_str))
        
        sql = """
        INSERT INTO web_chunks (url, chunk_index, chunk_text, embedding)
        VALUES %s
        ON CONFLICT (url, chunk_index) DO UPDATE
        SET
          chunk_text = EXCLUDED.chunk_text,
          embedding  = EXCLUDED.embedding;
        """
        execute_values(
            cursor,
            sql,
            records,
            template="(%s, %s, %s, %s::vector)"
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error inserting embeddings into DB: {e}")
        raise 
    finally:
        cursor.close()
        conn.close()

def retrieve_top_k_chunks(
    refined_queries: List[str],
    k: int = 5,
    model: Optional[SentenceTransformer] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieve top-k most similar chunks for the first refined query using pgvector.

    Strategy:
        1. Use a CTE to bind the query vector as %s::vector (dimension 384).
        2. Primary path: ORDER BY distance LIMIT k in SQL.
        3. If 0 rows returned but table has data, fall back to Python-side sort.
    """
    if not refined_queries:
        print("No refined queries provided.")
        return []

    if model is None:
        model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

    print(f"   → Encoding queries: {refined_queries}")
    all_query_embeddings = model.encode(refined_queries)
    query_embed = np.array(all_query_embeddings[0], dtype=np.float32)

    emb_str = _format_embedding_for_sql(query_embed)

    db_url = get_db_url()
    if "?pgbouncer=" in db_url:
        db_url = db_url.split("?pgbouncer=")[0]
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()
    rows: List[Tuple[Any, ...]] = []

    try:
        # Optional: set IVFFLAT probes for better recall
        try:
            cursor.execute("SET LOCAL ivfflat.probes = 10;")
        except Exception as e:
            # Not fatal if the extension isn't installed or setting isn't allowed
            print(f"   → Warning: could not SET ivfflat.probes: {e}")

        cursor.execute("SELECT COUNT(*) FROM public.web_chunks;")
        count = cursor.fetchone()[0]
        print(f"   → Database contains {count} chunks")

        if count == 0:
            print("   → No chunks in DB, skipping similarity search")
            return []

        # --- Primary (preferred) path: ORDER BY distance in SQL ---
        sql_primary = """
            WITH q AS (
                SELECT %s::vector AS v
            )
            SELECT
                url,
                chunk_index,
                chunk_text,
                (embedding <=> q.v) AS distance
            FROM public.web_chunks, q
            ORDER BY distance
            LIMIT %s;
        """

        print(f"   → Retrieving top {k} most similar chunks via SQL ORDER BY...")
        cursor.execute(sql_primary, (emb_str, k))
        rows = cursor.fetchall()
        print(f"   → Primary query returned {len(rows)} rows")

        # If ORDER BY bug hits: table has data but the query returned nothing
        if len(rows) == 0 and count > 0:
            print("   ⚠️ Suspected pgvector + pooler ORDER BY bug. Falling back to Python-side sort.")

            sql_fallback = """
                WITH q AS (
                    SELECT %s::vector AS v
                )
                SELECT
                    url,
                    chunk_index,
                    chunk_text,
                    (embedding <=> q.v) AS distance
                FROM public.web_chunks, q;
            """
            cursor.execute(sql_fallback, (emb_str,))
            all_rows = cursor.fetchall()
            print(f"   → Fallback query returned {len(all_rows)} rows")

            all_rows_sorted = sorted(all_rows, key=lambda r: r[3])
            rows = all_rows_sorted[:k]
            print(f"   → After Python sort, using top {len(rows)} rows")

    except Exception as e:
        print("Error retrieving top-k chunks:", e)
        print(f"Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        rows = []
    finally:
        cursor.close()
        conn.close()

    closest_chunks = [
        {
            "url": row[0],
            "chunk_index": row[1],
            "chunk_text": row[2],
            "distance": float(row[3]),
        }
        for row in rows
    ]
    return closest_chunks


def generate_prompt(original_query: str, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    system_prompt = WEB_AGENT_PROMPT
    if not chunks:
        context_str = "No web snippets were retrieved for this question."
    else:
        lines = []
        for i, ch in enumerate(chunks):
            url = ch.get("url", "Unknown URL")
            ch_idx = ch.get("chunk_index", "N/A")
            ch_text = ch.get("chunk_text", "")
            lines.append(
                f"[Source {i}] URL: {url}\n"
                f"Chunk index: {ch_idx}\n"
                f"Content:\n{ch_text}\n"
            )
        context_str = "\n\n".join(lines)
    user_content = f"""User question:
    {original_query}

    Retrieved web context:
    {context_str}

    Now, using the web context above (and clearly marking any speculation that goes beyond it), write the best possible answer to the user question."""
        
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]


def generate_answer(messages):
    response = call_llm_messages(messages)
    return response