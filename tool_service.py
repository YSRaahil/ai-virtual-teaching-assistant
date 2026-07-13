"""
tool_service.py — Agentic tool definitions for BODH AI
-------------------------------------------------------
Defines 3 tools that the LLM can call at runtime based on student intent.
Each tool is a plain Python function that queries real DB data.

Tools:
    get_student_performance  — grades, averages, weak/strong areas, trend
    get_course_summary       — course info, materials uploaded, assignment count
    flag_weak_topic          — logs a weak topic and returns study suggestions

Tool schema format follows Groq/OpenAI function calling spec.

Used by:
    app.py — POST /api/ai/chat (tool-enabled path)

Flow:
    1. app.py sends message + TOOL_DEFINITIONS to Groq
    2. Groq returns tool_calls if it decides a tool is needed
    3. app.py calls execute_tool() with the tool name + args
    4. Result is sent back to Groq as a tool message
    5. Groq generates the final answer grounded in real data
"""

import logging
import json
import models
import analytics

log = logging.getLogger(__name__)


# ─── TOOL FUNCTIONS ──────────────────────────────────────────────────────────
# These are plain Python functions. No Flask, no Groq SDK here.
# They take simple args, query the DB, return a dict.

def get_student_performance(student_id: int, course_id: int = None) -> dict:
    """
    Fetch a student's real grade data and compute performance summary.

    Args:
        student_id: The student's user ID.
        course_id:  Optional — filter to a specific course.

    Returns:
        Dict with average_score, total_assignments, strong_areas,
        weak_areas, trend, per_course breakdown.
    """
    grades = models.get_student_grades(student_id, course_id)

    if not grades:
        return {
            "found": False,
            "message": "No graded assignments found for this student yet.",
            "student_id": student_id,
            "course_id": course_id
        }

    summary = analytics.student_performance_summary(grades)
    weak_topics = analytics.identify_weak_topics(grades)

    return {
        "found": True,
        "student_id": student_id,
        "course_id": course_id,
        "average_score": summary["average_score"],
        "total_assignments": summary["total_assignments"],
        "strong_areas": summary["strong_areas"],
        "weak_areas": summary["weak_areas"],
        "weak_topics": weak_topics,
        "trend": summary["trend"],
        "per_course": summary["per_course"]
    }


def get_course_summary(course_id: int) -> dict:
    """
    Fetch course details, uploaded materials, and assignment count.

    Args:
        course_id: The course ID to summarise.

    Returns:
        Dict with course title, description, material count,
        chunk count, assignment count.
    """
    course = models.get_course_by_id(course_id)

    if not course:
        return {
            "found": False,
            "message": f"Course {course_id} not found."
        }

    materials = models.get_materials_by_course(course_id)
    assignments = models.get_assignments_by_course(course_id)

    total_chunks = sum(m.get("chunk_count", 0) for m in materials)

    return {
        "found": True,
        "course_id": course_id,
        "title": course["title"],
        "description": course.get("description", ""),
        "assignment_count": len(assignments),
        "assignments": [
            {
                "id": a["id"],
                "title": a["title"],
                "max_score": a["max_score"],
                "due_date": a.get("due_date")
            }
            for a in assignments
        ],
        "material_count": len(materials),
        "total_chunks_indexed": total_chunks,
        "materials": [m["original_name"] for m in materials]
    }


def flag_weak_topic(student_id: int, topic: str, course_id: int = None) -> dict:
    """
    Flag a topic the student is struggling with.
    Returns targeted study suggestions based on the topic name.

    Args:
        student_id: The student's user ID.
        topic:      The topic to flag (e.g. "gradient descent").
        course_id:  Optional course context.

    Returns:
        Dict with flagged topic and study suggestions.
    """
    log.info(f"Weak topic flagged — student={student_id}, topic='{topic}', course={course_id}")

    # Generate targeted suggestions based on topic keywords
    topic_lower = topic.lower()

    suggestions = []

    if any(k in topic_lower for k in ["gradient", "descent", "optimis", "learning rate"]):
        suggestions = [
            "Review the loss function landscape and how gradients point downhill",
            "Practice computing partial derivatives on simple functions",
            "Experiment with different learning rates in a small notebook"
        ]
    elif any(k in topic_lower for k in ["backprop", "chain rule", "derivative"]):
        suggestions = [
            "Work through the chain rule step by step on a 2-layer network",
            "Implement backprop from scratch for a single neuron",
            "Draw the computational graph and trace gradients manually"
        ]
    elif any(k in topic_lower for k in ["overfit", "regularis", "dropout", "generaliz"]):
        suggestions = [
            "Compare training vs validation loss curves on your assignments",
            "Try adding L2 regularisation to a model and observe the effect",
            "Read about the bias-variance tradeoff in your course material"
        ]
    elif any(k in topic_lower for k in ["sql", "query", "join", "database"]):
        suggestions = [
            "Practice writing JOIN queries on sample datasets",
            "Review the difference between INNER, LEFT, and RIGHT joins",
            "Work through the course assignment examples step by step"
        ]
    else:
        # Generic suggestions for any topic
        suggestions = [
            f"Re-read the course material sections covering '{topic}'",
            f"Try solving 2-3 practice problems specifically on '{topic}'",
            "Ask a clarifying question in the next session"
        ]

    return {
        "flagged": True,
        "student_id": student_id,
        "topic": topic,
        "course_id": course_id,
        "study_suggestions": suggestions,
        "message": f"Topic '{topic}' flagged for follow-up. Study suggestions generated."
    }


