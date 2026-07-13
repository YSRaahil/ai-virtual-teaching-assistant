"""
test_groq_sdk.py — Groq SDK connectivity tests
------------------------------------------------
Tests that the Groq client is configured and reachable.
No server required — imports directly.

Run: pytest tests/test_groq_sdk.py -v
"""

import pytest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

@pytest.fixture(scope="module")
def groq_client():
    try:
        from groq import Groq
    except ImportError:
        pytest.skip("groq-sdk not installed. Install with `pip install groq`")    
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or api_key == "*** ":    
        pytest.skip("GROQ_API_KEY not set in .env")
    return Groq(api_key=api_key)


class TestGroqSDK:

    def test_client_created(self, groq_client):
        """Groq client should initialise without error."""
        assert groq_client is not None

    def test_basic_completion(self, groq_client):
        """Basic chat completion should return a non-empty response."""
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": "Say OK"}],
            max_tokens=10
        )
        assert response is not None
        content = response.choices[0].message.content
        assert isinstance(content, str)
        assert len(content) > 0

    def test_response_structure(self, groq_client):
        """Response should have expected structure."""
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": "Say OK"}],
            max_tokens=10
        )
        assert hasattr(response, "choices")
        assert len(response.choices) > 0
        assert hasattr(response.choices[0], "message")
        assert hasattr(response.choices[0].message, "content")

    def test_model_name(self, groq_client):
        """Response should confirm correct model was used."""
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": "Say OK"}],
            max_tokens=10
        )
        assert "llama" in response.model.lower()

    def test_streaming(self, groq_client):
        """Streaming should yield multiple chunks."""
        chunks = []
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": "Count to 3"}],
            max_tokens=20,
            stream=True
        )
        for chunk in response:
            if chunk.choices[0].delta.content:
                chunks.append(chunk.choices[0].delta.content)

        assert len(chunks) > 0
        full_response = "".join(chunks)
        assert len(full_response) > 0