"""Embedding service for semantic search using sentence-transformers.

Lazy-loads the model on first use. Uses the same model as the vector DB:
  sentence-transformers/paraphrase-multilingual-mpnet-base-v2 (768 dim)
"""

from __future__ import annotations

import logging
import threading

logger = logging.getLogger(__name__)

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
EMBEDDING_DIM = 768

_model = None
_lock = threading.Lock()


def get_model():
    """Lazy-load the SentenceTransformer model (thread-safe)."""
    global _model
    if _model is not None:
        return _model
    with _lock:
        if _model is not None:
            return _model
        logger.info("Loading embedding model: %s", MODEL_NAME)
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(MODEL_NAME)
        logger.info("Embedding model loaded")
        return _model


def embed_query(text: str) -> list[float]:
    """Compute a normalized embedding vector for a search query."""
    model = get_model()
    return model.encode(text, normalize_embeddings=True).tolist()
