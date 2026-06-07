"""
grading.py — NLP auto-grading engine
Completely decoupled from Flask. Pure Python. Independently testable.

Approach: TF-IDF cosine similarity + weighted keyword matching.
- Keywords from rubric are the ground truth.
- Student answer is scored on how well it covers the rubric.
- Returns a 0-100 score + human-readable feedback.
"""

import re
import math
from collections import Counter


# Common English stopwords — no external library needed
STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "shall", "can", "need", "this",
    "that", "these", "those", "i", "you", "he", "she", "it", "we", "they",
    "me", "him", "her", "us", "them", "my", "your", "his", "its", "our",
    "their", "what", "which", "who", "when", "where", "how", "why", "not",
    "no", "so", "if", "as", "up", "out", "about", "into", "than", "then",
    "also", "just", "more", "some", "any", "all", "both", "each", "few"
}


def tokenize(text: str) -> list[str]:
    """Lowercase, remove punctuation, split, remove stopwords."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    tokens = text.split()
    return [t for t in tokens if t not in STOPWORDS and len(t) > 2]


def tf(tokens: list[str]) -> dict:
    """Term frequency: count / total."""
    count = Counter(tokens)
    total = len(tokens) if tokens else 1
    return {word: freq / total for word, freq in count.items()}


def cosine_similarity(vec_a: dict, vec_b: dict) -> float:
    """Cosine similarity between two TF vectors."""
    if not vec_a or not vec_b:
        return 0.0
    common = set(vec_a.keys()) & set(vec_b.keys())
    dot = sum(vec_a[w] * vec_b[w] for w in common)
    mag_a = math.sqrt(sum(v ** 2 for v in vec_a.values()))
    mag_b = math.sqrt(sum(v ** 2 for v in vec_b.values()))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def keyword_coverage(answer_tokens: list[str], rubric_keywords: list[str]) -> tuple[float, list[str], list[str]]:
    """
    Check what fraction of rubric keywords appear in the answer.
    Returns: (coverage_ratio, found_keywords, missing_keywords)
    """
    if not rubric_keywords:
        return 1.0, [], []

    answer_set = set(answer_tokens)
    found = []
    missing = []

    for kw in rubric_keywords:
        kw_tokens = tokenize(kw)
        # Keyword is "found" if any of its tokens appear in the answer
        if any(t in answer_set for t in kw_tokens):
            found.append(kw)
        else:
            missing.append(kw)

    coverage = len(found) / len(rubric_keywords)
    return coverage, found, missing


def grade(answer: str, rubric_keywords_str: str, max_score: int = 100) -> dict:
    """
    Main grading function.

    Args:
        answer: Student's submitted text
        rubric_keywords_str: Comma-separated keywords from the assignment rubric
        max_score: Maximum possible score for this assignment

    Returns:
        {
            score: int,
            percentage: float,
            feedback: str,
            found_keywords: list,
            missing_keywords: list,
            similarity_score: float,
            coverage_score: float
        }

    Scoring formula:
        - 60% weight: keyword coverage (did they hit the rubric points?)
        - 40% weight: cosine similarity (is the overall content relevant?)
    This mirrors what a human grader prioritises — rubric coverage matters most.
    """

    # Parse rubric keywords
    rubric_keywords = [
        kw.strip() for kw in rubric_keywords_str.split(",")
        if kw.strip()
    ]

    # Handle empty answer
    if not answer or not answer.strip():
        return {
            "score": 0,
            "percentage": 0.0,
            "feedback": "No answer provided.",
            "found_keywords": [],
            "missing_keywords": rubric_keywords,
            "similarity_score": 0.0,
            "coverage_score": 0.0
        }

    # Tokenize
    answer_tokens = tokenize(answer)
    rubric_tokens = tokenize(rubric_keywords_str)

    # Compute scores
    coverage_ratio, found_kws, missing_kws = keyword_coverage(answer_tokens, rubric_keywords)

    answer_tf = tf(answer_tokens)
    rubric_tf = tf(rubric_tokens)
    sim_score = cosine_similarity(answer_tf, rubric_tf)

    # Weighted composite score (0.0 to 1.0)
    composite = (0.6 * coverage_ratio) + (0.4 * sim_score)
    # Clamp between 0 and 1
    composite = max(0.0, min(1.0, composite))

    raw_score = round(composite * max_score)

    # Generate feedback
    feedback = _generate_feedback(coverage_ratio, sim_score, found_kws, missing_kws, raw_score, max_score)

    return {
        "score": raw_score,
        "percentage": round(composite * 100, 1),
        "feedback": feedback,
        "found_keywords": found_kws,
        "missing_keywords": missing_kws,
        "similarity_score": round(sim_score, 3),
        "coverage_score": round(coverage_ratio, 3)
    }


def _generate_feedback(coverage: float, similarity: float,
                        found: list, missing: list,
                        score: int, max_score: int) -> str:
    """Build a human-readable feedback string from grading metrics."""
    lines = []

    # Overall assessment
    pct = score / max_score if max_score else 0
    if pct >= 0.85:
        lines.append("Excellent work! Your answer comprehensively covers the key concepts.")
    elif pct >= 0.70:
        lines.append("Good answer. You've addressed most of the important points.")
    elif pct >= 0.50:
        lines.append("Satisfactory answer, but there are notable gaps in coverage.")
    elif pct >= 0.30:
        lines.append("Partial credit awarded. Your answer misses several key concepts.")
    else:
        lines.append("Your answer needs significant improvement to meet the rubric requirements.")

    # Keyword feedback
    if found:
        lines.append(f"Concepts covered: {', '.join(found)}.")
    if missing:
        lines.append(f"Missing concepts: {', '.join(missing)}. Review these topics.")

    # Content depth feedback
    if similarity < 0.2 and coverage < 0.5:
        lines.append("Tip: Make sure your answer directly addresses the question topic.")
    elif similarity > 0.6:
        lines.append("Your answer is well-aligned with the expected content.")

    return " ".join(lines)


def batch_grade(submissions: list[dict], rubric_keywords_str: str, max_score: int = 100) -> list[dict]:
    """
    Grade multiple submissions at once.
    Returns list of grading results in same order as input.
    """
    return [
        {**grade(sub.get("content", ""), rubric_keywords_str, max_score),
         "submission_id": sub.get("id")}
        for sub in submissions
    ]
