<div align="center">

# 🎓 BODH AI — Virtual Teaching Assistant

**Auto-grade assignments. Track student progress. Generate learning content with AI.**

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.0-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)](https://sqlite.org)
[![Gemini](https://img.shields.io/badge/Gemini_1.5_Flash-8E75B2?style=for-the-badge&logo=google&logoColor=white)](https://deepmind.google/technologies/gemini)
[![JWT](https://img.shields.io/badge/JWT_Auth-000000?style=for-the-badge&logo=jsonwebtokens&logoColor=white)](https://jwt.io)
[![Render](https://img.shields.io/badge/Deploy_on_Render-000000?style=for-the-badge&logo=render&logoColor=white)](https://render.com)

🏆 **1st Place — TechXcelerate 2025, BITS Pilani Hyderabad** &nbsp;|&nbsp; 700+ teams &nbsp;|&nbsp; ₹26,000 prize

</div>

---

## What is BODH AI?

BODH AI is a multi-role SaaS backend for educational institutions. Teachers create courses and assignments with rubric keywords. Students submit answers and receive **instant AI-powered grades** with keyword-level feedback. Administrators monitor platform-wide activity in real time.

**The grading pipeline in one sentence:** Student submits text → NLP engine extracts keywords → TF-IDF cosine similarity + keyword coverage → Score + actionable feedback, instantly.

> Built end-to-end in a 24-hour hackathon window and deployed as a production-ready SaaS backend.

---

## Architecture

```
                    ┌─────────────────────────────────────┐
                    │           Flask REST API             │
                    │                                      │
  Client Request ──►│  auth.py      → JWT validation       │
                    │  routes       → role-gated endpoints  │
                    │  models.py    → all DB queries        │
                    │  grading.py   → NLP auto-grader       │
                    │  analytics.py → performance insights  │
                    └──────────────┬──────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────┐
                    │         SQLite Database              │
                    │                                      │
                    │  users → courses → enrollments       │
                    │  assignments → submissions → grades  │
                    └─────────────────────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────┐
                    │         Gemini 1.5 Flash             │
                    │  AI chat + content generation        │
                    └─────────────────────────────────────┘
```

---

## Features

| Role | Capabilities |
|---|---|
| **Student** | Enroll in courses, submit assignments, get instant graded feedback with keyword breakdown, track performance trends, AI chat |
| **Teacher** | Create courses & assignments with rubric keywords, view all submissions, class analytics (avg, pass rate, struggling students), AI content generation (summaries, quizzes, explanations) |
| **Admin** | Platform-wide stats, user management, demo data seeding |

**Auto-grading engine:**
- TF-IDF cosine similarity between student answer and rubric (40% weight)
- Keyword coverage — how many rubric keywords the answer addresses (60% weight)
- Returns: score, percentage, found keywords, missing keywords, actionable feedback
- No external ML libraries — pure Python, zero latency overhead

---

## Project Structure

```
ai-virtual-teaching-assistant/
├── app.py                   # Flask app — all API routes
├── models.py                # Database schema + all queries (3NF)
├── grading.py               # NLP auto-grading engine
├── analytics.py             # Performance analytics
├── auth.py                  # JWT auth + role decorators
├── requirements.txt         # Python dependencies
├── Procfile                 # Render deployment config
├── .env.example             # Environment variable template
├── .gitignore
└── templates/
    ├── index.html           # Landing page + login/register
    ├── dashboard.html       # Student dashboard
    ├── teacher.html         # Teacher dashboard
    └── admin.html           # Admin dashboard
```

---

## API Endpoints

### Auth
| Method | Endpoint | Access | Description |
|---|---|---|---|
| POST | `/api/auth/register` | Public | Register student or teacher |
| POST | `/api/auth/login` | Public | Login, returns JWT |
| GET | `/api/auth/me` | Any | Get current user from token |

### Courses
| Method | Endpoint | Access | Description |
|---|---|---|---|
| GET | `/api/courses` | Any | Student: enrolled courses. Teacher/Admin: all |
| POST | `/api/courses` | Teacher | Create a new course |
| GET | `/api/courses/<id>` | Any | Course detail + assignments |
| POST | `/api/courses/<id>/enroll` | Student | Enroll in a course |
| GET | `/api/courses/<id>/students` | Teacher | List enrolled students |
| GET | `/api/courses/<id>/analytics` | Teacher | Class analytics dashboard |

### Assignments & Submissions
| Method | Endpoint | Access | Description |
|---|---|---|---|
| POST | `/api/courses/<id>/assignments` | Teacher | Create assignment with rubric |
| GET | `/api/assignments/<id>` | Any | Assignment detail + student's submission |
| POST | `/api/assignments/<id>/submit` | Student | Submit answer → auto-graded instantly |
| GET | `/api/assignments/<id>/submissions` | Teacher | All submissions + class analytics |

### Analytics & Admin
| Method | Endpoint | Access | Description |
|---|---|---|---|
| GET | `/api/students/<id>/performance` | Student/Admin | Grade history + weak topics |
| GET | `/api/admin/users` | Admin | All registered users |
| GET | `/api/admin/stats` | Admin | Platform-wide statistics |
| POST | `/api/admin/seed` | Admin | Seed demo data |
| POST | `/api/ai/chat` | Any | AI Q&A chatbot |
| POST | `/api/ai/generate-content` | Teacher | AI lesson/quiz generator |

---

## Database Schema

```sql
users         (id, name, email, password_hash, role, created_at)
courses       (id, title, description, teacher_id, created_at)
enrollments   (id, student_id, course_id, enrolled_at)          ← many-to-many
assignments   (id, course_id, title, description, rubric_keywords, max_score, due_date)
submissions   (id, assignment_id, student_id, content, submitted_at)
grades        (id, submission_id, score, feedback, graded_by, graded_at)
```

Normalised to 3NF — no transitive dependencies. Foreign keys enforced. Grades are decoupled from submissions (single responsibility).

---

## Local Setup

### Prerequisites
- Python 3.11+
- A Gemini API key (free at [aistudio.google.com](https://aistudio.google.com/app/apikey)) — optional, AI features disabled without it

### 1. Clone the repo

```bash
git clone https://github.com/YSRaahil/ai-virtual-teaching-assistant.git
cd ai-virtual-teaching-assistant
```

### 2. Create virtual environment

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set:
```env
SECRET_KEY=any-long-random-string
GEMINI_API_KEY=your_key_here    # optional
```

### 5. Run the app

```bash
python app.py
```

Open [http://localhost:5000](http://localhost:5000)

### 6. Seed demo data (optional)

Register an admin account, log in, go to the Admin dashboard → Demo Data → Seed. This creates:

| Email | Password | Role |
|---|---|---|
| admin@demo.com | admin123 | Admin |
| teacher@demo.com | teacher123 | Teacher |
| student@demo.com | student123 | Student |
| ananya@demo.com | student123 | Student |

---

## Deployment on Render (Free)

### 1. Push to GitHub

```bash
git add .
git commit -m "initial commit"
git push origin main
```

### 2. Create a Render Web Service

- Go to [render.com](https://render.com) → New → Web Service
- Connect your GitHub repo
- Set **Build Command:** `pip install -r requirements.txt`
- Set **Start Command:** `gunicorn app:app --workers 2 --bind 0.0.0.0:$PORT`
- Set **Environment:** Python 3

### 3. Add Environment Variables in Render Dashboard

```
SECRET_KEY        → any long random string
GEMINI_API_KEY    → your Gemini key
FLASK_ENV         → production
FRONTEND_ORIGIN   → your Render URL (e.g. https://bodh-ai.onrender.com)
```

### 4. Deploy

Render auto-deploys on every push to `main`. Your app will be live at `https://your-service.onrender.com`.

> **Note:** Render free tier spins down after inactivity. The first request after spin-down takes ~30 seconds. Upgrade to a paid instance for always-on.

---

## How the Grading Engine Works

```python
# grading.py — simplified flow

def grade(answer, rubric_keywords_str, max_score=100):

    # 1. Tokenize — lowercase, remove stopwords
    answer_tokens = tokenize(answer)
    rubric_tokens = tokenize(rubric_keywords_str)

    # 2. Keyword coverage — did the student hit the rubric points?
    coverage_ratio, found, missing = keyword_coverage(answer_tokens, rubric_keywords)

    # 3. Cosine similarity — is the overall content relevant?
    sim_score = cosine_similarity(tf(answer_tokens), tf(rubric_tokens))

    # 4. Weighted composite score
    composite = (0.6 * coverage_ratio) + (0.4 * sim_score)
    score = round(composite * max_score)

    return { score, feedback, found_keywords, missing_keywords }
```

**Why this weighting?** Keyword coverage (60%) mirrors what human graders prioritise — did the student address the rubric? Cosine similarity (40%) catches answers that use synonyms or paraphrasing without exact keyword matches.

**No external ML libraries.** TF-IDF and cosine similarity are implemented from scratch using Python's `math` and `collections` — zero dependency risk, zero latency overhead.

---

## Design Decisions & Tradeoffs

**SQLite over MySQL in dev:** SQLite requires zero setup — any developer can clone and run with one command. For production with concurrent users, migrate to PostgreSQL (change `DB_PATH` to a connection string and swap `sqlite3` for `psycopg2`).

**Synchronous grading over async queue:** Grading runs synchronously in the submission request. For the current scale this is fine — grading takes <10ms. At scale (1000+ concurrent submissions), move grading to a Celery task queue so the API returns immediately and grades async.

**JWT in Authorization header over cookies:** Simpler for API clients and avoids CSRF complexity. Tradeoff: tokens must be stored client-side (localStorage). For a production health/finance app, HttpOnly cookies are safer.

**No external NLP library (NLTK, spaCy):** TF-IDF from scratch means zero cold-start time and no model download on deploy. Tradeoff: no lemmatisation — "running" and "run" score differently. For higher accuracy, add a simple suffix-stripping stemmer.

**CORS `allow_origins=*` in dev:** Set `FRONTEND_ORIGIN` to your actual domain in production. Never leave `*` with `supports_credentials=True` in production.

---

## Known Limitations & Roadmap

- [ ] Migrate to PostgreSQL for production concurrent writes
- [ ] Add Celery + Redis for async grading queue at scale
- [ ] Add stemming/lemmatisation to improve NLP matching accuracy
- [ ] Input validation with marshmallow schemas (currently basic)
- [ ] Rate limiting per IP (flask-limiter)
- [ ] Unit test coverage (pytest)
- [ ] File upload support for assignment submissions (PDF/DOCX)

---

## Built By

**Syed Mohammad Rahil** — Backend architecture, NLP grading engine, REST API design, auth layer, analytics, deployment

[GitHub](https://github.com/YSRaahil) · [LinkedIn](https://linkedin.com/in/syed-mohammad-rahil)

---

<div align="center">
<sub>Built in 24 hours at TechXcelerate 2025, BITS Pilani Hyderabad. 1st place out of 700+ teams.</sub>
</div>
