"""
rag_service.py — RAG retrieval layer for BODH AI
Handles ChromaDB in persistent mode.
One collection per course, scoped by course_id.

Public API:
    ingest(chunks, course_id, source_filename)  — store chunks during PDF upload
    retrieve(query, course_id, k=3)             — fetch top-k chunks before Gemini call
    collection_stats(course_id)                 — chunk count + metadata for /knowledge-status
    delete_course_collection(course_id)         — cleanup if course is deleted

Used by:
    app.py — POST /api/courses/<id>/materials  → ingest()
    app.py — POST /api/ai/chat                 → retrieve()
    app.py — GET  /api/courses/<id>/knowledge-status → collection_stats()
"""

import os
import logging
import chromadb
from chromadb.config import Settings
from embedding_service import embed, embed_batch

log = logging.getLogger(__name__)

# ─── CHROMADB CLIENT (once at startup) ───────────────────────────────────────

_CHROMA_PATH = os.getenv("CHROMA_DB_PATH", "./chroma_db")
_client = None
def _get_client():
    """Return the shared ChromaDB persistent client. Initialised once."""
    global _client
    if _client is None:
        log.info(f"Initialising ChromaDB at: {_CHROMA_PATH}")
        _client = chromadb.PersistentClient(
            path=_CHROMA_PATH,
            settings=Settings(anonymized_telemetry=False)
        )
        log.info("✅ ChromaDB client ready")
    return _client


def _get_collection(course_id: int) -> chromadb.Collection:
    """
    Get or create a ChromaDB collection scoped to a course.
    Collection name: bodh_course_{course_id}
    Uses cosine similarity (best for sentence-transformer vectors).
    """
    client = _get_client()
    name = f"bodh_course_{course_id}"
    collection = client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"}
    )
    return collection


# ─── CHUNKING HELPER ─────────────────────────────────────────────────────────

def chunk_text(text: str, chunk_size: int = 300, overlap: int = 50) -> list[str]:
    """
    Split raw text into overlapping word-level chunks.

    Args:
        text:       Raw extracted text from a PDF page or document.
        chunk_size: Target words per chunk (default 300 ≈ ~400 tokens).
        overlap:    Words to repeat at start of next chunk for context continuity.

    Returns:
        List of chunk strings.

    Why word-level not character-level:
        Sentence transformers work on semantic units. Word boundaries are more
        natural split points than arbitrary character counts.
    """
    words = text.split()
    if not words:
        return []

    chunks = []
    start = 0

    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk = " ".join(words[start:end])
        if chunk.strip():
            chunks.append(chunk.strip())
        start += chunk_size - overlap  # slide with overlap

    return chunks


# ─── PUBLIC API ──────────────────────────────────────────────────────────────

def ingest(chunks: list[str], course_id: int, source_filename: str) -> dict:
    """
    Embed and store a list of text chunks in ChromaDB for a given course.

    Args:
        chunks:          List of text chunks from chunk_text().
        course_id:       The course these chunks belong to (used as collection scope).
        source_filename: Original PDF filename — stored in metadata for reload tracking.

    Returns:
        dict with keys: chunks_stored (int), collection_name (str)

    Called by:
        POST /api/courses/<id>/materials after PyMuPDF extraction + chunking.
    """
    if not chunks:
        raise ValueError("ingest() received empty chunk list.")

    collection = _get_collection(course_id)

    # Embed all chunks in one efficient batch call
    log.info(f"Embedding {len(chunks)} chunks for course {course_id} ...")
    vectors = embed_batch(chunks)

    # Build IDs — unique per course + filename + chunk index
    # Format: course_{id}_{filename}_{index}
    safe_name = source_filename.replace(" ", "_").replace("/", "_")
    ids = [f"course_{course_id}_{safe_name}_{i}" for i in range(len(chunks))]

    # Metadata stored per chunk — used in retrieve() and collection_stats()
    metadatas = [
        {
            "course_id": course_id,
            "source": source_filename,
            "chunk_index": i
        }
        for i in range(len(chunks))
    ]

    # Upsert — safe to re-ingest same file (won't duplicate)
    collection.upsert(
        ids=ids,
        embeddings=vectors,
        documents=chunks,
        metadatas=metadatas
    )

    log.info(f"✅ Ingested {len(chunks)} chunks into collection bodh_course_{course_id}")

    return {
        "chunks_stored": len(chunks),
        "collection_name": f"bodh_course_{course_id}"
    }


def retrieve(query: str, course_id: int, k: int = 3) -> list[dict]:
    """
    Retrieve the top-k most relevant chunks for a student's query.

    Args:
        query:     The student's question string.
        course_id: Scope retrieval to this course's collection only.
        k:         Number of chunks to return (default 3).

    Returns:
        List of dicts, each with:
            - text      (str)   the chunk content
            - source    (str)   original filename
            - score     (float) cosine distance (lower = more similar)
            - chunk_idx (int)   position in original document

    Returns empty list if the collection has no documents yet.

    Called by:
        POST /api/ai/chat — before building the Gemini prompt.
    """
    if not query or not query.strip():
        raise ValueError("retrieve() received empty query.")

    collection = _get_collection(course_id)

    # Guard: don't query an empty collection
    if collection.count() == 0:
        log.warning(f"Collection bodh_course_{course_id} is empty — no material uploaded yet.")
        return []

    query_vector = embed(query.strip())

    results = collection.query(
        query_embeddings=[query_vector],
        n_results=min(k, collection.count()),  # can't request more than exists
        include=["documents", "metadatas", "distances"]
    )

    chunks = []
    for i in range(len(results["documents"][0])):
        chunks.append({
            "text":      results["documents"][0][i],
            "source":    results["metadatas"][0][i].get("source", "unknown"),
            "score":     round(results["distances"][0][i], 4),
            "chunk_idx": results["metadatas"][0][i].get("chunk_index", i)
        })

    log.info(f"Retrieved {len(chunks)} chunks for course {course_id} | query: '{query[:60]}...'")
    return chunks


def collection_stats(course_id: int) -> dict:
    """
    Return stats about a course's knowledge base.

    Returns:
        dict with:
            - course_id       (int)
            - chunk_count     (int)   total chunks stored
            - sources         (list)  unique filenames ingested
            - collection_name (str)

    Called by:
        GET /api/courses/<id>/knowledge-status
    """
    collection = _get_collection(course_id)
    count = collection.count()

    sources = []
    if count > 0:
        # Fetch all metadata to extract unique source filenames
        all_meta = collection.get(include=["metadatas"])
        seen = set()
        for meta in all_meta["metadatas"]:
            src = meta.get("source", "unknown")
            if src not in seen:
                sources.append(src)
                seen.add(src)

    return {
        "course_id":       course_id,
        "chunk_count":     count,
        "sources":         sources,
        "collection_name": f"bodh_course_{course_id}"
    }


def delete_course_collection(course_id: int) -> bool:
    """
    Delete a course's entire ChromaDB collection.
    Call this if a course is deleted from the platform.

    Returns:
        True if deleted, False if collection didn't exist.
    """
    client = _get_client()
    name = f"bodh_course_{course_id}"
    try:
        client.delete_collection(name)
        log.info(f"Deleted ChromaDB collection: {name}")
        return True
    except Exception:
        log.warning(f"Collection {name} not found — nothing to delete.")
        return False