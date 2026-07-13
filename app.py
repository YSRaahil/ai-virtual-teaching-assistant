"""
app.py — Flask application entry point
All API routes live here. Business logic
lives in models/grading/analytics/auth.
Routes are organised by role: auth,
student, teacher, admin, ai.
"""
import os
import json
from tool_service import TOOL_DEFINITIONS,execute_tool
import logging
from urllib import response
from flask import Flask, request, jsonify,send_from_directory, Response,stream_with_context
from flask_cors import CORS
from dotenv import load_dotenv
from groq import Groq
import fitz  # PyMuPDF
import models
import grading
import analytics
from auth import login_required,role_required,generate_token,get_current_user
from rag_service import ingest, retrieve,collection_stats, chunk_text
import tool_service
# ─── SETUP
load_dotenv()
logging.basicConfig(level=logging.INFO,format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)
app = Flask(__name__,static_folder="static",template_folder="templates")
app.secret_key = os.getenv("SECRET_KEY",
"dev-secret-change-in-production")
# CORS: restrict to frontend origin in production
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "*")
CORS(app, origins=FRONTEND_ORIGIN,
supports_credentials=True)
# Groq setup
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

print("Debug: GROQ_API_KEY =", GROQ_API_KEY[:10])  # Debugging line

groq_client = None

if GROQ_API_KEY:
    groq_client = Groq(
        api_key=GROQ_API_KEY
    )
    log.info("✅ Groq configured")
else:
    log.warning("⚠️ GROQ_API_KEY not set — AI features disabled")
# Initialise DB on startup
models.init_db()
# ─── HELPERS
def ok(data=None, message="Success",
code=200):
    return jsonify({"status": "success",
"message": message, "data": data}), code
def err(message="An error occurred",
code=400):
    return jsonify({"status": "error",
"message": message}), code
def require_json(*fields):
    """Validate that required fields exist
in request JSON. Returns (data,
error_response)."""
    data = request.get_json(silent=True)
    if not data:
        return None, err("Request body must be JSON", 400)
    missing = [f for f in fields if not data.get(f)]
    if missing:
        return None, err(f"Missing required fields: {', '.join(missing)}", 422)
    return data, None
# ─── SERVE FRONTEND
@app.route("/")
def index():
    return send_from_directory("templates",
"index.html")
@app.route("/<path:filename>")
def serve_template(filename):
    """Serve HTML templates directly for dev convenience."""
    try:
        return send_from_directory("templates", filename)
    except Exception:
        return err("Page not found", 404)
# ─── HEALTH CHECK
@app.route("/api/health")
def health():
    return ok({"service": "AI Teaching Assistant", "version": "1.0.0"})
# ─── AUTH ROUTES
@app.route("/api/auth/register", methods=
["POST"])
def register():
    """
    Register a new user.
    Body: { name, email, password, role }
    Role must be: student | teacher (admin
created manually)
    """
    data, error = require_json("name",
"email", "password", "role")
    if error:
        return error
    if data["role"] not in ("student","teacher"):
        return err("Role must be 'student' or 'teacher'", 422)
    if len(data["password"]) < 6:
        return err("Password must be at least 6 characters", 422)
    result = models.create_user(
        name=data["name"].strip(),
       
email=data["email"].strip().lower(),
        password=data["password"],
        role=data["role"]
    )
    if not result["success"]:
        return err(result["error"], 409)
    user = models.get_user_by_email(data["email"].strip().lower())
    token = generate_token(user)
    log.info(f"New user registered: {user['email']} ({user['role']})")
    return ok({"token": token, "user": {
        "id": user["id"], "name":
user["name"],
        "email": user["email"], "role":
user["role"]
    }}, "Registration successful", 201)
@app.route("/api/auth/login", methods=
["POST"])
def login():
    """
    Login with email + password. Returns
JWT.
    Body: { email, password }
    """
    data, error = require_json("email",
"password")
    if error:
        return error
    user = models.verify_user(
       
email=data["email"].strip().lower(),
        password=data["password"]
    )
    if not user:
        return err("Invalid email or password", 401)
    token = generate_token(user)
    log.info(f"User logged in: {user['email']}")
    return ok({"token": token, "user": {
        "id": user["id"], "name":
user["name"],
        "email": user["email"], "role":
user["role"]
    }}, "Login successful")
