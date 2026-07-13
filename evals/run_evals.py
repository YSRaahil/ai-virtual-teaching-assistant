"""
run_evals.py — Offline evaluation framework for BODH AI
---------------------------------------------------------
Measures RAG pipeline quality and tool-calling accuracy.
Runs as a standalone script — NOT part of the live API.

Metrics:
    1. Answer Relevance   — does the answer address the question?
    2. Context Precision  — are retrieved chunks relevant to the query?
    3. Faithfulness       — does the answer stay within retrieved context?
    4. Tool Accuracy      — did the right tool get called? (tool test cases)

Usage:
    python evals/run_evals.py

Output:
    - Console summary with per-case scores
    - results/eval_report_{timestamp}.json
    - results/eval_summary_{timestamp}.txt

Requirements:
    Server does NOT need to be running.
    All calls go directly through rag_service and tool_service.
    Set GROQ_API_KEY in .env before running.
"""

import os
import sys
import json
import time
import datetime
import requests

# ── Path setup — run from project root ───────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from groq import Groq
from rag_service import retrieve
import tool_service

# ── Config ───────────────────────────────────────────────────────────────────

GROQ_API_KEY   = os.getenv("GROQ_API_KEY")
MODEL          = "llama-3.3-70b-versatile"
TEST_CASES_PATH = os.path.join(os.path.dirname(__file__), "test_cases.json")
RESULTS_DIR    = os.path.join(os.path.dirname(__file__), "results")
STUDENT_ID     = 4    # Test student ID from seeded demo data
TARGET_SCORE   = 80.0 # Target: > 80% across all metrics

os.makedirs(RESULTS_DIR, exist_ok=True)

if not GROQ_API_KEY:
    print("❌ GROQ_API_KEY not set in .env")
    sys.exit(1)

groq_client = Groq(api_key=GROQ_API_KEY)

# ── Metric functions ──────────────────────────────────────────────────────────

def score_answer_relevance(question: str, answer: str, expected_topics: list) -> float:
    """
    Answer Relevance — does the answer address the question?

    Method: Check how many expected topic keywords appear in the answer.
    Score = matched_topics / total_expected_topics * 100

    This is a keyword-overlap proxy for semantic relevance.
    Good enough for a custom eval without RAGAS dependency.
    """
    if not answer or not expected_topics:
        return 0.0

    answer_lower = answer.lower()
    matched = sum(
        1 for topic in expected_topics
        if any(word.lower() in answer_lower for word in topic.split())
    )
    return round((matched / len(expected_topics)) * 100, 1)


def score_context_precision(question: str, chunks: list, expected_keywords: list) -> float:
    """
    Context Precision — are the retrieved chunks relevant to the query?

    Method: For each chunk, check if it contains any expected keywords.
    Score = relevant_chunks / total_chunks * 100

    A chunk is considered relevant if it contains at least 1 expected keyword.
    """
    if not chunks:
        return 0.0  # no chunks retrieved — precision is 0

    if not expected_keywords:
        return 100.0

    relevant = 0
    for chunk in chunks:
        chunk_text = chunk.get("text", "").lower()
        if any(kw.lower() in chunk_text for kw in expected_keywords):
            relevant += 1

    return round((relevant / len(chunks)) * 100, 1)


def score_faithfulness(answer: str, chunks: list) -> float:
    """
    Faithfulness — does the answer stay within the retrieved context?

    Method: Extract key noun phrases from the answer and check what
    fraction appear in the retrieved chunks. Approximated by checking
    multi-word sequences from the answer against chunk text.

    Score = answer_words_found_in_chunks / total_answer_words * 100
    Capped: answers with no chunks get 0 (can't be faithful to nothing).
    """
    if not chunks:
        return 0.0  # no context = can't measure faithfulness

    if not answer:
        return 0.0

    # Combine all chunk text
    all_chunk_text = " ".join(c.get("text", "") for c in chunks).lower()

    # Extract meaningful words from answer (filter stop words)
    stop_words = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been",
        "to", "of", "and", "in", "that", "it", "for", "on", "with",
        "as", "at", "by", "from", "or", "but", "not", "this", "can",
        "will", "would", "could", "should", "may", "might", "do", "does"
    }

    answer_words = [
        w.strip(".,!?;:\"'()[]") for w in answer.lower().split()
        if len(w) > 4 and w.lower() not in stop_words
    ]

    if not answer_words:
        return 50.0  # short answers — neutral score

    found = sum(1 for w in answer_words if w in all_chunk_text)
    return round((found / len(answer_words)) * 100, 1)


