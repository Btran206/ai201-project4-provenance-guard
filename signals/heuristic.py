import re
import statistics


def analyze(text: str) -> dict:
    """
    Measures four stylometric features and returns a 0–1 AI-likelihood score.
    A score near 1 means the text looks machine-generated; near 0 means human.
    """
    sentences = _split_sentences(text)
    words = re.findall(r"\b\w+\b", text.lower())

    sub_scores = []
    features = {}

    # --- 1. Sentence-length uniformity ---
    # AI prose tends toward a consistent middle range; humans vary more.
    # Metric: coefficient of variation (std / mean) of per-sentence word counts.
    # Low CV → uniform → higher AI score.
    if len(sentences) >= 2:
        lengths = [len(re.findall(r"\b\w+\b", s)) for s in sentences]
        mean_len = statistics.mean(lengths)
        stdev_len = statistics.stdev(lengths)
        cv = stdev_len / mean_len if mean_len > 0 else 0.0
        # cv=0 → score 1.0 (perfectly uniform); cv≥1.5 → score 0.0
        uniformity_score = max(0.0, 1.0 - cv / 1.5)
    else:
        cv = None
        uniformity_score = 0.5

    features["sentence_length_cv"] = round(cv, 4) if cv is not None else None
    features["sentence_length_uniformity_score"] = round(uniformity_score, 4)
    sub_scores.append(uniformity_score)

    # --- 2. Vocabulary richness (Type-Token Ratio) ---
    # Lower lexical diversity is a soft AI signal.
    # TTR = unique tokens / total tokens; low TTR → higher AI score.
    if words:
        ttr = len(set(words)) / len(words)
        # Invert and clamp: TTR 0→score 1.0, TTR 1→score 0.0
        ttr_score = max(0.0, min(1.0, 1.0 - ttr))
    else:
        ttr = None
        ttr_score = 0.5

    features["type_token_ratio"] = round(ttr, 4) if ttr is not None else None
    features["ttr_score"] = round(ttr_score, 4)
    sub_scores.append(ttr_score)

    # --- 3. Punctuation pattern variance ---
    # Humans use em-dashes, ellipses, !, ? more erratically than AI.
    # Low density of these markers → higher AI score.
    word_count = len(words) if words else 1
    human_punct = (
        text.count("—")   # em-dash —
        + text.count("–") # en-dash –
        + text.count("...")
        + text.count("!")
        + text.count("?")
    )
    punct_density = human_punct / word_count
    # density=0 → score 1.0 (no human markers); density≥0.10 → score 0.0
    punct_score = max(0.0, 1.0 - punct_density / 0.10)

    features["human_punct_density"] = round(punct_density, 4)
    features["punct_score"] = round(punct_score, 4)
    sub_scores.append(punct_score)

    # --- 4. Burstiness ---
    # Humans alternate short punchy sentences with long flowing ones (high B).
    # AI output is metronomically even (B close to –1).
    # Burstiness B = (σ – μ) / (σ + μ) ∈ [–1, 1].
    # Map B to AI score: low B (uniform) → high score.
    if len(sentences) >= 2:
        lengths = [len(re.findall(r"\b\w+\b", s)) for s in sentences]
        mu = statistics.mean(lengths)
        sigma = statistics.stdev(lengths)
        B = (sigma - mu) / (sigma + mu) if (sigma + mu) > 0 else -1.0
        # B=–1 → score 1.0 (perfectly uniform); B=1 → score 0.0 (very bursty)
        burstiness_score = max(0.0, min(1.0, (1.0 - B) / 2.0))
    else:
        B = None
        burstiness_score = 0.5

    features["burstiness_B"] = round(B, 4) if B is not None else None
    features["burstiness_score"] = round(burstiness_score, 4)
    sub_scores.append(burstiness_score)

    final_score = round(sum(sub_scores) / len(sub_scores), 4)
    return {"score": final_score, "features": features}


def _split_sentences(text: str) -> list:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p for p in parts if p.strip()]