@app.route("/api/auth/me", methods=["GET"])
@login_required
def me(current_user):
    """Return current user info from
token."""
    return ok({"user": current_user})
# COURSE ROUTE
@app.route("/api/courses", methods=["GET"])
@login_required
def list_courses(current_user):
    """
    Students: returns enrolled courses.
    Teachers/Admin: returns all courses.
    """
    if current_user["role"] == "student":
        courses = models.get_enrolled_courses(current_user["user_id"])
    else:
        courses = models.get_all_courses()
    return ok(courses)
@app.route("/api/courses", methods=
["POST"])
@role_required("teacher", "admin")
def create_course(current_user):
    """Create a new course. Teacher
only."""
    data, error = require_json("title")
    if error:
        return error
    course_id = models.create_course(
        title=data["title"].strip(),
        description=data.get("description",
"").strip(),
        teacher_id=current_user["user_id"]
    )
    log.info(f"Course created: {data['title']} by {current_user['email']}")
    return ok({"course_id": course_id},"Course created", 201)
@app.route("/api/courses/<int:course_id>",
methods=["GET"])
@login_required
def get_course(current_user, course_id):
    """Get a single course with its
assignments."""
    course = models.get_course_by_id(course_id)
    if not course:
        return err("Course not found", 404)
    assignments = models.get_assignments_by_course(course_id)
    students = models.get_enrolled_students(course_id)
    return ok({
        "course": course,
        "assignments": assignments,
        "student_count": len(students)
    })
# ─── ENROLLMENT ROUTES
@app.route("/api/courses/<int:course_id>/enroll", methods=["POST"])
@role_required("student")
def enroll(current_user, course_id):
    """Student enrolls in a course."""
    course = models.get_course_by_id(course_id)
    if not course:
        return err("Course not found", 404)
    result = models.enroll_student(current_user["user_id"], course_id)
    if not result["success"]:
        return err(result["error"], 409)
    return ok({"course_id": course_id},
"Enrolled successfully", 201)
@app.route("/api/courses/<int:course_id>/students", methods=["GET"])
@role_required("teacher", "admin")
def course_students(current_user,course_id):
    """Get all students enrolled in a
course."""
    students = models.get_enrolled_students(course_id)
    return ok(students)
# ─── MATERIALS / RAG ROUTES
@app.route("/api/courses/<int:course_id>/materials", methods=["POST"])
@role_required("teacher", "admin")
def upload_material(current_user,course_id):
    """
    Upload a PDF for a course. Extracts
text, chunks it, embeds it,
    and stores it in ChromaDB. Records the
upload in SQLite materials table.
    Form data: file (PDF)
    Returns: { filename, chunk_count,
collection_name }
    """
    course = models.get_course_by_id(course_id)
    if not course:
        return err("Course not found", 404)
    if "file" not in request.files:
        return err("No file uploaded. Send PDF as multipart/form-data with key 'file'.", 400)
    file = request.files["file"]
    if not file.filename:
        return err("File has no name.",
400)
    if not file.filename.lower().endswith(".pdf"):
        return err("Only PDF files aresupported.", 422)
    try:
        # Read PDF bytes and extract text
        pdf_bytes = file.read()

        doc = fitz.open(
        stream=pdf_bytes,
        filetype="pdf"
        )

        raw_text = ""

        for page in doc:
            raw_text += page.get_text()

        doc.close()
        if not raw_text.strip():
            return err("PDF appears to be empty or scanned (no extractable text).",422)
        # Chunk the extracted text
        chunks = chunk_text(raw_text,chunk_size=300, overlap=50)
        if not chunks:
            return err("Could not extract any usable text chunks from this PDF.",422)
        # Ingest into ChromaDB
        original_name = file.filename
        result = ingest(
            chunks=chunks,
            course_id=course_id,
            source_filename=original_name
        )
        # Record in SQLite
        safe_filename = original_name.replace(" ","_").replace("/", "_")
        models.save_material(
            course_id=course_id,
            filename=safe_filename,
            original_name=original_name,
           chunk_count=result["chunks_stored"],
           uploaded_by=current_user["user_id"]
        )
        log.info(
            f"Material uploaded: course={course_id}, file={original_name}, "f"chunks={result['chunks_stored']}, by={current_user['email']}")
        return ok({
            "filename": original_name,
            "chunk_count":result["chunks_stored"],
            "collection_name":result["collection_name"]}, "Material uploaded and indexed successfully", 201)
    except Exception as e:
        log.error(f"Material upload error: {e}")
        return err(f"Failed to process PDF: {str(e)}", 500)
