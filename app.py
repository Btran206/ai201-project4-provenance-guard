from flask import Flask, request, jsonify
from dotenv import load_dotenv
import uuid
from datetime import datetime, timezone

from signals.heuristic import analyze as heuristic_analyze
import store
from store import get_log, insert_audit_log, update_content_status

load_dotenv()

app = Flask(__name__)
store.init_db()


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/log")
def log():
    return jsonify({"entries": get_log()})


@app.route("/submit", methods=["POST"])
def submit():
    body = request.get_json(silent=True)
    if not body or not body.get("content", "").strip():
        return jsonify({"error": "content field is required"}), 400

    content = body["content"]
    creator_id = body.get("creator_id")
    content_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    store.insert_content(content_id, content, creator_id, timestamp)

    heuristic_result = heuristic_analyze(content)

    # LLM signal stubbed for M1 — replaced in M2
    llm_result = {"score": 0.5, "reasoning": "LLM signal not yet implemented"}

    heuristic_score = heuristic_result["score"]
    llm_score = llm_result["score"]
    confidence = round(0.4 * heuristic_score + 0.6 * llm_score, 4)

    # M1: classification and attribution are stubs until label mapping lands in M2
    classification = "uncertain"
    attribution = "uncertain"

    update_content_status(content_id, "classified", classification, confidence)
    insert_audit_log(
        event="classification",
        content_id=content_id,
        timestamp=timestamp,
        classification=classification,
        attribution=attribution,
        confidence=confidence,
        heuristic_score=heuristic_score,
        llm_score=llm_score,
        status="classified",
    )

    return jsonify({
        "content_id": content_id,
        "classification": "uncertain",
        "attribution": "uncertain",
        "confidence": confidence,
        "label": {
            "variant": "uncertain",
            "text": "Label mapping not yet implemented — wired in M2."
        },
        "signals": {
            "heuristic": {
                "score": heuristic_score,
                "features": heuristic_result["features"]
            },
            "llm": {
                "score": llm_score,
                "reasoning": llm_result["reasoning"]
            }
        },
        "timestamp": timestamp
    })


if __name__ == "__main__":
    app.run(debug=True)
