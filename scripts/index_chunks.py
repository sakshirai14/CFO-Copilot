#!/usr/bin/env python3
"""scripts/index_chunks.py

Phase 3 Indexing Pipeline:
1. Deterministically chunks public filings, financial statement tables, and tenant documents.
2. Computes 384-dimensional dense embeddings using BAAI/bge-small-en-v1.5.
3. Stores chunks and vector embeddings idempotently in PostgreSQL with pgvector HNSW indexing.
"""

import argparse
import sys
import time
from pathlib import Path
import psycopg2

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import get_settings
from app.data.chunker import run_chunking_pipeline
from fastembed import TextEmbedding

DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"


def embed_and_store_chunks(is_test: bool = False):
    settings = get_settings()
    db_name = settings.POSTGRES_TEST_DB if is_test else settings.POSTGRES_DB
    print(f"[indexer] Indexing chunks and computing embeddings on '{db_name}'...")

    # Step 1: Run deterministic chunking
    chunk_stats = run_chunking_pipeline(is_test=is_test)

    # Step 2: Compute and update embeddings for all chunks missing embeddings
    conn = psycopg2.connect(**settings.get_connection_params(role="rw", is_test=is_test))
    cur = conn.cursor()

    try:
        model = TextEmbedding(model_name=DEFAULT_MODEL)
        tenants = [t.strip() for t in settings.TENANTS.split(",") if t.strip()]

        # 2a. Public chunks
        cur.execute("SELECT chunk_id, text FROM chunks WHERE embedding IS NULL AND tenant_id IS NULL;")
        public_rows = cur.fetchall()
        if public_rows:
            print(f"[indexer] Computing embeddings for {len(public_rows)} public chunks...")
            p_ids = [r[0] for r in public_rows]
            p_texts = [r[1] for r in public_rows]
            p_embs = list(model.embed(p_texts, batch_size=32))
            for cid, emb in zip(p_ids, p_embs):
                vec_str = "[" + ",".join(f"{x:.6f}" for x in emb) + "]"
                cur.execute("UPDATE chunks SET embedding = %s::vector WHERE chunk_id = %s;", (vec_str, cid))
            conn.commit()

        # 2b. Tenant chunks
        for t in tenants:
            cur.execute("SET LOCAL app.current_tenant = %s;", (t,))
            cur.execute("SELECT chunk_id, text FROM chunks WHERE embedding IS NULL AND tenant_id = %s;", (t,))
            tenant_rows = cur.fetchall()
            if tenant_rows:
                print(f"[indexer] Computing embeddings for {len(tenant_rows)} tenant chunks ({t})...")
                t_ids = [r[0] for r in tenant_rows]
                t_texts = [r[1] for r in tenant_rows]
                t_embs = list(model.embed(t_texts, batch_size=32))
                for cid, emb in zip(t_ids, t_embs):
                    vec_str = "[" + ",".join(f"{x:.6f}" for x in emb) + "]"
                    cur.execute("UPDATE chunks SET embedding = %s::vector WHERE chunk_id = %s;", (vec_str, cid))
                conn.commit()

        cur.execute("SELECT count(*), count(embedding) FROM chunks;")
        total_chunks, embedded_chunks = cur.fetchone()
        print(f"[indexer] Indexing complete: {embedded_chunks}/{total_chunks} chunks embedded.")

    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run chunking and embedding indexer")
    parser.add_argument("--test", action="store_true", help="Index test database")
    args = parser.parse_args()
    embed_and_store_chunks(is_test=args.test)

