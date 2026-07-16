"""
test_groq_sdk.py — Groq SDK tests
------------------------------------
Uses mocked responses in CI when GROQ_API_KEY is unavailable.
Real API calls only run when a valid key is present locally.

Run: pytest tests/test_groq_sdk.py -v
"""

import pytest
import os
import sys
from unittest.mock import Mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

# Skip entire module if key is missing or masked
_key = os.getenv("GROQ_API_KEY", "").strip()
if not _key or _key in ("***", "REPLACE_ME") or len(_key) < 20:
    pytest.skip(
        "GROQ_API_KEY not configured — skipping Groq SDK tests",
        allow_module_level=True
    )


def _is_valid_key(key: str) -> bool:
    """Check if API key is real — not masked, not empty, not placeholder."""
    if not key:
        return False
    key = key.strip()
    if key == "***":
        return False
    if key.startswith("***") or key.endswith("***"):
        return False
    if len(key) < 20:
        return False
    return True


def _make_mock_client():
    """Build a mock Groq client."""
    mock_client = Mock()
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = "OK"
    mock_response.choices[0].delta = Mock()
    mock_response.choices[0].delta.content = "OK"
    mock_response.model = "llama-3.3-70b-versatile"
    mock_client.chat.completions.create = Mock(return_value=mock_response)
    return mock_client


@pytest.fixture(scope="module")
def use_mock():
    """True if we should use mock instead of real API."""
    return not _is_valid_key(os.getenv("GROQ_API_KEY", ""))


@pytest.fixture(scope="module")
def groq_client(use_mock):
    """
    Return mock client in CI (no valid key),
    real Groq client when running locally with a valid key.
    """
    if use_mock:
        return _make_mock_client()

    try:
        from groq import Groq
    except ImportError:
        pytest.skip("groq SDK not installed")

    return Groq(api_key=os.getenv("GROQ_API_KEY"))


class TestGroqSDK:

    def test_client_created(self, groq_client):
        assert groq_client is not None

    def test_basic_completion(self, groq_client):
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
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": "Say OK"}],
            max_tokens=10
        )
        assert "llama" in response.model.lower()

    def test_streaming(self, groq_client, use_mock):
        if use_mock:
            stream_chunk = Mock()
            stream_chunk.choices = [Mock()]
            stream_chunk.choices[0].delta.content = "OK"
            groq_client.chat.completions.create.return_value = [stream_chunk]

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