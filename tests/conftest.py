"""
conftest.py — Shared pytest fixtures for BODH AI test suite
------------------------------------------------------------
Fixtures available to all test files automatically.
"""

import pytest
import requests

BASE_URL = "http://localhost:5000"

ADMIN_EMAIL    = "admin@demo.com"
ADMIN_PASSWORD = "admin123"
TEACHER_EMAIL  = "teacher@demo.com"
TEACHER_PASSWORD = "teacher123"
STUDENT_EMAIL  = "student@demo.com"
STUDENT_PASSWORD = "student123"


def get_token(email: str, password: str) -> str:
    """Login and return JWT token."""
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": email, "password": password},
        timeout=10
    )
    assert r.status_code == 200, f"Login failed for {email}: {r.text}"
    return r.json()["data"]["token"]


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL


@pytest.fixture(scope="session")
def admin_token():
    return get_token(ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture(scope="session")
def teacher_token():
    return get_token(TEACHER_EMAIL, TEACHER_PASSWORD)


@pytest.fixture(scope="session")
def student_token():
    return get_token(STUDENT_EMAIL, STUDENT_PASSWORD)


@pytest.fixture(scope="session")
def auth_header(student_token):
    return {
        "Authorization": f"Bearer {student_token}",
        "Content-Type": "application/json"
    }


@pytest.fixture(scope="session")
def teacher_header(teacher_token):
    return {
        "Authorization": f"Bearer {teacher_token}",
        "Content-Type": "application/json"
    }


@pytest.fixture(scope="session")
def seed_data(admin_token, base_url):
    """Seed demo data once per test session."""
    r = requests.post(
        f"{base_url}/api/admin/seed",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=10
    )
    assert r.status_code in (200, 201), f"Seed failed: {r.text}"
    return r.json()