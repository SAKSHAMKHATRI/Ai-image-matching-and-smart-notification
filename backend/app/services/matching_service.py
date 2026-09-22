import json
import logging
from dataclasses import asdict
from typing import Any

from app.database import repositories
from app.services.candidate_service import CandidateFilter, retrieve_candidates
from app.services.scoring_service import (
    DISCLAIMER_TEXT,
    MatchClassification,
    compute_match_score,
)

logger = logging.getLogger(__name__)


def _notify_owner_of_possible_match(
    lost_item: dict[str, Any],
    found_item: dict[str, Any],
    score_result: Any,
) -> None:
    try:
        from app.services.notification_service import notify_possible_match

        notify_possible_match(lost_item, found_item, score_result)
    except Exception as exc:
        logger.warning(
            "Failed to notify owner of possible match: %s",
            exc,
        )


def evaluate_and_persist_matches_for_found_item(
    found_item: dict[str, Any],
    filters: CandidateFilter | None = None,
) -> dict[str, Any]:
    """Retrieve candidates, compute deterministic scores, persist matches,

    and format safe output for the UI.
    """
    if filters is None:
        filters = CandidateFilter()

    found_item_id = found_item["id"]
    candidate_result = retrieve_candidates(found_item_id, filters)
    candidates = candidate_result.get("candidates", [])

    scored_matches: list[dict[str, Any]] = []
    strong_count = 0
    possible_count = 0
    low_count = 0

    for candidate in candidates:
        lost_id = candidate["id"]
        # Fetch full lost item record to access embedding blobs for scoring
        lost_item_full = repositories.get_lost_item(lost_id)
        if not lost_item_full:
            continue

        score_result = compute_match_score(found_item, lost_item_full)
        explanation_json = score_result.to_explanation_json()

        # Persist / upsert into matches table
        match_id = repositories.upsert_match(
            found_item_id=found_item_id,
            lost_item_id=lost_id,
            score=score_result.score,
            explanation_json=explanation_json,
            status="SUGGESTED",
        )

        # Notify lost item owner of possible match
        _notify_owner_of_possible_match(lost_item_full, found_item, score_result)

        if score_result.classification == MatchClassification.STRONG_CANDIDATE:
            strong_count += 1
        elif score_result.classification == MatchClassification.POSSIBLE_CANDIDATE:
            possible_count += 1
        else:
            low_count += 1

        scored_item = {
            "id": lost_id,
            "lost_item_id": lost_id,
            "match_id": match_id,
            "status": candidate.get("status", "ACTIVE"),
            "item_name": candidate.get("item_name", ""),
            "category": candidate.get("category"),
            "color": candidate.get("color"),
            "brand": candidate.get("brand"),
            "campus": candidate.get("campus"),
            "lost_date": candidate.get("lost_date"),
            "approximate_location": candidate.get("approximate_location"),
            "description": candidate.get("description"),
            "distinctive_features": candidate.get("distinctive_features"),
            "image_reference": candidate.get("image_reference"),
            "score": score_result.score,
            "score_percent": int(round(score_result.score * 100)),
            "classification": score_result.classification.value,
            "classification_label": score_result.classification_label,
            "reasons": score_result.reasons,
            "components": {
                name: asdict(comp) for name, comp in score_result.components.items()
            },
            "created_at": candidate.get("created_at", ""),
        }
        scored_matches.append(scored_item)

    scored_matches.sort(key=lambda m: m["score"], reverse=True)

    return {
        "found_item_id": found_item_id,
        "matches": scored_matches,
        "total_matches": len(scored_matches),
        "strong_matches_count": strong_count,
        "possible_matches_count": possible_count,
        "low_confidence_count": low_count,
        "disclaimer": DISCLAIMER_TEXT,
    }


def evaluate_and_persist_matches_for_lost_item(
    lost_item: dict[str, Any],
) -> None:
    """Evaluate active found items against a lost item and persist match results."""
    lost_item_id = lost_item["id"]
    found_items, _ = repositories.search_public_found_items(limit=100)

    for found_item_summary in found_items:
        found_item_full = repositories.get_found_item(found_item_summary["id"])
        if not found_item_full:
            continue

        score_result = compute_match_score(found_item_full, lost_item)
        explanation_json = score_result.to_explanation_json()

        repositories.upsert_match(
            found_item_id=found_item_summary["id"],
            lost_item_id=lost_item_id,
            score=score_result.score,
            explanation_json=explanation_json,
            status="SUGGESTED",
        )

        _notify_owner_of_possible_match(lost_item, found_item_full, score_result)


def get_lost_item_matches_response(
    lost_item: dict[str, Any],
    refresh: bool = False,
) -> dict[str, Any]:
    """Retrieve persisted and scored match results for a lost item owner."""
    lost_item_id = lost_item["id"]

    # 1. If refresh requested or no matches in DB, evaluate against active found items
    matches_db = repositories.get_matches_for_lost_item(lost_item_id)
    if refresh or not matches_db:
        evaluate_and_persist_matches_for_lost_item(lost_item)
        matches_db = repositories.get_matches_for_lost_item(lost_item_id)

    scored_matches: list[dict[str, Any]] = []
    strong_count = 0
    possible_count = 0
    low_count = 0

    for match in matches_db:
        found_item = repositories.get_found_item(match["found_item_id"])
        if not found_item:
            continue

        explanation: dict[str, Any] = {}
        if match.get("explanation_json"):
            try:
                explanation = json.loads(match["explanation_json"])
            except Exception:
                explanation = {}

        score = float(match.get("score") or 0.0)
        raw_classification = str(explanation.get("classification", "LOW_CONFIDENCE")).upper()
        if raw_classification == "STRONG_CANDIDATE":
            classification = "STRONG_CANDIDATE"
            strong_count += 1
        elif raw_classification == "POSSIBLE_CANDIDATE":
            classification = "POSSIBLE_CANDIDATE"
            possible_count += 1
        else:
            classification = "LOW_CONFIDENCE"
            low_count += 1

        scored_item = {
            "id": found_item["id"],
            "found_item_id": found_item["id"],
            "lost_item_id": lost_item_id,
            "match_id": match["id"],
            "status": found_item.get("status", "REPORTED"),
            "item_name": found_item.get("item_name") or found_item.get("category") or "Found Item",
            "category": found_item.get("category"),
            "color": found_item.get("color"),
            "brand": found_item.get("brand"),
            "campus": found_item.get("campus"),
            "found_date": found_item.get("found_at"),
            "lost_date": found_item.get("found_at"),
            "found_location": found_item.get("location"),
            "approximate_location": found_item.get("location"),
            "description": found_item.get("description"),
            "distinctive_features": found_item.get("distinctive_features"),
            "image_reference": found_item.get("image_reference"),
            "score": score,
            "score_percent": int(round(score * 100)),
            "classification": classification,
            "classification_label": explanation.get(
                "classification_label",
                "Strong candidate" if classification == "STRONG_CANDIDATE"
                else "Possible candidate" if classification == "POSSIBLE_CANDIDATE"
                else "Low confidence",
            ),
            "reasons": explanation.get("reasons", []),
            "components": explanation.get("components", {}),
            "created_at": match.get("created_at", ""),
        }
        scored_matches.append(scored_item)

    scored_matches.sort(key=lambda m: m["score"], reverse=True)

    return {
        "lost_item_id": lost_item_id,
        "matches": scored_matches,
        "total_matches": len(scored_matches),
        "strong_matches_count": strong_count,
        "possible_matches_count": possible_count,
        "low_confidence_count": low_count,
        "disclaimer": DISCLAIMER_TEXT,
    }
