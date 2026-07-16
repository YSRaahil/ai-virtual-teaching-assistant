"""
test_tool_service.py — Tool service tests
------------------------------------------
Tests tool functions and schema in isolation — no server required.
Also tests the agentic path via HTTP (server must be running for those).

Run (isolated): pytest tests/test_tool_service.py -v -k "not Api"
Run (full):     pytest tests/test_tool_service.py -v
"""

import pytest
import json
import os
import sys
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tool_service
from tool_service import (
    get_student_performance,
    get_course_summary,
    flag_weak_topic,
    execute_tool,
    TOOL_DEFINITIONS
)

@pytest.fixture(scope="module", autouse=True)
def setup_database():
    """Initialize DB before tool service tests run in CI."""
    import os
    os.environ.setdefault("DB_PATH", "ci_test.db")
    from models import init_db
    init_db()
    yield


BASE = "http://localhost:5000"
STUDENT_ID = 4   # seeded demo student
COURSE_ID  = 1


# ── Tool schema validation ────────────────────────────────────────────────────

class TestToolDefinitions:

    def test_three_tools_defined(self):
        assert len(TOOL_DEFINITIONS) == 3

    def test_tool_names_correct(self):
        names = {t["function"]["name"] for t in TOOL_DEFINITIONS}
        assert names == {"get_student_performance", "get_course_summary", "flag_weak_topic"}

    def test_all_tools_have_description(self):
        for t in TOOL_DEFINITIONS:
            assert len(t["function"]["description"]) > 10

    def test_flag_weak_topic_requires_topic(self):
        flag_tool = next(
            t for t in TOOL_DEFINITIONS
            if t["function"]["name"] == "flag_weak_topic"
        )
        required = flag_tool["function"]["parameters"]["required"]
        assert "topic" in required

    def test_get_course_summary_requires_course_id(self):
        course_tool = next(
            t for t in TOOL_DEFINITIONS
            if t["function"]["name"] == "get_course_summary"
        )
        required = course_tool["function"]["parameters"]["required"]
        assert "course_id" in required


# ── Tool function unit tests ──────────────────────────────────────────────────

class TestGetStudentPerformance:

    def test_returns_dict(self):
        result = get_student_performance(student_id=STUDENT_ID)
        assert isinstance(result, dict)

    def test_found_key_present(self):
        result = get_student_performance(student_id=STUDENT_ID)
        assert "found" in result

    def test_nonexistent_student_not_found(self):
        result = get_student_performance(student_id=99999)
        assert result["found"] is False

    def test_with_valid_student_returns_data(self):
        result = get_student_performance(student_id=STUDENT_ID)
        if result["found"]:
            assert "average_score" in result
            assert "total_assignments" in result
            assert "weak_areas" in result
            assert "strong_areas" in result
            assert "trend" in result

    def test_with_course_id_filter(self):
        result = get_student_performance(student_id=STUDENT_ID, course_id=COURSE_ID)
        assert isinstance(result, dict)
        assert "found" in result


class TestGetCourseSummary:

    def test_returns_dict(self):
        result = get_course_summary(course_id=COURSE_ID)
        assert isinstance(result, dict)

    def test_found_key_present(self):
        result = get_course_summary(course_id=COURSE_ID)
        assert "found" in result

    def test_valid_course_returns_data(self):
        result = get_course_summary(course_id=COURSE_ID)
        if result["found"]:
            assert "title" in result
            assert "assignment_count" in result
            assert "material_count" in result
            assert "materials" in result

    def test_nonexistent_course_not_found(self):
        result = get_course_summary(course_id=99999)
        assert result["found"] is False


class TestFlagWeakTopic:

    def test_returns_dict(self):
        result = flag_weak_topic(student_id=STUDENT_ID, topic="gradient descent")
        assert isinstance(result, dict)

    def test_flagged_is_true(self):
        result = flag_weak_topic(student_id=STUDENT_ID, topic="backpropagation")
        assert result["flagged"] is True

    def test_topic_in_result(self):
        result = flag_weak_topic(student_id=STUDENT_ID, topic="overfitting")
        assert result["topic"] == "overfitting"

    def test_study_suggestions_returned(self):
        result = flag_weak_topic(student_id=STUDENT_ID, topic="gradient descent")
        assert "study_suggestions" in result
        assert len(result["study_suggestions"]) > 0

    def test_with_course_id(self):
        result = flag_weak_topic(student_id=STUDENT_ID, topic="dropout", course_id=COURSE_ID)
        assert result["flagged"] is True
        assert result["course_id"] == COURSE_ID

    def test_unknown_topic_returns_generic_suggestions(self):
        result = flag_weak_topic(student_id=STUDENT_ID, topic="quantum_computing_xyz")
        assert len(result["study_suggestions"]) > 0


# ── execute_tool dispatcher tests ─────────────────────────────────────────────

class TestExecuteTool:

    def test_execute_get_student_performance(self):
        result_json = execute_tool(
            "get_student_performance",
            {"student_id": STUDENT_ID}
        )
        result = json.loads(result_json)
        assert "found" in result

    def test_execute_get_course_summary(self):
        result_json = execute_tool(
            "get_course_summary",
            {"course_id": COURSE_ID}
        )
        result = json.loads(result_json)
        assert "found" in result

    def test_execute_flag_weak_topic(self):
        result_json = execute_tool(
            "flag_weak_topic",
            {"student_id": STUDENT_ID, "topic": "backpropagation"}
        )
        result = json.loads(result_json)
        assert result["flagged"] is True

    def test_execute_unknown_tool_returns_error(self):
        result_json = execute_tool("nonexistent_tool", {})
        result = json.loads(result_json)
        assert "error" in result

    def test_execute_course_id_string_cast(self):
        """execute_tool should cast string course_id to int."""
        result_json = execute_tool(
            "get_course_summary",
            {"course_id": "1"}   # string — should be cast to int
        )
        result = json.loads(result_json)
        assert "error" not in result or "Unknown" not in result.get("error", "")


# ── Agentic API path tests (server must be running) ───────────────────────────

class TestToolCallingApi:

    def _get_token(self):
        r = requests.post(f"{BASE}/api/auth/login",
                          json={"email": "student@demo.com", "password": "student123"},
                          timeout=10)
        return r.json()["data"]["token"]

    def test_performance_tool_via_api(self):
        token = self._get_token()
        r = requests.post(
            f"{BASE}/api/ai/chat",
            headers={"Authorization": f"Bearer {token}",
                     "Content-Type": "application/json"},
            json={"message": "what are my grades and weak topics?"},
            timeout=30
        )
        assert r.status_code == 200
        data = r.json()["data"]
        assert data.get("tool_used") == "get_student_performance"
        assert len(data.get("response", "")) > 0

    def test_flag_weak_topic_via_api(self):
        token = self._get_token()
        r = requests.post(
            f"{BASE}/api/ai/chat",
            headers={"Authorization": f"Bearer {token}",
                     "Content-Type": "application/json"},
            json={"message": "I don't understand backpropagation at all"},
            timeout=30
        )
        assert r.status_code == 200
        data = r.json()["data"]
        assert data.get("tool_used") == "flag_weak_topic"

    def test_course_summary_via_api(self):
        token = self._get_token()
        r = requests.post(
            f"{BASE}/api/ai/chat",
            headers={"Authorization": f"Bearer {token}",
                     "Content-Type": "application/json"},
            json={"message": "what does course 1 cover?", "course_id": 1},
            timeout=30
        )
        assert r.status_code == 200
        data = r.json()["data"]
        assert data.get("tool_used") == "get_course_summary"