def score_tool_accuracy(tool_used: str, expected_tool: str) -> float:
    """
    Tool Accuracy — did the model call the right tool?
    Binary: 100 if correct, 0 if wrong or no tool called.
    """
    if not expected_tool:
        return 100.0  # no tool expected — N/A, count as pass
    if tool_used == expected_tool:
        return 100.0
    return 0.0


# ── RAG pipeline (mirrors what app.py does) ───────────────────────────────────

def run_rag_pipeline(question: str, course_id: int) -> tuple:
    """
    Run retrieval + generation for a question.
    Returns: (answer, chunks, tool_used)
    """
    # Retrieve
    chunks = []
    if course_id:
        try:
            chunks = retrieve(query=question, course_id=course_id, k=3)
        except Exception as e:
            print(f"   ⚠️  Retrieval failed: {e}")

    # Build prompt
    system_prompt = (
        "You are BODH AI, an intelligent teaching assistant. "
        "Answer the student's question based on the provided course material. "
        "Be concise and accurate."
    )

    if chunks:
        context = "\n\n".join(
            f"[Source: {c['source']}]\n{c['text']}" for c in chunks
        )
        user_content = (
            f"Course material:\n--- START ---\n{context}\n--- END ---\n\n"
            f"Question: {question}"
        )
    else:
        user_content = question

    # Generate
    response = groq_client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_content}
        ],
        max_tokens=512
    )

    answer = response.choices[0].message.content.strip()
    return answer, chunks, None


def run_tool_pipeline(question: str, course_id: int) -> tuple:
    """
    Run tool-calling pipeline for a question.
    Returns: (answer, chunks, tool_used)
    """
    system_prompt = (
        "You are BODH AI, an intelligent teaching assistant. "
        "When a student asks about grades, performance, or weak topics, use get_student_performance. "
        "When asked about course content or materials, use get_course_summary. "
        "When a student struggles with a concept, use flag_weak_topic. "
        "IMPORTANT: Do NOT pass student_id — it is injected server-side."
    )

    chunks = []
    if course_id:
        try:
            chunks = retrieve(query=question, course_id=course_id, k=3)
        except Exception:
            pass

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": question}
    ]

    response = groq_client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=tool_service.TOOL_DEFINITIONS,
        tool_choice="auto",
        max_tokens=512
    )

    message   = response.choices[0].message
    tool_used = None

    if message.tool_calls:
        messages.append({
            "role": "assistant",
            "content": message.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                }
                for tc in message.tool_calls
            ]
        })

        for tc in message.tool_calls:
            tool_name = tc.function.name
            tool_args = json.loads(tc.function.arguments)
            tool_used = tool_name

            # Inject student_id
            if tool_name in ("get_student_performance", "flag_weak_topic"):
                tool_args["student_id"] = STUDENT_ID

            # Cast course_id to int — model may pass string or placeholder
            if "course_id" in tool_args:
                try:
                    val = int(str(tool_args["course_id"]).strip())
                    if val <= 0:
                        tool_args.pop("course_id")
                    else:
                        tool_args["course_id"] = val
                except (ValueError, TypeError):
                    tool_args.pop("course_id")  # remove placeholder strings

            tool_result = tool_service.execute_tool(tool_name, tool_args)

            messages.append({
                "role":         "tool",
                "tool_call_id": tc.id,
                "content":      tool_result
            })

        final = groq_client.chat.completions.create(
            model=MODEL,
            messages=messages,
            max_tokens=512
        )
        answer = final.choices[0].message.content.strip()
    else:
        answer = message.content.strip() if message.content else ""

    return answer, chunks, tool_used


# ── Main eval loop ────────────────────────────────────────────────────────────

