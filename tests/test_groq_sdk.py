"""
test_groq_sdk.py — Groq SDK tests
------------------------------------
Uses mocked responses in CI to avoid real API calls.
Real API calls only run when GROQ_API_KEY is available and valid.

Run: pytest tests/test_groq_sdk.py -v
"""

import pytest
import os
import sys
from unittest.mock import Mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


def _make_mock_client():
    mock_client = Mock()
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = "OK"
    mock_response.choices[0].delta = Mock()
    mock_response.choices[0].delta.content = "OK"
    mock_response.model = "llama-3.3-70b-versatile"
    mock_client.chat.completions.create = Mock(return_value=mock_response)
    return mock_client, mock_response


@pytest.fixture(scope="module")
def groq_client():
    try:
        from groq import Groq
    except ImportError:
        pytest.skip("groq SDK not installed")

    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key or api_key.strip() == "***" or len(api_key) < 10:
        mock_client, _ = _make_mock_client()
        return mock_client

    return Groq(api_key=api_key)


@pytest.fixture(scope="module")
def is_mocked():
    api_key = os.getenv("GROQ_API_KEY", "")
    return not api_key or api_key.strip() == "***" or len(api_key) < 10


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

    def test_streaming(self, groq_client, is_mocked):
        if is_mocked:
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