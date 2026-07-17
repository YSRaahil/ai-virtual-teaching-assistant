"""
embedding_service.py — Embedding layer for BODH AI RAG pipeline
----------------------------------------------------------------
Model is lazy-loaded on first use — NOT at startup.
This keeps Render Free tier memory under 512MB on cold start.
The model loads only when a PDF is uploaded or RAG retrieval runs.

Model: all-MiniLM-L6-v2
    - 384-dimensional output vectors
    - ~90MB RAM when loaded
    - No API key needed — runs fully local
"""

import logging

log = logging.getLogger(__name__)

_MODEL_NAME = "all-MiniLM-L6-v2"
_model = None  # lazy — not loaded at import time


def _get_model():
    """
    Load the embedding model on first call only.
    Subsequent calls return the cached instance.
    """
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        log.info(f"Loading embedding model: {_MODEL_NAME} ...")
        _model = SentenceTransformer(_MODEL_NAME)
        log.info(f"Embedding model loaded — output dim: {_model.get_sentence_embedding_dimension()}")
    return _model


def embed(text: str) -> list:
    """
    Embed a single string into a 384-dimensional vector.
    """
    if not text or not text.strip():
        raise ValueError("embed() received empty text — check input before calling.")
    model = _get_model()
    vector = model.encode(text.strip(), convert_to_numpy=True)
    return vector.tolist()


def embed_batch(texts: list) -> list:
    """
    Embed a list of strings in one efficient batch call.
    """
    if not texts:
        raise ValueError("embed_batch() received empty list.")
    cleaned = [t.strip() for t in texts if t and t.strip()]
    if not cleaned:
        raise ValueError("embed_batch() — all texts were empty after stripping.")
    model = _get_model()
    vectors = model.encode(cleaned, convert_to_numpy=True, batch_size=32, show_progress_bar=False)
    return vectors.tolist()


def embedding_dim() -> int:
    """Return the output dimension of the current model (384)."""
    return _get_model().get_sentence_embedding_dimension()