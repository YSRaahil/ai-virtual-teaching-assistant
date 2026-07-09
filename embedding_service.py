"""
embedding_service.py — Embedding layer for BODH AI RAG pipeline
----------------------------------------------------------------
Loads all-MiniLM-L6-v2 once at module import (startup), not per request.
Exposes a single function: embed(text) -> list[float]

Used by:
    rag_service.py — to embed chunks during ingestion
    rag_service.py — to embed student queries during retrieval

Model: sentence-transformers/all-MiniLM-L6-v2
    - 384-dimensional output vectors
    - ~80MB on disk, ~90MB RAM
    - No API key needed — runs fully local
    - Fast: ~10ms per sentence on CPU
"""

import logging
from sentence_transformers import SentenceTransformer

log = logging.getLogger(__name__)

# ─── MODEL LOAD (once at startup) ────────────────────────────────────────────
# This runs when the module is first imported — i.e. when app.py starts.
# Never reload inside a request handler.

_MODEL_NAME = "all-MiniLM-L6-v2"
_model: SentenceTransformer | None = None


def _load_model() -> SentenceTransformer:
    """Load the embedding model. Called once at startup."""
    global _model
    if _model is None:
        log.info(f"Loading embedding model: {_MODEL_NAME} ...")
        _model = SentenceTransformer(_MODEL_NAME)
        log.info(f"✅ Embedding model loaded — output dim: {_model.get_sentence_embedding_dimension()}")
    return _model


# Load immediately on import
_load_model()


# ─── PUBLIC API ──────────────────────────────────────────────────────────────

def embed(text: str) -> list[float]:
    """
    Embed a single string into a 384-dimensional vector.

    Args:
        text: Any string — a document chunk or a student query.

    Returns:
        list[float] of length 384.

    Usage:
        from embedding_service import embed
        vector = embed("What is backpropagation?")
    """
    if not text or not text.strip():
        raise ValueError("embed() received empty text — check input before calling.")

    model = _load_model()
    vector = model.encode(text.strip(), convert_to_numpy=True)
    return vector.tolist()


def embed_batch(texts: list[str]) -> list[list[float]]:
    """
    Embed a list of strings in one efficient batch call.
    Faster than calling embed() in a loop for large chunk sets.

    Args:
        texts: List of strings to embed.

    Returns:
        List of 384-dim vectors in the same order as input.

    Usage:
        from embedding_service import embed_batch
        vectors = embed_batch(["chunk 1 text", "chunk 2 text", "chunk 3 text"])
    """
    if not texts:
        raise ValueError("embed_batch() received empty list.")

    cleaned = [t.strip() for t in texts if t and t.strip()]
    if not cleaned:
        raise ValueError("embed_batch() — all texts were empty after stripping.")

    model = _load_model()
    vectors = model.encode(cleaned, convert_to_numpy=True, batch_size=32, show_progress_bar=False)
    return vectors.tolist()


def embedding_dim() -> int:
    """
    Return the output dimension of the current model (384 for all-MiniLM-L6-v2).
    Useful for sanity checks and logging.
    """
    return _load_model().get_sentence_embedding_dimension()