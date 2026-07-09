# test_phase1.py — run this in your project root
from embedding_service import embed, embedding_dim
from rag_service import chunk_text, ingest, retrieve

# Test 1: embedding
v = embed("What is gradient descent?")
assert len(v) == 384
print(f"✅ embed() works — dim: {len(v)}")

# Test 2: chunking
chunks = chunk_text("word " * 700, chunk_size=300, overlap=50)
print(f"✅ chunk_text() works — {len(chunks)} chunks from 700 words")

# Test 3: ingest + retrieve
result = ingest(["Gradient descent minimises the loss function iteratively.",
                 "Backpropagation computes gradients using the chain rule.",
                 "Learning rate controls the step size during optimisation."],
                course_id=999, source_filename="test.pdf")
print(f"✅ ingest() works — {result['chunks_stored']} chunks stored")

hits = retrieve("how does gradient descent work?", course_id=999, k=2)
print(f"✅ retrieve() works — top hit: '{hits[0]['text'][:60]}...'")