_LABEL_MAP = {
    "high-confidence-ai": (
        "ai",
        "This content was likely generated with AI assistance. "
        "Our system is highly confident in this assessment.",
    ),
    "high-confidence-human": (
        "human",
        "This content appears to be written by a human. "
        "Our system is highly confident in this assessment.",
    ),
    "uncertain": (
        "uncertain",
        "Our system could not confidently determine whether this content was "
        "AI-generated or human-written. The classification is shown as uncertain.",
    ),
}


def fuse(heuristic_score: float, llm_score: float) -> float:
    return round(0.4 * heuristic_score + 0.6 * llm_score, 4)


def classify(confidence: float) -> dict:
    if confidence >= 0.75:
        variant = "high-confidence-ai"
    elif confidence <= 0.25:
        variant = "high-confidence-human"
    else:
        variant = "uncertain"

    classification, text = _LABEL_MAP[variant]
    return {
        "classification": classification,
        "label": {"variant": variant, "text": text},
    }
