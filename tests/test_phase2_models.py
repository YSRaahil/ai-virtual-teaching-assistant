"""
test_phase2_models.py — Database + materials table tests
---------------------------------------------------------
Tests models.py in isolation — no server, no HTTP.
Uses a separate test database to avoid polluting production data.

Run: pytest tests/test_phase2_models.py -v
"""

import pytest
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Use a temp DB for tests — never touch production DB
os.environ["DB_PATH"] = os.path.join(tempfile.gettempdir(), "test_bodh_ai.db")

from models import (
    init_db, create_user, get_user_by_email, get_user_by_id,
    verify_user, create_course, get_course_by_id,
    enroll_student, get_enrolled_courses,
    save_material, get_materials_by_course,
    get_material_filenames, delete_material
)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    """Initialize fresh test database before all tests in this module."""
    init_db()
    yield
    # Cleanup test DB after module
    db_path = os.environ.get("DB_PATH")
    if db_path and os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture(scope="module")
def teacher():
    """Create and return a test teacher."""
    create_user("Test Teacher", "pytest_teacher@test.com", "password123", "teacher")
    return get_user_by_email("pytest_teacher@test.com")


@pytest.fixture(scope="module")
def student():
    """Create and return a test student."""
    create_user("Test Student", "pytest_student@test.com", "password123", "student")
    return get_user_by_email("pytest_student@test.com")


@pytest.fixture(scope="module")
def course(teacher):
    """Create and return a test course."""
    course_id = create_course(
        title="Pytest Test Course",
        description="Created during pytest run",
        teacher_id=teacher["id"]
    )
    return get_course_by_id(course_id)


# ── User tests ────────────────────────────────────────────────────────────────

class TestUsers:

    def test_create_teacher(self, teacher):
        assert teacher is not None
        assert teacher["role"] == "teacher"
        assert teacher["email"] == "pytest_teacher@test.com"

    def test_create_student(self, student):
        assert student is not None
        assert student["role"] == "student"

    def test_get_user_by_id(self, teacher):
        user = get_user_by_id(teacher["id"])
        assert user is not None
        assert user["id"] == teacher["id"]

    def test_verify_user_correct_password(self):
        user = verify_user("pytest_teacher@test.com", "password123")
        assert user is not None

    def test_verify_user_wrong_password(self):
        user = verify_user("pytest_teacher@test.com", "wrongpassword")
        assert user is None

    def test_verify_user_nonexistent(self):
        user = verify_user("nobody@test.com", "password")
        assert user is None

    def test_duplicate_email_rejected(self):
        result = create_user("Dup", "pytest_teacher@test.com", "pass", "teacher")
        assert result["success"] is False
        assert "already registered" in result["error"]


# ── Course tests ──────────────────────────────────────────────────────────────

class TestCourses:

    def test_create_course(self, course):
        assert course is not None
        assert course["title"] == "Pytest Test Course"

    def test_get_course_by_id(self, course):
        fetched = get_course_by_id(course["id"])
        assert fetched is not None
        assert fetched["id"] == course["id"]

    def test_get_nonexistent_course(self):
        result = get_course_by_id(99999)
        assert result is None


# ── Enrollment tests ──────────────────────────────────────────────────────────

class TestEnrollments:

    def test_enroll_student(self, student, course):
        result = enroll_student(student["id"], course["id"])
        assert result["success"] is True

    def test_duplicate_enrollment_rejected(self, student, course):
        result = enroll_student(student["id"], course["id"])
        assert result["success"] is False
        assert "Already enrolled" in result["error"]

    def test_get_enrolled_courses(self, student, course):
        courses = get_enrolled_courses(student["id"])
        assert any(c["id"] == course["id"] for c in courses)


# ── Materials tests ───────────────────────────────────────────────────────────

class TestMaterials:

    def test_save_material(self, course, teacher):
        material_id = save_material(
            course_id=course["id"],
            filename="test_notes",
            original_name="test_notes.pdf",
            chunk_count=12,
            uploaded_by=teacher["id"]
        )
        assert material_id is not None
        assert isinstance(material_id, int)

    def test_get_materials_by_course(self, course):
        rows = get_materials_by_course(course["id"])
        assert len(rows) >= 1
        assert any(r["original_name"] == "test_notes.pdf" for r in rows)

    def test_material_chunk_count(self, course):
        rows = get_materials_by_course(course["id"])
        material = next(r for r in rows if r["original_name"] == "test_notes.pdf")
        assert material["chunk_count"] == 12

    def test_get_material_filenames(self, course):
        names = get_material_filenames(course["id"])
        assert "test_notes.pdf" in names

    def test_upsert_updates_chunk_count(self, course, teacher):
        """Re-uploading same file should update chunk_count, not create duplicate."""
        save_material(
            course_id=course["id"],
            filename="test_notes",
            original_name="test_notes.pdf",
            chunk_count=25,
            uploaded_by=teacher["id"]
        )
        rows = get_materials_by_course(course["id"])
        matching = [r for r in rows if r["original_name"] == "test_notes.pdf"]
        assert len(matching) == 1           # no duplicate
        assert matching[0]["chunk_count"] == 25

    def test_save_multiple_materials(self, course, teacher):
        save_material(
            course_id=course["id"],
            filename="lecture2",
            original_name="lecture2.pdf",
            chunk_count=8,
            uploaded_by=teacher["id"]
        )
        rows = get_materials_by_course(course["id"])
        assert len(rows) >= 2

    def test_delete_material(self, course):
        deleted = delete_material(course["id"], "lecture2.pdf")
        assert deleted is True

    def test_delete_nonexistent_material(self, course):
        deleted = delete_material(course["id"], "nonexistent.pdf")
        assert deleted is False

    def test_get_materials_empty_course(self):
        rows = get_materials_by_course(99999)
        assert rows == []