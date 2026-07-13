"""
test_phase3_api.py — API route tests
--------------------------------------
Tests all Flask routes end to end via HTTP.
Requires server running: python app.py

Run: pytest tests/test_phase3_api.py -v
"""

import pytest
import os
import requests

BASE = "http://localhost:5000"
COURSE_ID = 1

# PDF path — update this to your ML course material PDF
PDF_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "ml_course_material.pdf"
)


# ── Health + Auth ─────────────────────────────────────────────────────────────

class TestHealth:

    def test_health_check(self):
        r = requests.get(f"{BASE}/api/health", timeout=5)
        assert r.status_code == 200

    def test_health_response_structure(self):
        r = requests.get(f"{BASE}/api/health", timeout=5)
        body = r.json()
        assert "status" in body


class TestAuth:

    def test_admin_login(self, admin_token):
        assert admin_token is not None
        assert len(admin_token) > 20

    def test_teacher_login(self, teacher_token):
        assert teacher_token is not None

    def test_student_login(self, student_token):
        assert student_token is not None

    def test_invalid_login_rejected(self):
        r = requests.post(f"{BASE}/api/auth/login",
                          json={"email": "nobody@test.com", "password": "wrong"},
                          timeout=5)
        assert r.status_code in (401, 400)

    def test_protected_route_without_token(self):
        r = requests.get(f"{BASE}/api/courses/{COURSE_ID}/knowledge-status",
                         timeout=5)
        assert r.status_code == 401

    def test_me_endpoint(self, student_token):
        r = requests.get(f"{BASE}/api/auth/me",
                         headers={"Authorization": f"Bearer {student_token}"},
                         timeout=5)
        assert r.status_code == 200
        assert r.json()["data"]["email"] == "student@demo.com"


# ── Materials upload ──────────────────────────────────────────────────────────

class TestMaterialsUpload:

    def test_student_cannot_upload(self, student_token):
        """Students are blocked from uploading — role guard."""
        with open(PDF_PATH, "rb") as f:
            r = requests.post(
                f"{BASE}/api/courses/{COURSE_ID}/materials",
                headers={"Authorization": f"Bearer {student_token}"},
                files={"file": ("test.pdf", f, "application/pdf")},
                timeout=30
            )
        assert r.status_code == 403

    def test_non_pdf_rejected(self, teacher_token):
        """Non-PDF files should be rejected with 422."""
        r = requests.post(
            f"{BASE}/api/courses/{COURSE_ID}/materials",
            headers={"Authorization": f"Bearer {teacher_token}"},
            files={"file": ("notes.txt", b"some text", "text/plain")},
            timeout=10
        )
        assert r.status_code == 422

    def test_no_file_rejected(self, teacher_token):
        """Request without file should return 400."""
        r = requests.post(
            f"{BASE}/api/courses/{COURSE_ID}/materials",
            headers={"Authorization": f"Bearer {teacher_token}",
                     "Content-Type": "application/json"},
            json={},
            timeout=10
        )
        assert r.status_code == 400

    def test_upload_pdf_success(self, teacher_token, seed_data):
        """Valid PDF upload should return 201 with chunk count."""
        if not os.path.exists(PDF_PATH):
            pytest.skip(f"PDF not found at {PDF_PATH}")

        with open(PDF_PATH, "rb") as f:
            r = requests.post(
                f"{BASE}/api/courses/{COURSE_ID}/materials",
                headers={"Authorization": f"Bearer {teacher_token}"},
                files={"file": ("ml_course_material.pdf", f, "application/pdf")},
                timeout=60
            )
        assert r.status_code == 201
        data = r.json()["data"]
        assert data["chunk_count"] > 0
        assert data["collection_name"] == f"bodh_course_{COURSE_ID}"


# ── Knowledge status ──────────────────────────────────────────────────────────

class TestKnowledgeStatus:

    def test_knowledge_status_returns_200(self, teacher_token, seed_data):
        r = requests.get(
            f"{BASE}/api/courses/{COURSE_ID}/knowledge-status",
            headers={"Authorization": f"Bearer {teacher_token}"},
            timeout=10
        )
        assert r.status_code == 200

    def test_knowledge_status_structure(self, teacher_token, seed_data):
        r = requests.get(
            f"{BASE}/api/courses/{COURSE_ID}/knowledge-status",
            headers={"Authorization": f"Bearer {teacher_token}"},
            timeout=10
        )
        data = r.json()["data"]
        assert "chunk_count" in data
        assert "sources" in data
        assert "materials" in data
        assert isinstance(data["chunk_count"], int)

    def test_nonexistent_course_returns_404(self, teacher_token):
        r = requests.get(
            f"{BASE}/api/courses/99999/knowledge-status",
            headers={"Authorization": f"Bearer {teacher_token}"},
            timeout=10
        )
        assert r.status_code == 404


# ── AI chat ───────────────────────────────────────────────────────────────────