# ─── TOOL DEFINITIONS (Groq / OpenAI function calling schema) ────────────────
# Passed to the LLM so it knows what tools are available and when to call them.

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_student_performance",
            "description": (
                "Retrieve a student's real grade data, performance summary, "
                "strong areas, weak areas, and score trend. "
                "Call this when a student asks about their grades, performance, "
                "progress, scores, or what topics they are struggling with."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "student_id": {
                        "type": "integer",
                        "description": "The Student ID.Always pass 0 - the server will fill with the authenticated user's ID."
                    },
                    "course_id": {
                        "type": "integer",
                        "description": "Optional. Filter performance to a specific course ID."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_course_summary",
            "description": (
                "Retrieve course details including title, description, number of assignments, "
                "uploaded study materials, and how much content has been indexed. "
                "Call this when a student asks what a course covers, what materials are available, "
                "or how many assignments there are."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "course_id": {
                        "type": "integer",
                        "description": "The course ID to summarise."
                    }
                },
                "required": ["course_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "flag_weak_topic",
            "description": (
                "Flag a specific topic that the student is struggling with "
                "and return targeted study suggestions. "
                "Call this when a student says they don't understand a specific topic, "
                "asks for help with a concept, or when performance data shows repeated "
                "failures on a particular subject."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "student_id": {
                        "type": "integer",
                        "description": "The Student ID. Always pass 0 - the server will fill with the authenticated user's ID."
                    },
                    "topic": {
                        "type": "string",
                        "description": "The topic the student is struggling with."
                    },
                    "course_id": {
                        "type": "integer",
                        "description": "Optional. The course this topic belongs to."
                    }
                },
                "required": ["topic"]
            }
        }
    }
]


# ─── TOOL EXECUTOR ───────────────────────────────────────────────────────────

# Maps tool name → function
_TOOL_MAP = {
    "get_student_performance": get_student_performance,
    "get_course_summary":      get_course_summary,
    "flag_weak_topic":         flag_weak_topic,
}

def execute_tool(tool_name: str, tool_args: dict) -> str:
    """
    Execute a tool by name with the given arguments.
    Returns the result as a JSON string (required by Groq tool message format).

    Args:
        tool_name: One of the names in TOOL_DEFINITIONS.
        tool_args: Dict of arguments parsed from the LLM's tool_call.

    Returns:
        JSON string of the tool result.

    Called by:
        app.py after Groq returns a tool_call in the chat response.
    """

    fn = _TOOL_MAP.get(tool_name)

    if not fn:
        log.warning(f"Unknown tool called: {tool_name}")
        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    try:
        # ─── Normalize LLM generated arguments ───
        # Groq may return numbers as strings
        if "student_id" in tool_args:
            tool_args["student_id"] = int(tool_args["student_id"])

        if "course_id" in tool_args and tool_args["course_id"] is not None:
            tool_args["course_id"] = int(tool_args["course_id"])

        log.info(
            f"Executing tool: {tool_name} | args: {tool_args}"
        )

        result = fn(**tool_args)

        log.info(
            f"Tool result: {tool_name} → found={result.get('found', True)}"
        )

        return json.dumps(result)

    except TypeError as e:
        log.error(
            f"Tool arg mismatch for {tool_name}: {e}"
        )
        return json.dumps({
            "error": f"Invalid arguments for {tool_name}: {str(e)}"
        })

    except Exception as e:
        log.error(
            f"Tool execution error for {tool_name}: {e}"
        )
        return json.dumps({
            "error": f"Tool failed: {str(e)}"
        })


        