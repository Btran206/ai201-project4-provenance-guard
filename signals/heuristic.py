import re
import statistics

_TRANSITION_RE = re.compile(
    r"\b(furthermore|moreover|additionally|consequently|therefore|"
    r"thus|hence|nevertheless|nonetheless|however|in conclusion|"
    r"in summary|to summarize|as a result|on the other hand|"
    r"notably|importantly|it is worth noting|that said|"
    r"firstly|secondly|thirdly|finally|subsequently)\b",
    re.IGNORECASE,
)

PROSE_WEIGHTS = {
    "ttr": 0.13,
    "sentence_length_uniformity": 0.15,
    "human_punctuation": 0.08,
    "structural_punctuation": 0.12,
    "contractions": 0.10,
    "capitalization": 0.06,
    "repeated_sentence_starts": 0.16,
    "transition_density": 0.20,
}

VERSE_WEIGHTS = {
    "ttr": 0.18,
    "human_punctuation": 0.10,
    "structural_punctuation": 0.15,
    "contractions": 0.14,
    "capitalization": 0.08,
    "repeated_sentence_starts": 0.10,
    "transition_density": 0.25,
}

_CONTRACTION_RE = re.compile(
    r"\b(i'm|i've|i'd|i'll|you're|you've|you'd|you'll|he's|he'd|he'll"
    r"|she's|she'd|she'll|it's|we're|we've|we'd|we'll|they're|they've"
    r"|they'd|they'll|that's|that'd|who's|who'd|what's|don't|doesn't"
    r"|didn't|won't|wouldn't|can't|couldn't|isn't|aren't|wasn't|weren't"
    r"|hasn't|haven't|hadn't|shouldn't|mustn't|let's|there's|here's)\b",
    re.IGNORECASE,
)


