"""Generiert Embeddings fuer alle esoteric_items mit sentence-transformers + pgvector."""
import os
import sys
import time
import psycopg
import numpy as np
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent / ".env")
TARGET_DB = os.getenv("TARGET_DB", "postgresql://quantec:quantec_vec_2026@localhost:5434/quantec_vector")

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
BATCH_SIZE = 64
DIMENSIONS = 768


def enrich_text(text_primary: str | None, text_full: str | None, category_name: str) -> str:
    base = text_primary or ""
    if text_full and len(text_full) > len(base) + 20:
        base = text_full
    if not base:
        return category_name
    if len(base) < 30:
        return f"{category_name}: {base}"
    return base


def main():
    print(f"Lade Modell: {MODEL_NAME}")
    t0 = time.time()

    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(MODEL_NAME)
    print(f"Modell geladen in {time.time() - t0:.1f}s")

    conn = psycopg.connect(TARGET_DB)

    # Zaehle Items ohne Embedding
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM esoteric_item WHERE embedding IS NULL")
        total = cur.fetchone()[0]
    print(f"Zu verarbeiten: {total:,} Items")

    if total == 0:
        print("Alle Items haben bereits Embeddings.")
        conn.close()
        return

    # Batch-Verarbeitung
    processed = 0
    t_start = time.time()

    while True:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, text_primary, text_full, category_name
                FROM esoteric_item
                WHERE embedding IS NULL
                ORDER BY id
                LIMIT %s
            """, (BATCH_SIZE,))
            batch = cur.fetchall()

        if not batch:
            break

        ids = [r[0] for r in batch]
        texts = [enrich_text(r[1], r[2], r[3]) for r in batch]

        embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)

        with conn.cursor() as cur:
            for item_id, emb in zip(ids, embeddings):
                cur.execute(
                    "UPDATE esoteric_item SET embedding = %s WHERE id = %s",
                    (emb.tolist(), item_id),
                )
        conn.commit()

        processed += len(batch)
        elapsed = time.time() - t_start
        rate = processed / elapsed if elapsed > 0 else 0
        eta = (total - processed) / rate if rate > 0 else 0
        pct = processed / total * 100

        if processed % (BATCH_SIZE * 10) == 0 or processed >= total:
            print(f"  {processed:>7,}/{total:,} ({pct:5.1f}%) | {rate:.0f} items/s | ETA {eta:.0f}s")

    elapsed = time.time() - t_start
    print(f"\n=== Embeddings abgeschlossen ===")
    print(f"  {processed:,} Items in {elapsed:.1f}s ({processed/elapsed:.0f} items/s)")

    # HNSW-Index erstellen
    print("Erstelle HNSW-Index...")
    t_idx = time.time()
    with conn.cursor() as cur:
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_ei_embedding ON esoteric_item
            USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 200)
        """)
    conn.commit()
    print(f"  HNSW-Index in {time.time() - t_idx:.1f}s erstellt")

    conn.close()
    print("Fertig.")


if __name__ == "__main__":
    main()
