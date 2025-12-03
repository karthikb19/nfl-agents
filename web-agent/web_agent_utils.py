import json
import time
from typing import List, Dict, Tuple, Any
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
import numpy as np
import trafilatura

import psycopg2
from psycopg2.extras import execute_values
from pgvector.psycopg2 import register_vector


CHUNK_DIM = 384
CHUNK_SIZE = 512
CHUNK_OVERLAP = 64 


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



def retrieve_top_k_chunks(refined_queries: List[str], k: int = 5, model: SentenceTransformer = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")) -> List[Dict[str, Any]]: 
    print(f"   → Encoding queries: {refined_queries}")
    all_query_embeddings = model.encode(refined_queries)
    
    # focus on just the first one
    query_embed = all_query_embeddings[0]
    emb_list = query_embed.astype(float).tolist()
    
    db_url = get_db_url()
    if "?pgbouncer=" in db_url:
        db_url = db_url.split("?pgbouncer=")[0]
    print(f"   → Connecting to database: {db_url}")

    conn = psycopg2.connect(db_url)
    register_vector(conn)
    cursor = conn.cursor()
    closest_chunks = []
    try:
        # Check row count
        cursor.execute("SELECT COUNT(*) FROM web_chunks;")
        count = cursor.fetchone()[0]
        print(f"   → Database contains {count} chunks")

        # 3) Now run the distance query
        # NOTE: There's a bug with pgvector + connection pooler where ORDER BY returns 0 rows
        # Workaround: fetch all rows with distances and sort in Python
        sql = """
            SELECT
                url,
                chunk_index,
                chunk_text,
                (embedding <=> %s) AS distance
            FROM public.web_chunks;
        """
        print(f"   → Retrieving top {k} most similar chunks...")

        # Convert to numpy array - pgvector's register_vector expects numpy arrays
        query_vector = np.array(emb_list, dtype=np.float32)
        
        cursor.execute(sql, (query_vector,))
        all_rows = cursor.fetchall()
        
        # Sort by distance in Python and take top k
        sorted_rows = sorted(all_rows, key=lambda x: x[3])[:k]
        rows = sorted_rows
        print(f"   → Found {len(rows)} relevant chunks")

    except Exception as e:
        print("Error retrieving:", e)
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
    # try:
    #     sql = """
    #         SELECT
    #             url,
    #             chunk_index,
    #             chunk_text,
    #             (embedding <=> %s::vector) AS distance
    #         FROM web_chunks
    #         WHERE (embedding <=> %s::vector) < %s
    #         ORDER BY embedding <=> %s::vector
    #         LIMIT %s;
    #     """

    #     cursor.execute(
    #         sql,
    #         (
    #             emb_str,            # for SELECT distance
    #             emb_str,            # for WHERE distance comparison
    #             1, # e.g., 0.3 for cosine distance cutoff
    #             emb_str,            # for ORDER BY
    #             k                   # top-k rows
    #         )
    #     )
    #     rows = cursor.fetchall()
    #     print(f"   → Retrieved {len(rows)} chunks from database")
    #     closest_chunks =  [
    #         {
    #             "url": row[0],
    #             "chunk_index": row[1],
    #             "chunk_text": row[2],
    #             "distance": float(row[3]),
    #         }
    #         for row in rows
    #     ]
    # except Exception as e:
    #     print(f"Error retrieving top k chunks: {e}")
    #     import traceback
    #     traceback.print_exc()
    # finally:
    #     cursor.close()
    #     conn.close()

    # return closest_chunks