@app.route("/api/courses/<int:course_id>/knowledge-status", methods=["GET"])
@login_required
def knowledge_status(current_user,
course_id):
    """
    Returns ChromaDB collection stats for a
course.
    Shows chunk count and which files have
been ingested.
    Returns: { course_id, chunk_count,
sources, collection_name, materials }
    """
    course = models.get_course_by_id(course_id)
    if not course:
        return err("Course not found", 404)
    # ChromaDB stats
    stats = collection_stats(course_id)
    # SQLite metadata (upload timestamps,who uploaded)
    materials =models.get_materials_by_course(course_id)
    return ok({
        "course_id": course_id,
        "chunk_count":stats["chunk_count"],
        "sources": stats["sources"],
        "collection_name":stats["collection_name"],
        "materials": materials})
# ─── ASSIGNMENT ROUTES
@app.route("/api/courses/<int:course_id>/assignments", methods=["POST"])
@role_required("teacher", "admin")
def create_assignment(current_user,course_id):
    """
    Create an assignment for a course.
    rubric_keywords: comma-separated
keywords used for auto-grading.
    e.g. "photosynthesis, chlorophyll,
sunlight, glucose, oxygen"
    """
    data, error = require_json("title",
"rubric_keywords")
    if error:
        return error
    course = models.get_course_by_id(course_id)
    if not course:
        return err("Course not found", 404)
    assignment_id = models.create_assignment(
        course_id=course_id,
        title=data["title"].strip(),
        description=data.get("description","").strip(),
        rubric_keywords=data["rubric_keywords"].strip(),
        max_score=int(data.get("max_score",100)),
        due_date=data.get("due_date", "")
    )
    log.info(f"Assignment created:{data['title']} in course {course_id}")
    return ok ({"assignment_id":assignment_id}, "Assignment created",201)
@app.route("/api/assignments/<int:assignment_id>", methods=["GET"])
@login_required
def get_assignment(current_user,assignment_id):
    """Get assignment details. Students
also see their own submission if any."""
    assignment = models.get_assignment_by_id(assignment_id)
    if not assignment:
        return err("Assignment not found",404)
    response = {"assignment": assignment}
    if current_user["role"] == "student":
        submission = models.get_submission(assignment_id,current_user["user_id"])
        response["submission"] = submission
        if submission:
            grade = models.get_grade(submission["id"])
            response["grade"] = grade
    return ok(response)
# ─── SUBMISSION ROUTES
@app.route("/api/assignments/<int:assignment_id>/submit", methods=["POST"])
@role_required("student")
def submit(current_user, assignment_id):
    """
    Student submits an answer. Triggers
auto-grading immediately.
    Body: { content: "student's answer
text" }
    """
    data, error = require_json("content")
    if error:
        return error
    assignment = models.get_assignment_by_id(assignment_id)
    if not assignment:
        return err("Assignment not found",404)
    if len(data["content"].strip()) < 10:
        return err("Answer is too short.Please provide a meaningful response.",422)
    # Save submission
    sub_id = models.submit_assignment(
        assignment_id=assignment_id,
        student_id=current_user["user_id"],
        content=data["content"].strip()
    )
    # Auto-grade immediately
    result = grading.grade(
        answer=data["content"],
       rubric_keywords_str=assignment["rubric_keywords"],
        max_score=assignment["max_score"]
    )
    models.save_grade(
        submission_id=sub_id,
        score=result["score"],
        feedback=result["feedback"],
        graded_by="auto"
    )
    log.info(
        f"Submission graded: student={current_user['user_id']}, "
        f"assignment={assignment_id},score={result['score']}/{assignment['max_score']}")
    return ok({
        "submission_id": sub_id,
        "score": result["score"],
        "max_score":
assignment["max_score"],
        "percentage": result["percentage"],
        "feedback": result["feedback"],
        "found_keywords":
result["found_keywords"],
        "missing_keywords":
result["missing_keywords"]
    }, "Submitted and graded successfully")
