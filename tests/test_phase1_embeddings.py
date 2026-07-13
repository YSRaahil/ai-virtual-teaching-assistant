"""
test_phase1_embeddings.py — Embedding + RAG service tests
----------------------------------------------------------
Tests embedding_service.py and rag_service.py in isolation.
No server, no HTTP — imports directly.

Run: pytest tests/test_phase1_embeddings.py -v
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from embedding_service import embed, embed_batch, embedding_dim
from rag_service import chunk_text, ingest, retrieve, collection_stats

# ── Embedding service tests ───────────────────────────────────────────────────

class TestEmbeddingService:

    def test_embedding_dim(self):
        """Model should output 384-dimensional vectors."""
        dim = embedding_dim()
        assert dim == 384, f"Expected 384, got {dim}"

    def test_embed_returns_vector(self):
        """embed() should return a list of 384 floats."""
        v = embed("What is gradient descent?")
        assert isinstance(v, list)
        assert len(v) == 384
        assert isinstance(v[0], float)

    def test_embed_different_inputs_differ(self):
        """Different inputs should produce different vectors."""
        v1 = embed("What is gradient descent?")
        v2 = embed("What is photosynthesis?")
        assert v1 != v2

    def test_embed_same_input_consistent(self):
        """Same input should produce same vector."""
        v1 = embed("Hello world")
        v2 = embed("Hello world")
        assert v1 == v2

    def test_embed_empty_raises(self):
        """Empty string should raise ValueError."""
        with pytest.raises(ValueError):
            embed("")

    def test_embed_whitespace_raises(self):
        """Whitespace-only string should raise ValueError."""
        with pytest.raises(ValueError):
            embed("   ")

    def test_embed_batch_returns_multiple_vectors(self):
        """embed_batch() should return one vector per input."""
        texts = [
            "Supervised learning uses labeled data.",
            "Unsupervised learning finds hidden patterns.",
            "Reinforcement learning uses rewards."
        ]
        vectors = embed_batch(texts)
        assert len(vectors) == 3
        assert all(len(v) == 384 for v in vectors)

    def test_embed_batch_empty_raises(self):
        """Empty list should raise ValueError."""
        with pytest.raises(ValueError):
            embed_batch([])

    def test_embed_batch_matches_single(self):
        """embed_batch result should match individual embed calls."""
        text = "Machine learning is a subset of AI."
        single = embed(text)
        batch = embed_batch([text])
        assert len(single) == len(batch[0])
        # Values should be very close (floating point)
        diffs = [abs(a - b) for a, b in zip(single, batch[0])]
        assert max(diffs) < 1e-5


# ── RAG service tests ─────────────────────────────────────────────────────────

class TestRagService:

    TEST_COURSE_ID = 9999  # isolated test collection

    TEST_CHUNKS = [
        "Gradient descent minimises the loss function iteratively.",
        "Backpropagation computes gradients using the chain rule.",
        "Learning rate controls the step size during optimisation.",
        "Overfitting occurs when a model memorises training data.",
        "Regularisation techniques like dropout prevent overfitting."
    ]

    def test_chunk_text_basic(self):
        """chunk_text() should split long text into multiple chunks."""
        long_text = "word " * 700
        chunks = chunk_text(long_text, chunk_size=300, overlap=50)
        assert len(chunks) >= 2
        assert all(isinstance(c, str) for c in chunks)
        assert all(len(c) > 0 for c in chunks)

    def test_chunk_text_overlap(self):
        """Chunks should have overlapping content."""
        text = " ".join([f"word{i}" for i in range(400)])
        chunks = chunk_text(text, chunk_size=200, overlap=50)
        assert len(chunks) >= 2
        # Last words of chunk 0 should appear at start of chunk 1
        last_words_chunk0 = set(chunks[0].split()[-10:])
        first_words_chunk1 = set(chunks[1].split()[:10])
        assert len(last_words_chunk0 & first_words_chunk1) > 0

    def test_chunk_text_empty(self):
        """Empty text should return empty list."""
        chunks = chunk_text("")
        assert chunks == []

    def test_chunk_text_short(self):
        """Text shorter than chunk_size should return single chunk."""
        text = "This is a short text."
        chunks = chunk_text(text, chunk_size=300, overlap=50)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_ingest_stores_chunks(self):
        """ingest() should store all chunks and return correct count."""
        result = ingest(
            chunks=self.TEST_CHUNKS,
            course_id=self.TEST_COURSE_ID,
            source_filename="test.pdf"
        )
        assert result["chunks_stored"] == len(self.TEST_CHUNKS)
        assert result["collection_name"] == f"bodh_course_{self.TEST_COURSE_ID}"

    def test_ingest_empty_raises(self):
        """ingest() with empty chunks should raise ValueError."""
        with pytest.raises(ValueError):
            ingest([], course_id=self.TEST_COURSE_ID, source_filename="empty.pdf")

    def test_retrieve_returns_results(self):
        """retrieve() should return relevant chunks for a known query."""
        # Ensure data is ingested first
        ingest(self.TEST_CHUNKS, self.TEST_COURSE_ID, "test.pdf")

        hits = retrieve("how does gradient descent work?", course_id=self.TEST_COURSE_ID, k=2)
        assert len(hits) == 2
        assert all("text" in h for h in hits)
        assert all("score" in h for h in hits)
        assert all("source" in h for h in hits)

    def test_retrieve_semantic_relevance(self):
        """Top retrieved chunk should be semantically related to query."""
        ingest(self.TEST_CHUNKS, self.TEST_COURSE_ID, "test.pdf")

        hits = retrieve("gradient descent optimization", course_id=self.TEST_COURSE_ID, k=1)
        assert len(hits) == 1
        assert "gradient" in hits[0]["text"].lower() or "descent" in hits[0]["text"].lower()

    def test_retrieve_source_metadata(self):
        """Retrieved chunks should carry correct source filename."""
        ingest(self.TEST_CHUNKS, self.TEST_COURSE_ID, "test.pdf")

        hits = retrieve("backpropagation", course_id=self.TEST_COURSE_ID, k=1)
        assert hits[0]["source"] == "test.pdf"

    def test_retrieve_empty_collection_returns_empty(self):
        """retrieve() on a course with no data should return []."""
        result = retrieve("anything", course_id=88888, k=3)
        assert result == []

    def test_retrieve_empty_query_raises(self):
        """retrieve() with empty query should raise ValueError."""
        with pytest.raises(ValueError):
            retrieve("", course_id=self.TEST_COURSE_ID, k=3)

    def test_collection_stats_after_ingest(self):
        """collection_stats() should report correct chunk count and sources."""
        ingest(self.TEST_CHUNKS, self.TEST_COURSE_ID, "test.pdf")

        stats = collection_stats(self.TEST_COURSE_ID)
        assert stats["chunk_count"] == len(self.TEST_CHUNKS)
        assert "test.pdf" in stats["sources"]
        assert stats["course_id"] == self.TEST_COURSE_ID

    def test_ingest_upsert_no_duplicate(self):
        """Re-ingesting the same file should not duplicate chunks."""
        ingest(self.TEST_CHUNKS, self.TEST_COURSE_ID, "test.pdf")
        ingest(self.TEST_CHUNKS, self.TEST_COURSE_ID, "test.pdf")

        stats = collection_stats(self.TEST_COURSE_ID)
        # Should still be 5, not 10
        assert stats["chunk_count"] == len(self.TEST_CHUNKS)