def analyze(text: str) -> dict:
    """
    Measures stylometric features and returns a 0-1 AI-likelihood score.
    A score near 1 means the text looks machine-generated; near 0 means human.
    signal_confidence reflects how much to trust the score based on text length:
    short texts produce unstable feature values and should be weighted lower.
    For verse inputs, the uniformity feature is skipped (null) because
    structural regularity is a poetic convention, not an AI signal.
    """
    is_verse = _is_verse(text)
    sentences = _split_sentences(text)
    words = re.findall(r"\b\w+\b", text.lower())
    word_count = len(words) if words else 1

    if word_count < 80:
        signal_confidence = "low"
    elif word_count < 250:
        signal_confidence = "medium"
    else:
        signal_confidence = "high"

    scores: dict = {}
    features: dict = {"content_type": "verse" if is_verse else "prose"}

    # --- 2. Type-token ratio (length-gated) ---
    # TTR = unique words / total words. AI text on longer passages tends toward
    # lower TTR (more lexical repetition). Score rises as TTR falls.
    # Calibration: ttr <= 0.35 -> score 1.0, ttr >= 0.70 -> score 0.0.
    # Excluded below 150 words: short passages are nearly all-unique regardless
    # of authorship, so a floored 0.0 here is "no data," not a human signal.
    ttr = len(set(words)) / word_count
    ttr_score = max(0.0, min(1.0, (0.70 - ttr) / 0.35))
    features["ttr"] = round(ttr, 4)
    features["ttr_score"] = round(ttr_score, 4)
    if word_count >= 150:
        scores["ttr"] = ttr_score

    # --- 1. Sentence-length uniformity (prose only) ---
    if not is_verse:
        if len(sentences) >= 2:
            lengths = [len(re.findall(r"\b\w+\b", s)) for s in sentences]
            mean_len = statistics.mean(lengths)
            stdev_len = statistics.stdev(lengths)
            cv = stdev_len / mean_len if mean_len > 0 else 0.0
            uniformity_score = max(0.0, min(1.0, 1.0 - cv / 1.2))
        else:
            cv = None
            uniformity_score = 0.5
        features["sentence_length_cv"] = round(cv, 4) if cv is not None else None
        features["sentence_length_uniformity_score"] = round(uniformity_score, 4)
        scores["sentence_length_uniformity"] = uniformity_score
    else:
        features["sentence_length_cv"] = None
        features["sentence_length_uniformity_score"] = None

    # --- 3. Punctuation pattern variance (always active) ---
    # Humans use ellipses, !, ? more erratically than AI.
    # Em-dash excluded here — tracked separately as an AI signal below.
    # Threshold: 0.05 so even 1-2 markers move the score meaningfully.
    human_punct = (
        text.count("-")
        + text.count("...")
        + text.count("!")
        + text.count("?")
    )
    punct_density = human_punct / word_count
    punct_score = max(0.0, 1.0 - punct_density / 0.05)

    features["human_punct_density"] = round(punct_density, 4)
    features["punct_score"] = round(punct_score, 4)
    scores["human_punctuation"] = punct_score

    # --- 4. Structural punctuation density (always active) ---
    # AI text uses commas, em-dashes, colons, and semicolons heavily for complex
    # clause structures and stylistic asides. Casual human writing uses far fewer.
    # High density -> higher AI score. Threshold: 0.08 (1 per ~12 words).
    comma_count = text.count(",")
    em_dash_count = text.count("—")
    colon_count = text.count(":")
    semicolon_count = text.count(";")
    struct_punct_density = (comma_count + em_dash_count + colon_count + semicolon_count) / word_count
    struct_punct_score = max(0.0, min(1.0, struct_punct_density / 0.08))

    features["comma_count"] = comma_count
    features["em_dash_count"] = em_dash_count
    features["colon_count"] = colon_count
    features["semicolon_count"] = semicolon_count
    features["struct_punct_density"] = round(struct_punct_density, 4)
    features["struct_punct_score"] = round(struct_punct_score, 4)
    scores["structural_punctuation"] = struct_punct_score

    # --- 5. Contractions (always active) ---
    # Contractions are a strong informality marker. AI formal prose avoids them;
    # casual human writing uses them freely. High density -> lower AI score.
    # Threshold: density >= 0.05 (1 contraction per 20 words) -> score 0.0.
    contraction_count = len(_CONTRACTION_RE.findall(text))
    contraction_density = contraction_count / word_count
    contraction_score = max(0.0, 1.0 - contraction_density / 0.05)

    features["contraction_count"] = contraction_count
    features["contraction_density"] = round(contraction_density, 4)
    features["contraction_score"] = round(contraction_score, 4)
    scores["contractions"] = contraction_score

    # --- 6. Capitalization irregularity (always active) ---
    # AI output almost always capitalizes sentence starts and the pronoun "I".
    # Casual human writing online frequently skips both. High irregularity -> low AI score.
    sentence_count = len(sentences) if sentences else 1
    lowercase_starts = sum(1 for s in sentences if s and s[0].islower())
    lowercase_i = len(re.findall(r"\bi\b", text))  # case-sensitive: matches only lowercase i
    total_i = len(re.findall(r"\bi\b", text, re.IGNORECASE))
    irregularity_ratio = (lowercase_starts + lowercase_i) / (sentence_count + max(total_i, 1))
    capitalization_score = max(0.0, 1.0 - irregularity_ratio)

    features["lowercase_sentence_start_ratio"] = round(lowercase_starts / sentence_count, 4)
    features["lowercase_i_ratio"] = round(lowercase_i / max(total_i, 1), 4)
    features["capitalization_score"] = round(capitalization_score, 4)
    scores["capitalization"] = capitalization_score

    # --- 7. Repeated sentence starts (length-gated) ---
    # AI often opens consecutive sentences with the same 1-2 word pattern
    # ("This means...", "This allows...", "This creates...").
    # High repetition ratio -> higher AI score.
    # Excluded below 4 sentences: with too few sentences the ratio is dominated
    # by noise, and a 0.0 ("all openers unique") is "no data," not a human signal.
    starts = []
    for s in sentences:
        tokens = re.findall(r"\b\w+\b", s.lower())
        if len(tokens) >= 2:
            starts.append(" ".join(tokens[:2]))

    if starts:
        repeated_start_ratio = 1.0 - (len(set(starts)) / len(starts))
    else:
        repeated_start_ratio = 0.0

    features["repeated_start_ratio"] = round(repeated_start_ratio, 4)
    features["repeated_start_score"] = round(repeated_start_ratio, 4)
    if len(starts) >= 4:
        scores["repeated_sentence_starts"] = repeated_start_ratio

    # --- 8. Formulaic transition density (always active) ---
    # AI text overuses transitional phrases ("furthermore", "consequently", etc.)
    # at rates humans rarely match outside of formal academic writing.
    # Threshold: 0.04 (1 per 25 words) -> score 1.0.
    transition_count = len(_TRANSITION_RE.findall(text))
    transition_density = transition_count / word_count
    transition_score = max(0.0, min(1.0, transition_density / 0.04))

    features["transition_count"] = transition_count
    features["transition_density"] = round(transition_density, 4)
    features["transition_score"] = round(transition_score, 4)
    scores["transition_density"] = transition_score

    # Renormalize over only the features that actually had enough data to fire.
    # Length-gated features (ttr, repeated_sentence_starts) and verse-skipped
    # uniformity are absent from `scores`; their weight is redistributed across
    # the active features rather than diluting the average with a fake 0.0.
    weights = VERSE_WEIGHTS if is_verse else PROSE_WEIGHTS
    active_weight = sum(weights[k] for k in scores)
    if active_weight > 0:
        final_score = round(sum(scores[k] * weights[k] for k in scores) / active_weight, 4)
    else:
        final_score = 0.5

    features["active_features"] = sorted(scores.keys())
    return {"score": final_score, "signal_confidence": signal_confidence, "features": features}


def _split_sentences(text: str) -> list:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p for p in parts if p.strip()]


def _is_verse(text: str) -> bool:
    lines = [l for l in text.splitlines() if l.strip()]
    if len(lines) < 3:
        return False
    avg_words = sum(len(l.split()) for l in lines) / len(lines)
    short_line_ratio = sum(1 for l in lines if len(l.split()) < 12) / len(lines)
    return avg_words < 10 and short_line_ratio > 0.7