@app.route("/api/assignments/<int:assignment_id>/submissions", methods=["GET"])
@role_required("teacher", "admin")
def list_submissions(current_user,
assignment_id):
    """Teacher views all submissions for an
assignment with grades."""
    assignment = models.get_assignment_by_id(assignment_id)
    if not assignment:
        return err("Assignment not found",404)
    submissions =models.get_submissions_by_assignment(assignment_id)
    # Class analytics
    class_stats =analytics.class_performance_summary(submissions,assignment["max_score"])
    return ok({
        "assignment": assignment,
        "submissions": submissions,
        "analytics": class_stats
    })
# ─── ANALYTICS ROUTES
@app.route("/api/students/<int:student_id>/performance", methods=["GET"])
@login_required
def student_performance(current_user,
student_id):
    """
    Student can view their own performance.
    Teacher/Admin can view any student's
performance.
    """
    if current_user["role"] == "student" and current_user["user_id"] != student_id:
        return err("Access denied", 403)
    course_id = request.args.get("course_id", type=int)
    grades =models.get_student_grades(student_id,course_id)
    summary = analytics.student_performance_summary(grades)
    weak_topics = analytics.identify_weak_topics(grades)
    return ok({
        "grades": grades,
        "summary": summary,
        "weak_topics": weak_topics
    })
@app.route("/api/courses/<int:course_id>/analytics", methods=["GET"])
@role_required("teacher", "admin")
def course_analytics(current_user,
course_id):
    """Teacher dashboard analytics for a
course."""
    course = models.get_course_by_id(course_id)
    if not course:
        return err("Course not found", 404)
    assignments = models.get_assignments_by_course(course_id)
    students = models.get_enrolled_students(course_id)
    # Per-assignment analytics
    assignment_analytics = []
    total_submissions = 0
    for a in assignments:
        subs = models.get_submissions_by_assignment(a["id"])
        total_submissions += len(subs)
        stats = analytics.class_performance_summary(subs,a["max_score"])
        assignment_analytics.append({
            "assignment": a,
            "stats": stats
        })
    engagement = analytics.course_engagement_summary(
        enrollments=len(students),
        submissions=total_submissions,
        assignments=len(assignments)
    )
    return ok({
        "course": course,
        "student_count": len(students),
        "assignment_count":len(assignments),
        "engagement": engagement,
        "assignments": assignment_analytics
    })
# ─── ADMIN ROUTES
@app.route("/api/admin/users", methods=["GET"])
@role_required("admin")
def admin_list_users(current_user):
    """Admin: list all users."""
    users = models.get_all_users()
    return ok(users)
@app.route("/api/admin/stats", methods=["GET"])
@role_required("admin")
def admin_stats(current_user):
    """Admin: platform-wide statistics."""
    stats = models.get_platform_stats()
    return ok(stats)
@app.route("/api/admin/seed", methods=["POST"])
@role_required("admin")
def admin_seed(current_user):
    """Admin: create demo data for
testing."""
    _seed_demo_data()
    return ok(message="Demo data seeded")
