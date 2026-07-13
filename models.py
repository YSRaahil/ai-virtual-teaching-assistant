"""
models.py — Database schema and query layer
All DB interaction lives here. Routes never touch SQL directly.
"""

import sqlite3
import hashlib
import os
from datetime import datetime

DB_PATH = os.getenv("DB_PATH", "teaching_assistant.db")


def get_db():
    """Get a database connection with row factory for dict-like access."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """
    Initialize all tables. Safe to call on every startup — uses IF NOT EXISTS.
    Schema: Users, Courses, Enrollments, Assignments, Submissions, Grades
    Normalised to 3NF — no transitive dependencies, no redundant data.
    """
    conn = get_db()
    c = conn.cursor()

    # Users — 3 roles: admin, teacher, student
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'teacher', 'student')),
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # Courses — owned by a teacher
    c.execute("""
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            teacher_id INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (teacher_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    # Enrollments — many-to-many: students <-> courses
    c.execute("""
        CREATE TABLE IF NOT EXISTS enrollments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            course_id INTEGER NOT NULL,
            enrolled_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
            UNIQUE(student_id, course_id)
        )
    """)

    # Assignments — belong to a course, have a rubric for auto-grading
    c.execute("""
        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            rubric_keywords TEXT NOT NULL DEFAULT '',
            max_score INTEGER NOT NULL DEFAULT 100,
            due_date TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
        )
    """)

    # Submissions — one per student per assignment
    c.execute("""
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            submitted_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (assignment_id) REFERENCES assignments(id) ON DELETE CASCADE,
            FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(assignment_id, student_id)
        )
    """)

    # Grades — separate from submissions (single responsibility)
    c.execute("""
        CREATE TABLE IF NOT EXISTS grades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id INTEGER NOT NULL UNIQUE,
            score INTEGER NOT NULL,
            feedback TEXT,
            graded_by TEXT NOT NULL DEFAULT 'auto',
            graded_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (submission_id) REFERENCES submissions(id) ON DELETE CASCADE
        )
    """)

    # Materials — tracks PDFs uploaded per course for ChromaDB reload on cold start
    # One row per file upload. Used by /api/courses/<id>/knowledge-status
    # and the /knowledge/reload recovery endpoint.
    c.execute("""
        CREATE TABLE IF NOT EXISTS materials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            original_name TEXT NOT NULL,
            chunk_count INTEGER NOT NULL DEFAULT 0,
            uploaded_by INTEGER NOT NULL,
            uploaded_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
            FOREIGN KEY (uploaded_by) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(course_id, original_name)
        )
    """)

    conn.commit()
    conn.close()
    print("✅ Database initialised")


# ─── AUTH ────────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def create_user(name: str, email: str, password: str, role: str):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
            (name, email, hash_password(password), role)
        )
        conn.commit()
        return {"success": True}
    except sqlite3.IntegrityError:
        return {"success": False, "error": "Email already registered"}
    finally:
        conn.close()


def get_user_by_email(email: str):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return dict(user) if user else None


def verify_user(email: str, password: str):
    user = get_user_by_email(email)
    if not user:
        return None
    if user["password_hash"] == hash_password(password):
        return user
    return None


def get_user_by_id(user_id: int):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(user) if user else None


# ─── COURSES ─────────────────────────────────────────────────────────────────

def create_course(title: str, description: str, teacher_id: int):
    conn = get_db()
    c = conn.execute(
        "INSERT INTO courses (title, description, teacher_id) VALUES (?, ?, ?)",
        (title, description, teacher_id)
    )
    conn.commit()
    course_id = c.lastrowid
    conn.close()
    return course_id


