"""
analytics.py — Performance analytics engine
Decoupled from Flask. Takes raw data, returns insights.
No DB calls here — data is passed in from routes.
"""

from collections import defaultdict


def student_performance_summary(grades: list[dict]) -> dict:
    """
    Summarise a student's grades across all assignments.

    Returns:
        - average_score: overall average percentage
        - total_assignments: how many graded
        - strong_areas: courses/assignments scoring >= 75%
        - weak_areas: courses/assignments scoring < 50%
        - trend: 'improving', 'declining', 'stable' based on last 3 scores
        - per_course: breakdown by course
    """
    if not grades:
        return {
            "average_score": 0,
            "total_assignments": 0,
            "strong_areas": [],
            "weak_areas": [],
            "trend": "no data",
            "per_course": {}
        }

    scores = []
    strong = []
    weak = []
    per_course = defaultdict(list)

    for g in grades:
        pct = (g["score"] / g["max_score"] * 100) if g["max_score"] else 0
        scores.append(pct)

        label = f"{g['assignment_title']} ({g['course_title']})"
        if pct >= 75:
            strong.append(label)
        elif pct < 50:
            weak.append(label)

        per_course[g["course_title"]].append(pct)

    avg = round(sum(scores) / len(scores), 1)

    # Trend: compare average of last 3 vs previous 3
    trend = "stable"
    if len(scores) >= 4:
        recent = sum(scores[-3:]) / 3
        earlier = sum(scores[:-3][-3:]) / min(3, len(scores) - 3)
        if recent > earlier + 5:
            trend = "improving"
        elif recent < earlier - 5:
            trend = "declining"

    # Per-course averages
    course_summary = {
        course: round(sum(s) / len(s), 1)
        for course, s in per_course.items()
    }

    return {
        "average_score": avg,
        "total_assignments": len(scores),
        "strong_areas": strong,
        "weak_areas": weak,
        "trend": trend,
        "per_course": course_summary
    }


def class_performance_summary(submissions: list[dict], max_score: int = 100) -> dict:
    """
    Summarise class performance on a single assignment.

    Returns:
        - average_score
        - highest_score
        - lowest_score
        - submission_count
        - graded_count
        - pass_rate: % scoring >= 50%
        - distribution: score buckets (0-25, 25-50, 50-75, 75-100)
        - top_students: names of students scoring >= 75%
        - struggling_students: names scoring < 50%
    """
    graded = [s for s in submissions if s.get("score") is not None]

    if not graded:
        return {
            "average_score": 0,
            "highest_score": 0,
            "lowest_score": 0,
            "submission_count": len(submissions),
            "graded_count": 0,
            "pass_rate": 0,
            "distribution": {"0-25": 0, "25-50": 0, "50-75": 0, "75-100": 0},
            "top_students": [],
            "struggling_students": []
        }

    scores = [s["score"] for s in graded]
    percentages = [(s / max_score * 100) if max_score else 0 for s in scores]

    distribution = {"0-25": 0, "25-50": 0, "50-75": 0, "75-100": 0}
    top_students = []
    struggling = []

    for s, pct in zip(graded, percentages):
        name = s.get("student_name", "Unknown")
        if pct < 25:
            distribution["0-25"] += 1
        elif pct < 50:
            distribution["25-50"] += 1
            struggling.append(name)
        elif pct < 75:
            distribution["50-75"] += 1
        else:
            distribution["75-100"] += 1
            top_students.append(name)

        if pct < 50:
            struggling.append(name)

    # Deduplicate struggling (added twice for <25 + <50 logic above)
    struggling = list(set(
        s.get("student_name", "Unknown")
        for s, pct in zip(graded, percentages)
        if pct < 50
    ))
    top_students = list(set(
        s.get("student_name", "Unknown")
        for s, pct in zip(graded, percentages)
        if pct >= 75
    ))

    pass_rate = round(sum(1 for p in percentages if p >= 50) / len(percentages) * 100, 1)

    return {
        "average_score": round(sum(scores) / len(scores), 1),
        "highest_score": max(scores),
        "lowest_score": min(scores),
        "submission_count": len(submissions),
        "graded_count": len(graded),
        "pass_rate": pass_rate,
        "distribution": distribution,
        "top_students": top_students,
        "struggling_students": struggling
    }


def identify_weak_topics(grades: list[dict]) -> list[str]:
    """
    Identify topics (from missing_keywords in feedback) that a student
    consistently struggles with across assignments.

    Since feedback contains "Missing concepts: X, Y, Z", parse these out
    and return the most frequently missing concepts.
    """
    import re
    topic_count = defaultdict(int)

    for g in grades:
        feedback = g.get("feedback", "")
        match = re.search(r"Missing concepts: ([^.]+)\.", feedback)
        if match:
            topics = [t.strip() for t in match.group(1).split(",")]
            for t in topics:
                if t:
                    topic_count[t] += 1

    # Return topics that appeared as missing in >= 2 assignments
    weak = [topic for topic, count in topic_count.items() if count >= 2]
    return sorted(weak, key=lambda t: -topic_count[t])


def course_engagement_summary(enrollments: int, submissions: int, assignments: int) -> dict:
    """
    Simple engagement metrics for a course.
    """
    if assignments == 0 or enrollments == 0:
        return {"submission_rate": 0, "engagement_level": "no data"}

    expected = enrollments * assignments
    rate = round((submissions / expected * 100), 1) if expected else 0

    if rate >= 80:
        level = "high"
    elif rate >= 50:
        level = "medium"
    else:
        level = "low"

    return {
        "submission_rate": rate,
        "engagement_level": level
    }