# ─── AI / GROQ ROUTES
@app.route("/api/ai/chat", methods=["POST"])
@login_required
def ai_chat(current_user):
    """
    RAG-grounded AI chat. Retrieves
relevant chunks from ChromaDB
    before calling Groq, so answers are
grounded in course material.
    Body: { message: str, course_id: int
(optional), context: str (optional) }
    If course_id is provided and the course
has ingested material,
    the top-3 relevant chunks are prepended
to the prompt.
    Falls back to direct Groq call if no
material is available.
    """
    if not groq_client :
        return err("AI features are not configured. Set GROQ_API_KEY.", 503)
    data, error = require_json("message")
    if error:
        return error
    user_message = data["message"].strip()
    course_id = data.get("course_id")
    context = data.get("context","").strip()
    if not user_message:
        return err("Message cannot be empty", 422)
    if len(user_message) > 2000:
        return err("Message too long. Max 2000 characters.", 422)
    # ── RAG retrieval
    retrieved_chunks = []
    rag_used = False
    if course_id:
        try:
            retrieved_chunks = retrieve(
                query=user_message,
                course_id=int(course_id),
                k=3
            )
            rag_used = len(retrieved_chunks) > 0
        except Exception as e:
            log.warning(f"RAG retrieval failed (falling back to direct): {e}")
    # ── Build prompt
    system_context = (
        f"You are BODH AI, an intelligent teaching assistant. "
        f"You are helping a {current_user['role']}. "
        f"When calling tools, never include student_id in arguments — "
        f"it is always handled server-side. "
        f"Be concise, accurate, and educational."
    )
    if rag_used:
        chunk_text_combined = "\n\n".join(
            f"[Source: {c['source']}]\n{c['text']}" for c in retrieved_chunks)
        prompt = (
            f"{system_context}\n\n"
            f"Use the following course material to answer the question. "
            f"If the material doesn't cover it, say so and answer from generalknowledge.\n\n"
            f"--- COURSE MATERIAL ---\n{chunk_text_combined}\n--- END ---\n\n"
            f"Student question: {user_message}"
        )
    else:
        if context:
            system_context += f" The current topic/course context is:{context}."
        prompt = f"{system_context}\n\nUser: {user_message}"
    
    # ── Groq Call with Tool Caling
    # Debugging line
    try:

        messages = [
            {
                "role": "system",
                "content": system_context
            },
            {
                "role": "user",
                "content": prompt
            }
        ]


        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            tools= tool_service.TOOL_DEFINITIONS,
            tool_choice="auto"
        )


        message = response.choices[0].message


        if message.tool_calls:

            messages.append({
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [
                    {
                        "id": tool_call.id,
                        "type": "function",
                        "function": {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments
                        }
                     
                    }
                    for tool_call in message.tool_calls 
                ]
            })

            for tool_call in message.tool_calls:

                tool_name = tool_call.function.name

                tool_args = json.loads(
                    tool_call.function.arguments
                )
                if tool_name in ("get_student_performance", "flag_weak_topic"):
                    # Inject current_user's ID for security
                    tool_args["student_id"] = current_user["user_id"]

                tool_result = tool_service.execute_tool(
                    tool_name,
                    tool_args
                )

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": tool_result
                    }
                )


            final_response = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages
            )

            answer = final_response.choices[0].message.content.strip()


        else:

            answer = message.content.strip()


    # Logging
        log.info(
            f"AI chat: user={current_user['user_id']}, "
            f"rag={'yes' if rag_used else 'no'}, "
            f"chunks={len(retrieved_chunks)}, "
            f"tools={'yes' if message.tool_calls else 'no'}"
        )


    # ONLY RETURN HERE
        return ok({
        "response": answer,
        "rag_used": rag_used,
        "tool_used":tool_name if message.tool_calls else None,
        "chunks_retrieved": len(retrieved_chunks),
        "sources": list({c["source"] for c in retrieved_chunks})
        })
    except Exception as e:

        log.error(f"Groq error: {e}")

        return err(
            "AI service temporarily unavailable. Please try again.",
        503
        )
        