def get_courses_by_teacher(teacher_id: int):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM courses WHERE teacher_id = ? ORDER BY created_at DESC",
        (teacher_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_courses():
    conn = get_db()
    rows = conn.execute("""
        SELECT c.*, u.name as teacher_name
        FROM courses c
        JOIN users u ON c.teacher_id = u.id
        ORDER BY c.created_at DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_course_by_id(course_id: int):
    conn = get_db()
    row = conn.execute("SELECT * FROM courses WHERE id = ?", (course_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# ─── ENROLLMENTS ─────────────────────────────────────────────────────────────

def enroll_student(student_id: int, course_id: int):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO enrollments (student_id, course_id) VALUES (?, ?)",
            (student_id, course_id)
        )
        conn.commit()
        return {"success": True}
    except sqlite3.IntegrityError:
        return {"success": False, "error": "Already enrolled"}
    finally:
        conn.close()


def get_enrolled_courses(student_id: int):
    conn = get_db()
    rows = conn.execute("""
        SELECT c.*, u.name as teacher_name
        FROM courses c
        JOIN enrollments e ON c.id = e.course_id
        JOIN users u ON c.teacher_id = u.id
        WHERE e.student_id = ?
        ORDER BY e.enrolled_at DESC
    """, (student_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_enrolled_students(course_id: int):
    conn = get_db()
    rows = conn.execute("""
        SELECT u.id, u.name, u.email, e.enrolled_at
        FROM users u
        JOIN enrollments e ON u.id = e.student_id
        WHERE e.course_id = ?
        ORDER BY u.name
    """, (course_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── ASSIGNMENTS ─────────────────────────────────────────────────────────────

def create_assignment(course_id: int, title: str, description: str,
                      rubric_keywords: str, max_score: int, due_date: str):
    conn = get_db()
    c = conn.execute(
        """INSERT INTO assignments
           (course_id, title, description, rubric_keywords, max_score, due_date)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (course_id, title, description, rubric_keywords, max_score, due_date)
    )
    conn.commit()
    assignment_id = c.lastrowid
    conn.close()
    return assignment_id


def get_assignments_by_course(course_id: int):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM assignments WHERE course_id = ? ORDER BY created_at DESC",
        (course_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_assignment_by_id(assignment_id: int):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM assignments WHERE id = ?", (assignment_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# ─── SUBMISSIONS ─────────────────────────────────────────────────────────────

def submit_assignment(assignment_id: int, student_id: int, content: str):
    conn = get_db()
    try:
        c = conn.execute(
            """INSERT INTO submissions (assignment_id, student_id, content)
               VALUES (?, ?, ?)
               ON CONFLICT(assignment_id, student_id)
               DO UPDATE SET content=excluded.content, submitted_at=datetime('now')""",
            (assignment_id, student_id, content)
        )
        conn.commit()
        sub_id = c.lastrowid or conn.execute(
            "SELECT id FROM submissions WHERE assignment_id=? AND student_id=?",
            (assignment_id, student_id)
        ).fetchone()["id"]
        conn.close()
        return sub_id
    except Exception as e:
        conn.close()
        raise e


def get_submission(assignment_id: int, student_id: int):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM submissions WHERE assignment_id=? AND student_id=?",
        (assignment_id, student_id)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_submissions_by_assignment(assignment_id: int):
    conn = get_db()
    rows = conn.execute("""
        SELECT s.*, u.name as student_name,
               g.score, g.feedback, g.graded_by, g.graded_at
        FROM submissions s
        JOIN users u ON s.student_id = u.id
        LEFT JOIN grades g ON g.submission_id = s.id
        WHERE s.assignment_id = ?
        ORDER BY s.submitted_at DESC
    """, (assignment_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── GRADES ──────────────────────────────────────────────────────────────────

def save_grade(submission_id: int, score: int, feedback: str, graded_by: str = "auto"):
    conn = get_db()
    conn.execute(
        """INSERT INTO grades (submission_id, score, feedback, graded_by)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(submission_id)
           DO UPDATE SET score=excluded.score, feedback=excluded.feedback,
                         graded_by=excluded.graded_by, graded_at=datetime('now')""",
        (submission_id, score, feedback, graded_by)
    )
    conn.commit()
    conn.close()


def get_grade(submission_id: int):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM grades WHERE submission_id = ?", (submission_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_student_grades(student_id: int, course_id: int = None):
    """Get all grades for a student, optionally filtered by course."""
    conn = get_db()
    query = """
        SELECT g.score, g.feedback, g.graded_at,
               a.title as assignment_title, a.max_score,
               c.title as course_title, c.id as course_id
        FROM grades g
        JOIN submissions s ON g.submission_id = s.id
        JOIN assignments a ON s.assignment_id = a.id
        JOIN courses c ON a.course_id = c.id
        WHERE s.student_id = ?
    """
    params = [student_id]
    if course_id:
        query += " AND c.id = ?"
        params.append(course_id)
    query += " ORDER BY g.graded_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── ADMIN ───────────────────────────────────────────────────────────────────

def get_all_users():
    conn = get_db()
    rows = conn.execute(
        "SELECT id, name, email, role, created_at FROM users ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── MATERIALS ───────────────────────────────────────────────────────────────

def save_material(course_id: int, filename: str, original_name: str,
                  chunk_count: int, uploaded_by: int):
    """
    Record a successfully ingested PDF in the materials table.

    Args:
        course_id:     Course this material belongs to.
        filename:      Sanitised filename used as ChromaDB ID prefix.
        original_name: Original upload filename shown to the teacher.
        chunk_count:   Number of chunks ingested into ChromaDB.
        uploaded_by:   User ID of the teacher who uploaded it.

    Returns:
        material_id (int) on success.
        None if the same file was already uploaded for this course (UNIQUE constraint).

    Called by:
        POST /api/courses/<id>/materials after rag_service.ingest() succeeds.
    """
    conn = get_db()
    try:
        c = conn.execute(
            """INSERT INTO materials
               (course_id, filename, original_name, chunk_count, uploaded_by)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(course_id, original_name)
               DO UPDATE SET chunk_count=excluded.chunk_count,
                             uploaded_at=datetime('now')""",
            (course_id, filename, original_name, chunk_count, uploaded_by)
        )
        conn.commit()
        material_id = c.lastrowid
        conn.close()
        return material_id
    except Exception as e:
        conn.close()
        raise e


def get_materials_by_course(course_id: int):
    """
    Return all materials uploaded for a course.
    Used by GET /api/courses/<id>/knowledge-status.

    Returns:
        List of dicts with: id, course_id, filename, original_name,
                            chunk_count, uploaded_by, uploaded_at
    """
    conn = get_db()
    rows = conn.execute(
        """SELECT m.*, u.name as uploaded_by_name
           FROM materials m
           JOIN users u ON m.uploaded_by = u.id
           WHERE m.course_id = ?
           ORDER BY m.uploaded_at DESC""",
        (course_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_material_filenames(course_id: int) -> list:
    """
    Return just the original filenames for a course.
    Used by the /knowledge/reload endpoint to re-ingest after Render cold start.

    Returns:
        List of original_name strings.
    """
    conn = get_db()
    rows = conn.execute(
        "SELECT original_name FROM materials WHERE course_id = ? ORDER BY uploaded_at ASC",
        (course_id,)
    ).fetchall()
    conn.close()
    return [r["original_name"] for r in rows]


def delete_material(course_id: int, original_name: str) -> bool:
    """
    Remove a material record from SQLite.
    Call this alongside rag_service.delete_course_collection() if needed.

    Returns:
        True if a row was deleted, False if not found.
    """
    conn = get_db()
    c = conn.execute(
        "DELETE FROM materials WHERE course_id = ? AND original_name = ?",
        (course_id, original_name)
    )
    conn.commit()
    deleted = c.rowcount > 0
    conn.close()
    return deleted


def get_platform_stats():
    conn = get_db()
    stats = {
        "total_users": conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        "total_students": conn.execute("SELECT COUNT(*) FROM users WHERE role='student'").fetchone()[0],
        "total_teachers": conn.execute("SELECT COUNT(*) FROM users WHERE role='teacher'").fetchone()[0],
        "total_courses": conn.execute("SELECT COUNT(*) FROM courses").fetchone()[0],
        "total_assignments": conn.execute("SELECT COUNT(*) FROM assignments").fetchone()[0],
        "total_submissions": conn.execute("SELECT COUNT(*) FROM submissions").fetchone()[0],
        "total_graded": conn.execute("SELECT COUNT(*) FROM grades").fetchone()[0],
    }
    conn.close()
    return stats