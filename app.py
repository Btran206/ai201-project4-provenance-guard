from flask import Flask, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv
import uuid
from datetime import datetime, timezone

from signals.heuristic import analyze as heuristic_analyze
from signals.llm_signal import analyze as llm_analyze
import pipeline
import store
from store import (
    get_log, insert_audit_log, update_content_status,
    get_content, get_appeal_by_content_id, insert_appeal,
    update_content_appeal_status,
)

load_dotenv()

app = Flask(__name__)

limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=[],
)
store.init_db()


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/log")
def log():
    return jsonify({"entries": get_log()})


@app.route("/submit", methods=["POST"])
@limiter.limit("10 per minute; 100 per hour")
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
    llm_result = llm_analyze(content)

    heuristic_score = heuristic_result["score"]
    llm_score = llm_result["score"]
    confidence = pipeline.fuse(heuristic_score, llm_score)

    result = pipeline.classify(confidence)
    classification = result["classification"]
    label = result["label"]
    attribution = label["variant"]

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
        "classification": classification,
        "confidence": confidence,
        "label": label,
        "signals": {
            "heuristic": {
                "score": heuristic_score,
                "signal_confidence": heuristic_result["signal_confidence"],
                "features": heuristic_result["features"]
            },
            "llm": {
                "score": llm_score,
                "reasoning": llm_result["reasoning"]
            }
        },
        "timestamp": timestamp
    })


@app.route("/appeal", methods=["POST"])
def appeal():
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"error": "JSON body required"}), 400

    content_id = body.get("content_id", "").strip()
    creator_id = body.get("creator_id")
    reason = body.get("reason", "").strip()

    if not content_id:
        return jsonify({"error": "content_id is required"}), 400
    if not reason:
        return jsonify({"error": "reason is required"}), 400

    record = get_content(content_id)
    if not record:
        return jsonify({"error": "content_id not found"}), 404

    existing = get_appeal_by_content_id(content_id)
    if existing:
        return jsonify({"error": "An appeal for this content is already under review"}), 409

    appeal_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    insert_appeal(appeal_id, content_id, creator_id, reason, timestamp)
    update_content_appeal_status(content_id, "under_review")
    insert_audit_log(
        event="appeal",
        content_id=content_id,
        timestamp=timestamp,
        classification=record.get("classification"),
        attribution=None,
        confidence=record.get("confidence"),
        heuristic_score=None,
        llm_score=None,
        status="under_review",
        appeal_id=appeal_id,
        appeal_reason=reason,
    )

    return jsonify({
        "appeal_id": appeal_id,
        "status": "under_review",
        "message": "Your appeal has been logged.",
    })


if __name__ == "__main__":
    app.run(debug=True)