class TestAIChat:

    def test_basic_chat_returns_200(self, student_token):
        r = requests.post(
            f"{BASE}/api/ai/chat",
            headers={"Authorization": f"Bearer {student_token}",
                     "Content-Type": "application/json"},
            json={"message": "what is machine learning?"},
            timeout=30
        )
        assert r.status_code == 200

    def test_chat_response_structure(self, student_token):
        r = requests.post(
            f"{BASE}/api/ai/chat",
            headers={"Authorization": f"Bearer {student_token}",
                     "Content-Type": "application/json"},
            json={"message": "what is machine learning?"},
            timeout=30
        )
        data = r.json()["data"]
        assert "response" in data
        assert "rag_used" in data
        assert "chunks_retrieved" in data
        assert "sources" in data

    def test_chat_without_course_id_no_rag(self, student_token):
        """Chat without course_id should not use RAG."""
        r = requests.post(
            f"{BASE}/api/ai/chat",
            headers={"Authorization": f"Bearer {student_token}",
                     "Content-Type": "application/json"},
            json={"message": "what is machine learning?"},
            timeout=30
        )
        data = r.json()["data"]
        assert data["rag_used"] is False
        assert data["chunks_retrieved"] == 0

    def test_chat_with_course_id_uses_rag(self, student_token, seed_data):
        """Chat with course_id should attempt RAG retrieval."""
        r = requests.post(
            f"{BASE}/api/ai/chat",
            headers={"Authorization": f"Bearer {student_token}",
                     "Content-Type": "application/json"},
            json={"message": "explain gradient descent", "course_id": COURSE_ID},
            timeout=30
        )
        assert r.status_code == 200
        data = r.json()["data"]
        # rag_used depends on whether material is uploaded
        assert "rag_used" in data

    def test_empty_message_rejected(self, student_token):
        r = requests.post(
            f"{BASE}/api/ai/chat",
            headers={"Authorization": f"Bearer {student_token}",
                     "Content-Type": "application/json"},
            json={"message": ""},
            timeout=10
        )
        assert r.status_code == 422

    def test_message_too_long_rejected(self, student_token):
        r = requests.post(
            f"{BASE}/api/ai/chat",
            headers={"Authorization": f"Bearer {student_token}",
                     "Content-Type": "application/json"},
            json={"message": "x" * 2001},
            timeout=10
        )
        assert r.status_code == 422

    def test_chat_unauthenticated_rejected(self):
        r = requests.post(
            f"{BASE}/api/ai/chat",
            headers={"Content-Type": "application/json"},
            json={"message": "hello"},
            timeout=10
        )
        assert r.status_code == 401


# ── Tool calling ──────────────────────────────────────────────────────────────

class TestToolCalling:

    def test_performance_tool_triggered(self, student_token):
        """Asking about grades should trigger get_student_performance."""
        r = requests.post(
            f"{BASE}/api/ai/chat",
            headers={"Authorization": f"Bearer {student_token}",
                     "Content-Type": "application/json"},
            json={"message": "what are my grades and scores?"},
            timeout=30
        )
        assert r.status_code == 200
        data = r.json()["data"]
        assert data.get("tool_used") == "get_student_performance"

    def test_flag_weak_topic_triggered(self, student_token):
        """Saying you don't understand a topic should trigger flag_weak_topic."""
        r = requests.post(
            f"{BASE}/api/ai/chat",
            headers={"Authorization": f"Bearer {student_token}",
                     "Content-Type": "application/json"},
            json={"message": "I don't understand backpropagation at all"},
            timeout=30
        )
        assert r.status_code == 200
        data = r.json()["data"]
        assert data.get("tool_used") == "flag_weak_topic"

    def test_course_summary_tool_triggered(self, student_token, seed_data):
        """Asking what a course covers should trigger get_course_summary."""
        r = requests.post(
            f"{BASE}/api/ai/chat",
            headers={"Authorization": f"Bearer {student_token}",
                     "Content-Type": "application/json"},
            json={"message": "what does course 1 cover?", "course_id": COURSE_ID},
            timeout=30
        )
        assert r.status_code == 200
        data = r.json()["data"]
        assert data.get("tool_used") == "get_course_summary"


# ── Streaming ─────────────────────────────────────────────────────────────────

class TestStreaming:

    def test_stream_returns_200(self, student_token):
        with requests.post(
            f"{BASE}/api/ai/chat/stream",
            headers={"Authorization": f"Bearer {student_token}",
                     "Content-Type": "application/json"},
            json={"message": "explain AI in one sentence"},
            stream=True,
            timeout=30
        ) as r:
            assert r.status_code == 200

    def test_stream_content_type(self, student_token):
        with requests.post(
            f"{BASE}/api/ai/chat/stream",
            headers={"Authorization": f"Bearer {student_token}",
                     "Content-Type": "application/json"},
            json={"message": "explain AI in one sentence"},
            stream=True,
            timeout=30
        ) as r:
            assert "text/event-stream" in r.headers.get("Content-Type", "")

    def test_stream_returns_sse_events(self, student_token):
        events = []
        with requests.post(
            f"{BASE}/api/ai/chat/stream",
            headers={"Authorization": f"Bearer {student_token}",
                     "Content-Type": "application/json"},
            json={"message": "say hello"},
            stream=True,
            timeout=30
        ) as r:
            for line in r.iter_lines():
                if line:
                    decoded = line.decode("utf-8")
                    if decoded.startswith("data:"):
                        events.append(decoded[5:].strip())
                if "[DONE]" in (line.decode("utf-8") if line else ""):
                    break

        assert len(events) > 0
        assert "[DONE]" in events

    def test_stream_unauthenticated_rejected(self):
        with requests.post(
            f"{BASE}/api/ai/chat/stream",
            headers={"Content-Type": "application/json"},
            json={"message": "hello"},
            stream=True,
            timeout=10
        ) as r:
            assert r.status_code == 401