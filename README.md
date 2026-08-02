# Hey, I'm Rahil 👋

![Typing SVG](https://readme-typing-svg.demolab.com?font=Fira+Code&size=22&pause=1000&color=3B82F6&width=600&lines=Python+Backend+Developer;FastAPI+%7C+RAG+%7C+LightGBM+%7C+SHAP;Building+things+that+actually+work.)

I'm a Software Developer based in Hyderabad, India — CSE(AI&ML) Graduated from CBIT,2026.

I build backend systems that are actually production-aware: clean APIs, real data pipelines, and AI integrations that go beyond the tutorial. I care about *why* something works, not just that it works.

🏆 **1st place — TechXcelerate 2025, BITS Pilani Hyderabad** (700+ teams, ₹26,000 prize)

---

## What I work with

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-000000?style=for-the-badge&logo=flask&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL-4479A1?style=for-the-badge&logo=mysql&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![React](https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)
![ChromaDB](https://img.shields.io/badge/ChromaDB-Vector_DB-FF6B35?style=for-the-badge)
![Pandas](https://img.shields.io/badge/Pandas-150458?style=for-the-badge&logo=pandas&logoColor=white)
![NumPy](https://img.shields.io/badge/NumPy-013243?style=for-the-badge&logo=numpy&logoColor=white)
![Git](https://img.shields.io/badge/Git-F05032?style=for-the-badge&logo=git&logoColor=white)
![Postman](https://img.shields.io/badge/Postman-FF6C37?style=for-the-badge&logo=postman&logoColor=white)
![VS Code](https://img.shields.io/badge/VS%20Code-007ACC?style=for-the-badge&logo=visual-studio-code&logoColor=white)

---

## Projects worth looking at

### 🔐 PhishGuard — ML-Powered Phishing Detection API

![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)
![LightGBM](https://img.shields.io/badge/LightGBM-00B4D8?style=flat-square)
![SHAP](https://img.shields.io/badge/SHAP-Explainability-orange?style=flat-square)

> Real-time URL phishing detection with explainability built in. Every prediction returns a SHAP breakdown showing *why* a URL was flagged — not just a risk score.

- Engineered **44 lexical, structural & behavioural features** per URL (Shannon entropy, IP detection, redirect chains, TLD type)

- **50-trial Optuna** hyperparameter search + 5-fold stratified cross-validation → **95%+ accuracy**

- Single + batch prediction endpoints (up to 100 URLs), Pydantic validation, per-request SHAP explanations

[![View Repo](https://img.shields.io/badge/View%20Repo-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/YSRaahil/Phishing-Website-Detection-)

---

### 🎓 BODH AI — RAG-Powered Virtual Teaching Assistant

![Flask](https://img.shields.io/badge/Flask-000000?style=flat-square&logo=flask&logoColor=white)
![Groq](https://img.shields.io/badge/Groq-LLaMA_3.3_70B-F55036?style=flat-square&logo=groq&logoColor=white)
![ChromaDB](https://img.shields.io/badge/ChromaDB-Vector_Store-FF6B35?style=flat-square)
![JWT](https://img.shields.io/badge/JWT_Auth-000000?style=flat-square&logo=jsonwebtokens&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white)
![CI](https://github.com/YSRaahil/ai-virtual-teaching-assistant/actions/workflows/ci.yml/badge.svg)
![Render](https://img.shields.io/badge/Live_on_Render-000000?style=flat-square&logo=render&logoColor=white)
![Hackathon](https://img.shields.io/badge/🏆%201st%20Place-TechXcelerate%202025-gold?style=flat-square)

> Started as a 24-hour hackathon MVP, rebuilt into a production-grade backend with a full RAG pipeline, agentic tool calling, and a custom eval framework. Teachers upload course PDFs; students get answers grounded in that material — not the model's generic knowledge — and assignments are auto-graded in real time.

- **RAG pipeline**: all-MiniLM-L6-v2 embeddings → ChromaDB (persistent, per-course collections) → top-k retrieval before every AI response
- **Agentic tool calling**: Groq LLaMA 3.3 70B decides at runtime whether to answer from retrieved content or call a tool (`get_student_performance`, `get_course_summary`, `flag_weak_topic`) — with tool arguments overwritten server-side from the JWT to prevent the LLM from ever controlling whose data gets fetched
- **SSE streaming** endpoint for token-by-token AI responses
- **Custom eval framework** (built from scratch, no RAGAS): 20 test cases across RAG + tool-calling scenarios — Answer Relevance 81.8%, Context Precision 89.8%, Faithfulness 90.2%, Tool Accuracy 100%
- **84 pytest tests** across 5 files (unit + integration) + **GitHub Actions CI** running tests and a Docker build on every push, pushed to **ghcr.io**
- NLP auto-grader (TF-IDF + keyword coverage, zero external ML libs) cut manual evaluation effort by 40–50% in demo testing
- Role-based access control enforced at the API layer across 24 REST endpoints, containerised and **live on Render**

[![View Repo](https://img.shields.io/badge/View%20Repo-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/YSRaahil/ai-virtual-teaching-assistant)
[![Live Demo](https://img.shields.io/badge/Live%20Demo-000000?style=for-the-badge&logo=render&logoColor=white)](https://ai-virtual-teaching-assistant.onrender.com)

---

### 🎤 HealthMate — AI Voice Agent for Health Q&A

![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)
![AssemblyAI](https://img.shields.io/badge/AssemblyAI-5B4FE9?style=flat-square)
![RAG](https://img.shields.io/badge/RAG-VectorDB-blueviolet?style=flat-square)
![React](https://img.shields.io/badge/React-20232A?style=flat-square&logo=react&logoColor=61DAFB)

> Speak a health question, get a grounded, source-backed answer in real time. Built to solve the hallucination problem in medical AI by anchoring every response in a curated knowledge base.

- Full voice pipeline: **AssemblyAI** transcription → semantic retrieval → LLM generation → React frontend
- **RAG with metadata-filtered vector search** — no hallucinated medical answers
- Async streaming with intermediate UI states so the app never feels frozen

[![View Repo](https://img.shields.io/badge/View%20Repo-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/YSRaahil/healthmate-ai-voice-agent)

---

## Currently working on

- 🔧 JobPulse — data engineering project (Kafka, Celery, TimescaleDB, FastAPI)
- 🚦 Rate-limited API Gateway (FastAPI, Redis, Lua scripting, token bucket algorithm)
- 📊 LeetCode grind — consistent DSA practice
- 🎯 Targeting AI Engineer, ML Engineer, and backend/SWE roles at product companies

---

## A bit more about me

- I co-founded a small creative agency ([Renderera.Visuals](https://www.instagram.com/renderera.visuals)) — so I know how to talk to clients, not just compilers
- I debug systematically, not by guessing — profiling before optimising is a hill I'll die on
- More interested in building things that solve real problems than in tech for its own sake

---

## Let's connect

[![LinkedIn](https://img.shields.io/badge/LinkedIn-0A66C2?style=for-the-badge&logo=linkedin&logoColor=white)](#)
[![Gmail](https://img.shields.io/badge/Gmail-EA4335?style=for-the-badge&logo=gmail&logoColor=white)](mailto:mohammadrahilsyed@gmail.com)
[![GitHub](https://img.shields.io/badge/GitHub-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/YSRaahil)

📍 Hyderabad, India — open to remote and relocation

![Visitor Count](https://komarev.com/ghpvc/?username=YSRaahil&color=3B82F6&style=flat-square&label=Profile+Views)

*If you're here from a job application — BODH AI has the most technical depth (RAG + agentic AI + evals + CI/CD).*