@app.route("/api/ai/chat/stream", methods=["POST"])
@login_required
def ai_chat_stream(current_user):
    """
    Streaming version of /api/ai/chat.
    Returns Server-Sent Events (SSE) —
tokens arrive as Groq produces them.
    Same RAG logic as /api/ai/chat.
    Body: { message: str, course_id: int
(optional) }
    Client usage (JS):
        const es = new EventSource(...)  //
doesn't support POST, so use fetch with
ReadableStream
        // Or test with: curl -N -X POST
http://localhost:5000/api/ai/chat/stream \
        //   -H "Authorization: Bearer
<token>" \
        //   -H "Content-Type:
application/json" \
        //   -d '{"message": "what is
backpropagation?", "course_id": 1}'
    """
    if not groq_client :
        return err("AI features are not configured. Set GROQ_API_KEY.", 503)
    data, error = require_json("message")
    if error:
        return error
    user_message = data["message"].strip()
    course_id = data.get("course_id")
    if not user_message:
        return err("Message cannot be empty", 422)
    # ── RAG retrieval (same as nonstreaming)
    retrieved_chunks = []
    rag_used = False
    if course_id:
        try:
            retrieved_chunks = retrieve(
                query=user_message,
                course_id=int(course_id),
                k=3)
            rag_used = len(retrieved_chunks) > 0
        except Exception as e:
            log.warning(f"Stream RAG retrieval failed: {e}")
    # ── Build prompt
    system_context = (
        f"You are an AI teaching assistant helping a {current_user['role']} "
        f"with educational questions. Be concise, accurate, and educational."
    )
    if rag_used:
        chunk_text_combined = "\n\n".join(
            f"[Source:{c['source']}]\n{c['text']}" for c in retrieved_chunks)
        prompt = (
            f"{system_context}\n\n"
            f"Use the following course material to answer the question.\n\n"
            f"--- COURSE MATERIAL ---\n{chunk_text_combined}\n--- END ---\n\n"
            f"Student question:{user_message}"
        )
    else:
        prompt = f"{system_context}\n\nUser: {user_message}"
    # ── SSE generator
    def generate():
        try:
        # SSE event
            yield f"data: [META] rag_used={rag_used} chunks={len(retrieved_chunks)}\n\n"
            
            _system = (
                f"You are an AI teaching assistant helping a {current_user['role']} "
                f"with educational questions. Be concise, accurate, and educational."
            )

        # Stream Groq response token by token (new SDK)
            response = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": _system},
                    {"role": "user", "content": prompt}
                ],
                stream=True
            )

            for chunk in response:
                if chunk.choices[0].delta.content:
                    # SSE format: data:<content>\n\n
                    yield f"data: {chunk.choices[0].delta.content}\n\n"

        # Signal end of stream
            yield "data: [DONE]\n\n"

        except Exception as e:
            log.error(f"Stream generation error: {e}")
            yield f"data: [ERROR] {str(e)}\n\n"


    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )
@app.route("/api/ai/generate-content",methods=["POST"])
@role_required("teacher", "admin")
def generate_content(current_user):
    """
    Teacher tool: Generate lesson
summaries, quiz questions, or explanations.
    Body: { type:
'summary'|'quiz'|'explanation', topic: str,
details: str }
    """
    if not groq_client :
        return err("AI features not configured.", 503)
    data, error = require_json("type","topic")
    if error:
        return error
    content_type = data["type"]
    topic = data["topic"].strip()
    details = data.get("details","").strip()
    prompts = {
        "summary": (
            f"Create a clear, structured lesson summary on: {topic}. "
            f"{'Additional context: ' + details if details else ''} "
            f"Include key concepts,definitions, and 3 takeaways. Keep it under300 words."
        ),
        "quiz": (
            f"Generate 5 multiple-choice quiz questions on: {topic}. "
            f"{'Focus on: ' + details if details else ''} "
            f"Format each as: Q) question A) option B) option C) option D) option Answer: X"
        ),
        "explanation": (
            f"Explain the following concept clearly for students: {topic}. "
            f"{'Specific aspect: ' + details if details else ''} "
            f"Use simple language, an analogy, and a concrete example."
        )
    }
    if content_type not in prompts:
        return err("Type must be 'summary','quiz', or 'explanation'", 422)
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "user", "content": prompts[content_type]}
            ]
        )

        return ok({
            "content": response.choices[0].message.content.strip(),
            "type": content_type,
            "topic": topic
        })
    except Exception as e:
        log.error(f"Content generation error: {e}")
        return err("AI service temporarily unavailable.", 503)
# ─── ERROR HANDLERS
@app.errorhandler(404)
def not_found(e):
    return err("Resource not found", 404)
@app.errorhandler(405)
def method_not_allowed(e):
    return err("Method not allowed", 405)
