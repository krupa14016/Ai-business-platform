import os
import re
import requests


OLLAMA_URL = os.getenv(
    "OLLAMA_BASE_URL",
    "http://localhost:11434"
)

OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "qwen2.5:3b"
)


# Claims that require explicit support in the verified answer.
CLAIM_GROUPS = [
    ("increased", "increase", "increasing", "increases"),
    ("decreased", "decrease", "decreasing", "decreases"),
    ("grew", "grow", "growth", "growing"),
    ("higher", "high", "highest"),
    ("lower", "low", "lowest"),
    ("improved", "improve", "improving", "improvement"),
    ("declined", "decline", "declining"),
    ("rose", "rise", "rising"),
    ("fell", "fall", "falling"),
    ("more",),
    ("less",),
    ("compared", "compare", "comparison"),
    ("previous",),
    ("historically", "historical", "history"),
]

def _numbers(text):
    """Extract numeric values, treating FY2023 and 2023 as equivalent."""

    normalized_text = re.sub(
        r"\bFY\s*(\d{4})\b",
        r"\1",
        text,
        flags=re.IGNORECASE
    )

    matches = re.findall(
        r"(?<![A-Za-z0-9])\$?\d[\d,]*(?:\.\d+)?%?x?",
        normalized_text
    )

    return {
        value.replace(",", "").replace("$", "").replace("%", "").replace("x", "")
        for value in matches
    }

def _is_supported_explanation(explanation, verified_answer):
    """
    Reject unsupported numerical values and financial claims.
    """

    explanation_numbers = _numbers(explanation)
    verified_numbers = _numbers(verified_answer)

    if not explanation_numbers.issubset(verified_numbers):
        return False

    explanation_lower = explanation.lower()
    verified_lower = verified_answer.lower()

    for group in CLAIM_GROUPS:
        explanation_uses_claim = any(
            re.search(r"\b" + re.escape(word) + r"\b", explanation_lower)
            for word in group
        )

        verified_supports_claim = any(
            re.search(r"\b" + re.escape(word) + r"\b", verified_lower)
            for word in group
        )

        if explanation_uses_claim and not verified_supports_claim:
            return False

    return True

def explain_verified_result(question, verified_result):
    """
    Generate a concise explanation of a verified financial result.

    PostgreSQL remains the source of truth.
    Unsupported Ollama explanations are rejected.
    """

    if verified_result.get("status") != "success":
        return None

    # Do not ask the model to explain greetings or latest-only trends.
    allowed_intents = {
        "financial_lookup",
        "comparison",
        "best_year",
    }

    if verified_result.get("intent") not in allowed_intents:
        return None

    verified_answer = verified_result.get("answer", "").strip()

    if not verified_answer:
        return None

    payload = {
        "model": OLLAMA_MODEL,
        "stream": False,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You explain verified financial answers. "
                    "The supplied answer is the complete and only source of facts. "
                    "Restate it in simple, natural English. "
                    "Do not infer trends, causes, rankings, historical records, "
                    "or comparisons unless explicitly stated in the supplied answer. "
                    "Do not add any numbers, dates, percentages, or financial facts. "
                    "Do not calculate or change values. "
                    "Use at most two short sentences. "
                    "If a simple restatement is not possible, repeat the supplied "
                    "answer without adding information."
                )
            },
            {
                "role": "user",
                "content": (
                    f"Question: {question}\n\n"
                    f"Verified answer:\n{verified_answer}\n\n"
                    "Restate only the verified answer simply."
                )
            }
        ]
    }

    response = requests.post(
        f"{OLLAMA_URL}/api/chat",
        json=payload,
        timeout=(5, 120)
    )

    response.raise_for_status()

    response_data = response.json()

    explanation = (
        response_data.get("message", {})
        .get("content", "")
        .strip()
    )

    if not explanation:
        raise RuntimeError("Ollama returned an empty explanation.")


    if not _is_supported_explanation(explanation, verified_answer):
        print("Ollama explanation rejected: unsupported information detected.")
        return None

    return explanation