def run_evals():
    print("\n" + "="*60)
    print("  BODH AI — Evaluation Framework")
    print(f"  Model: {MODEL}")
    print(f"  Target: >{TARGET_SCORE}% across all metrics")
    print("="*60 + "\n")

    with open(TEST_CASES_PATH) as f:
        test_cases = json.load(f)

    results   = []
    total_relevance  = []
    total_precision  = []
    total_faithfulness = []
    total_tool_acc   = []

    for i, tc in enumerate(test_cases):
        tc_id       = tc["id"]
        question    = tc["question"]
        category    = tc["category"]
        course_id   = tc.get("course_id")
        expected_tool = tc.get("expected_tool")

        print(f"[{i+1:02d}/{len(test_cases)}] {tc_id} — {question[:55]}...")

        try:
            if category == "tool":
                answer, chunks, tool_used = run_tool_pipeline(question, course_id)
            else:
                answer, chunks, tool_used = run_rag_pipeline(question, course_id)

            # Score
            relevance    = score_answer_relevance(question, answer, tc["expected_topics"])
            precision    = score_context_precision(question, chunks, tc["expected_context_keywords"])
            tool_acc     = score_tool_accuracy(tool_used, expected_tool)

            # Faithfulness only applies to RAG cases — tool answers come from DB not chunks
            faithfulness = score_faithfulness(answer, chunks) if category == "rag" else None

            total_relevance.append(relevance)
            if category == "rag":
                total_precision.append(precision)
            if faithfulness is not None:
                total_faithfulness.append(faithfulness)
            if expected_tool:
                total_tool_acc.append(tool_acc)

            faith_str = f"{faithfulness}%" if faithfulness is not None else "n/a"
            status = "✅" if relevance >= TARGET_SCORE else "⚠️ "
            print(f"   {status} relevance={relevance}% | precision={precision}% | "
                  f"faithfulness={faith_str} | tool={tool_used or 'none'} "
                  f"(expected={expected_tool or 'none'})")

            results.append({
                "id":            tc_id,
                "category":      category,
                "question":      question,
                "answer":        answer,
                "chunks_retrieved": len(chunks),
                "tool_used":     tool_used,
                "expected_tool": expected_tool,
                "scores": {
                    "answer_relevance":  relevance,
                    "context_precision": precision,
                    "faithfulness":      faithfulness,
                    "tool_accuracy":     tool_acc
                }
            })

            # Rate limit — avoid hitting Groq too fast
            time.sleep(1.5)

        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            results.append({
                "id": tc_id, "question": question,
                "error": str(e), "scores": {}
            })
            time.sleep(2)

    # ── Aggregate scores ──────────────────────────────────────────────────────
    avg_relevance    = round(sum(total_relevance) / len(total_relevance), 1) if total_relevance else 0
    avg_precision    = round(sum(total_precision) / len(total_precision), 1) if total_precision else 0
    avg_faithfulness = round(sum(total_faithfulness) / len(total_faithfulness), 1) if total_faithfulness else 0
    avg_tool_acc     = round(sum(total_tool_acc) / len(total_tool_acc), 1) if total_tool_acc else 0

    passed = sum(1 for r in results if r.get("scores", {}).get("answer_relevance", 0) >= TARGET_SCORE)

    summary = {
        "timestamp":         datetime.datetime.now().isoformat(),
        "model":             MODEL,
        "total_cases":       len(test_cases),
        "passed":            passed,
        "target_score":      TARGET_SCORE,
        "aggregate_scores": {
            "answer_relevance":  avg_relevance,
            "context_precision": avg_precision,
            "faithfulness":      avg_faithfulness,
            "tool_accuracy":     avg_tool_acc
        },
        "results": results
    }

    # ── Save report ───────────────────────────────────────────────────────────
    ts        = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = os.path.join(RESULTS_DIR, f"eval_report_{ts}.json")
    txt_path  = os.path.join(RESULTS_DIR, f"eval_summary_{ts}.txt")

    with open(json_path, "w") as f:
        json.dump(summary, f, indent=2)

    txt_report = f"""
BODH AI — Eval Report
=====================
Timestamp : {summary['timestamp']}
Model     : {MODEL}
Cases     : {len(test_cases)} total | {passed} passed (>={TARGET_SCORE}%)

SCORES
------
Answer Relevance  : {avg_relevance}%   {'✅' if avg_relevance >= TARGET_SCORE else '❌'} (target: >{TARGET_SCORE}%)
Context Precision : {avg_precision}%   {'✅' if avg_precision >= TARGET_SCORE else '❌'}
Faithfulness      : {avg_faithfulness}%   {'✅' if avg_faithfulness >= TARGET_SCORE else '❌'}
Tool Accuracy     : {avg_tool_acc}%   {'✅' if avg_tool_acc >= TARGET_SCORE else '❌'}
"""

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(txt_report)

    # ── Print summary ─────────────────────────────────────────────────────────
    print("\n" + "="*60)
    print(txt_report)
    print(f"  JSON report : {json_path}")
    print(f"  TXT summary : {txt_path}")
    print("="*60 + "\n")

    if avg_relevance >= TARGET_SCORE:
        print(f"✅ Target met — Answer Relevance {avg_relevance}% >= {TARGET_SCORE}%")
    else:
        print(f"⚠️  Below target — Answer Relevance {avg_relevance}% < {TARGET_SCORE}%")
        print("   Try: increase k from 3 to 5 in retrieve(), or increase chunk overlap")


if __name__ == "__main__":
    run_evals()