@app.errorhandler(500)
def server_error(e):
    log.error(f"Unhandled server error:{e}")
    return err("Internal server error",500)
# ─── DEMO DATA SEEDER
def _seed_demo_data():
    """Create demo users, courses, and
assignments for development."""
    # Create demo users
    users_data = [
        ("Admin User", "admin@demo.com","admin123", "admin"),
        ("Dr. Priya Sharma",
"teacher@demo.com", "teacher123",
"teacher"),
        ("Rahil Khan", "student@demo.com",
"student123", "student"),
        ("Ananya Singh", "ananya@demo.com",
"student123", "student"),
    ]
    for name, email, password, role in users_data:
        models.create_user(name, email,password, role)
    teacher =models.get_user_by_email("teacher@demo.com")
    student1 =models.get_user_by_email("student@demo.com")
    student2 =models.get_user_by_email("ananya@demo.com")
    if not teacher or not student1:
        return
    # Create courses
    c1 = models.create_course(
        "Introduction to Machine Learning",
        "Fundamentals of ML algorithms,supervised and unsupervised learning.",
        teacher["id"]
    )
    c2 = models.create_course(
        "Python for Data Science",
        "Practical Python programming for data analysis and visualisation.",
        teacher["id"]
    )
    # Enroll students
    models.enroll_student(student1["id"],
c1)
    models.enroll_student(student1["id"],
c2)
    models.enroll_student(student2["id"],
c1)
    # Create assignments
    a1 = models.create_assignment(
        course_id=c1,
        title="Explain SupervisedLearning",
        description="Describe what supervised learning is, give two examples,and explain training vs testing.",
        rubric_keywords="supervisedlearning, labeled data, training, testing,classification, regression, prediction",
        max_score=100,
        due_date="2025-12-31"
    )
    a2 = models.create_assignment(
        course_id=c1,
        title="Neural Networks Basics",
        description="Explain how a neural network learns using backpropagation.",
        rubric_keywords="neural network,backpropagation, weights, loss function,gradient descent, layers, activation",
        max_score=100,
        due_date="2025-12-31"
    )
    a3 = models.create_assignment(
        course_id=c2,
        title="Python List Comprehensions",
        description="Explain list comprehensions and when to use them overloops.",
        rubric_keywords="listcomprehension, iteration, filter,expression, readable, concise, loop",
        max_score=50,
        due_date="2025-12-31"
    )
    # Create sample submissions and autograde them
    sample_answers = [
        (a1, student1["id"],
         "Supervised learning is a type of machine learning where the model is trained on labeled data. "
         "The training set contains inputoutput pairs. The model learns to predictoutputs for new inputs. "
         "Examples include classification tasks like spam detection and regressiontasks like house price prediction. "
         "After training, the model isevaluated on a testing set to measure itsperformance."),
        (a2, student1["id"],
         "A neural network consists of layers of neurons with weights connectingthem. "
         "During training, backpropagationcomputes the gradient of the loss functionwith respect to weights. "
         "Gradient descent then updates theweights to minimise the loss. The activation function introduces nonlinearity."),
        (a3, student1["id"],
         "List comprehensions provide a concise way to create lists in Python. "
         "Instead of writing a loop, you can write an expression in one line. "
         "They are more readable and often faster than equivalent for loops. "
         "You can also filter elements using a condition."),
        (a1, student2["id"],
         "Supervised learning uses labeled examples to train a model to make predictions. "
         "It is used in classification and regression problems.")
    ]
    for assignment_id, student_id, answer in sample_answers:
        assignment = models.get_assignment_by_id(assignment_id)
        if assignment:
            sub_id = models.submit_assignment(assignment_id,student_id, answer)
            result = grading.grade(answer,assignment["rubric_keywords"],assignment["max_score"])
            models.save_grade(sub_id,result["score"], result["feedback"])
    log.info("✅ Demo data seeded")
# ─── ENTRY POINT
if __name__ == "__main__":
    debug = os.getenv("FLASK_ENV","development") == "development"
    port = int(os.getenv("PORT", 5000))
    app.run(debug=debug, port=port,host="0.0.0.0")