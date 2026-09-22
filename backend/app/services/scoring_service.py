"""Phase 11 — Match Scoring and Thresholds Service.

Computes match confidence from image similarity, attribute similarity,
location, and date compatibility.

Threshold categories:
- Strong candidate: >= 0.85
- Possible candidate: 0.70 – 0.85
- Low confidence: < 0.70

All scores are deterministic, explainable by explicit components, and
never treated as proof of ownership.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any

from app.services.embedding_service import (
    cosine_similarity,
    deserialize_embedding,
)

logger = logging.getLogger(__name__)

# Default threshold constants
DEFAULT_STRONG_THRESHOLD: float = 0.85
DEFAULT_POSSIBLE_THRESHOLD: float = 0.70

# Default ownership disclaimer
DISCLAIMER_TEXT: str = (
    "Match confidence is for ranking and candidate review only "
    "and does not establish proof of ownership."
)


class MatchClassification(str, Enum):
    """Categorical classification of candidate matches based on confidence."""

    STRONG_CANDIDATE = "STRONG_CANDIDATE"
    POSSIBLE_CANDIDATE = "POSSIBLE_CANDIDATE"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"


@dataclass(frozen=True)
class ScoringWeights:
    """Configurable weights for match scoring components."""

    # Weights when a lost-item image is present (sum = 1.0)
    image_text_with_image: float = 0.45
    lost_image_with_image: float = 0.20
    attributes_with_image: float = 0.15
    location_with_image: float = 0.10
    date_with_image: float = 0.10

    # Weights when no lost-item image is present (sum = 1.0)
    image_text_without_image: float = 0.55
    attributes_without_image: float = 0.20
    location_without_image: float = 0.15
    date_without_image: float = 0.10


@dataclass(frozen=True)
class ScoringThresholds:
    """Configurable score thresholds for classifying match confidence."""

    strong_threshold: float = DEFAULT_STRONG_THRESHOLD
    possible_threshold: float = DEFAULT_POSSIBLE_THRESHOLD

    def __post_init__(self) -> None:
        if not (0.0 <= self.possible_threshold <= self.strong_threshold <= 1.0):
            raise ValueError(
                "Thresholds must satisfy 0.0 <= possible_threshold <= strong_threshold <= 1.0"
            )


@dataclass
class ComponentScore:
    """Breakdown of an individual score component."""

    score: float
    weight: float
    contribution: float


@dataclass
class MatchScoreResult:
    """Complete, explainable scoring result for a found/lost item pair."""

    found_item_id: int
    lost_item_id: int
    score: float
    classification: MatchClassification
    classification_label: str
    has_lost_image: bool
    components: dict[str, ComponentScore] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
    disclaimer: str = DISCLAIMER_TEXT

    def to_dict(self) -> dict[str, Any]:
        return {
            "found_item_id": self.found_item_id,
            "lost_item_id": self.lost_item_id,
            "score": self.score,
            "classification": self.classification.value,
            "classification_label": self.classification_label,
            "has_lost_image": self.has_lost_image,
            "components": {
                name: asdict(comp) for name, comp in self.components.items()
            },
            "reasons": self.reasons,
            "disclaimer": self.disclaimer,
        }

    def to_explanation_json(self) -> str:
        """Serialize scoring explanation to JSON for database storage."""
        return json.dumps(
            {
                "score": self.score,
                "classification": self.classification.value,
                "classification_label": self.classification_label,
                "reasons": self.reasons,
                "components": {
                    k: {
                        "score": round(v.score, 4),
                        "weight": round(v.weight, 4),
                        "contribution": round(v.contribution, 4),
                    }
                    for k, v in self.components.items()
                },
                "disclaimer": self.disclaimer,
            }
        )


def _resolve_vector(value: Any) -> list[float] | None:
    """Helper to deserialize string embedding blobs or accept list of floats."""
    if value is None:
        return None
    if isinstance(value, str):
        return deserialize_embedding(value)
    if isinstance(value, list) and all(isinstance(x, (int, float)) for x in value):
        return [float(x) for x in value]
    return None


def compute_image_text_similarity(
    found_image_embedding: Any,
    lost_description_embedding: Any,
) -> float:
    """Calculate cosine similarity between found image vector and lost text vector.

    Clamped between 0.0 and 1.0.
    """
    vec_found = _resolve_vector(found_image_embedding)
    vec_lost = _resolve_vector(lost_description_embedding)
    if not vec_found or not vec_lost:
        return 0.0
    sim = cosine_similarity(vec_found, vec_lost)
    return float(max(0.0, min(1.0, sim)))


def compute_image_image_similarity(
    found_image_embedding: Any,
    lost_image_embedding: Any,
) -> float:
    """Calculate cosine similarity between found image vector and lost image vector.

    Clamped between 0.0 and 1.0.
    """
    vec_found = _resolve_vector(found_image_embedding)
    vec_lost = _resolve_vector(lost_image_embedding)
    if not vec_found or not vec_lost:
        return 0.0
    sim = cosine_similarity(vec_found, vec_lost)
    return float(max(0.0, min(1.0, sim)))


def _normalize_str(val: Any) -> str:
    """Helper to trim and lowercase a string."""
    if val is None:
        return ""
    return str(val).strip().lower()


def _extract_category_tokens(cat_str: str) -> set[str]:
    """Extract normalized category keywords/tokens for flexible matching."""
    if not cat_str:
        return set()
    words = re.findall(r"[A-Za-z0-9]+", cat_str.lower())
    stop_words = {"and", "or", "in", "of", "the", "a", "an", "item", "items"}
    tokens = set()
    for w in words:
        if w not in stop_words and len(w) > 2:
            tokens.add(w)
            tokens.add(w.rstrip("s"))
    return tokens


def compute_attribute_similarity(
    found_item: dict[str, Any],
    lost_item: dict[str, Any],
) -> tuple[float, list[str]]:
    """Compare item attributes (category, color, brand, distinctive features).

    Returns a score in [0.0, 1.0] and a list of human-readable explanation reasons.
    """
    reasons: list[str] = []
    scores: list[float] = []
    weights: list[float] = []

    # 1. Category comparison (weight = 0.40)
    found_cat = _normalize_str(found_item.get("category"))
    lost_cat = _normalize_str(lost_item.get("category"))
    if found_cat and lost_cat:
        found_tokens = _extract_category_tokens(found_cat)
        lost_tokens = _extract_category_tokens(lost_cat)
        if (
            found_cat == lost_cat
            or found_cat in lost_cat
            or lost_cat in found_cat
            or (len(found_cat) > 3 and len(lost_cat) > 3 and found_cat.rstrip("s") == lost_cat.rstrip("s"))
            or (found_tokens and lost_tokens and bool(found_tokens & lost_tokens))
        ):
            scores.append(1.0)
            weights.append(0.40)
            reasons.append(f"Same category: {found_item.get('category') or lost_item.get('category')}")
        else:
            scores.append(0.0)
            weights.append(0.40)
    elif found_cat or lost_cat:
        scores.append(0.5)
        weights.append(0.20)

    # 2. Brand comparison (weight = 0.30)
    found_brand = _normalize_str(found_item.get("brand"))
    lost_brand = _normalize_str(lost_item.get("brand"))
    if found_brand and lost_brand:
        if found_brand == lost_brand or found_brand in lost_brand or lost_brand in found_brand:
            scores.append(1.0)
            weights.append(0.30)
            reasons.append(f"Brand appears consistent: {found_item.get('brand') or lost_item.get('brand')}")
        elif found_brand in ("other", "unknown", "unbranded") or lost_brand in ("other", "unknown", "unbranded"):
            scores.append(0.5)
            weights.append(0.15)
        else:
            scores.append(0.0)
            weights.append(0.30)
    elif found_brand or lost_brand:
        scores.append(0.5)
        weights.append(0.15)

    # 3. Color comparison (weight = 0.30)
    found_color = _normalize_str(found_item.get("color"))
    lost_color = _normalize_str(lost_item.get("color"))
    if found_color and lost_color:
        if found_color == lost_color or found_color in lost_color or lost_color in found_color:
            scores.append(1.0)
            weights.append(0.30)
            reasons.append(f"Matching color: {found_item.get('color') or lost_item.get('color')}")
        elif found_color in ("other", "unknown", "multi-color / pattern", "multi-color") or lost_color in ("other", "unknown", "multi-color / pattern", "multi-color"):
            scores.append(0.5)
            weights.append(0.15)
        else:
            scores.append(0.0)
            weights.append(0.30)
    elif found_color or lost_color:
        scores.append(0.5)
        weights.append(0.15)

    # 4. Distinctive features / keywords check
    found_feat = _normalize_str(found_item.get("distinctive_features"))
    lost_feat = _normalize_str(lost_item.get("distinctive_features"))
    if found_feat and lost_feat:
        words_found = set(re.findall(r"\w+", found_feat))
        words_lost = set(re.findall(r"\w+", lost_feat))
        common = words_found.intersection(words_lost)
        # Filter out short stopwords
        common = {w for w in common if len(w) > 3}
        if common:
            reasons.append(f"Similar distinctive features: {', '.join(sorted(common)[:3])}")

    if not weights:
        return 0.5, reasons

    total_weight = sum(weights)
    weighted_score = sum(s * w for s, w in zip(scores, weights)) / total_weight
    return float(max(0.0, min(1.0, weighted_score))), reasons


def compute_location_compatibility(
    found_campus: str | None,
    found_location: str | None,
    lost_campus: str | None,
    lost_location: str | None,
) -> tuple[float, list[str]]:
    """Evaluate location compatibility based on campus and location strings.

    Returns a score in [0.0, 1.0] and explanation reasons.
    """
    reasons: list[str] = []
    fc = _normalize_str(found_campus)
    lc = _normalize_str(lost_campus)
    fl = _normalize_str(found_location)
    ll = _normalize_str(lost_location)

    # If campuses are provided and conflict -> 0.0
    if fc and lc and fc != lc:
        return 0.0, reasons

    # Campuses match or at least one is unspecified
    score = 0.5
    if fc and lc and fc == lc:
        score = 0.8
        reasons.append(f"Compatible campus: {found_campus}")

        # Check for specific location overlap
        if fl and ll:
            words_found = {w for w in re.findall(r"\w+", fl) if len(w) > 3}
            words_lost = {w for w in re.findall(r"\w+", ll) if len(w) > 3}
            if words_found and words_lost and (words_found & words_lost):
                score = 1.0
                reasons.append(f"Compatible specific location: {found_location}")
            elif fl == ll:
                score = 1.0
                reasons.append(f"Compatible specific location: {found_location}")
    elif fc or lc:
        score = 0.6
        if fc:
            reasons.append(f"Located near {found_campus}")

    return float(max(0.0, min(1.0, score))), reasons


def _parse_date(value: Any) -> date | None:
    """Safely parse a date or datetime object/string."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        val = value.strip()
        if not val:
            return None
        # Try ISO format or standard YYYY-MM-DD
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(val.split("T")[0] if "T" in val else val, "%Y-%m-%d").date()
            except ValueError:
                continue
    return None


def compute_date_compatibility(
    found_date: Any,
    lost_date: Any,
) -> tuple[float, list[str]]:
    """Evaluate temporal compatibility between lost date and found date.

    Items are expected to be found on or shortly after being lost.
    Returns a score in [0.0, 1.0] and explanation reasons.
    """
    reasons: list[str] = []
    fd = _parse_date(found_date)
    ld = _parse_date(lost_date)

    if not fd or not ld:
        return 0.5, reasons

    days_diff = (fd - ld).days

    if days_diff < -7:
        # Found significantly before it was reportedly lost (anomalous)
        return 0.0, ["Found date precedes reported lost date"]
    elif days_diff < 0:
        # Margin for timezone/approximate reporting boundary
        return 0.70, ["Found date corresponds closely to reported lost date"]
    elif days_diff <= 3:
        score = 1.00
        reasons.append(f"Found {days_diff} day(s) after reported lost date")
    elif days_diff <= 7:
        score = 0.90
        reasons.append(f"Found {days_diff} days after reported lost date")
    elif days_diff <= 14:
        score = 0.80
        reasons.append("Found within 2 weeks of reported lost date")
    elif days_diff <= 30:
        score = 0.65
        reasons.append("Found within 1 month of reported lost date")
    elif days_diff <= 60:
        score = 0.50
    elif days_diff <= 90:
        score = 0.35
    else:
        score = 0.20

    return float(max(0.0, min(1.0, score))), reasons


def classify_score(
    score: float,
    thresholds: ScoringThresholds | None = None,
) -> tuple[MatchClassification, str]:
    """Classify a match score into standard categories."""
    thresh = thresholds or ScoringThresholds()
    if score >= thresh.strong_threshold:
        return MatchClassification.STRONG_CANDIDATE, "Strong candidate"
    if score >= thresh.possible_threshold:
        return MatchClassification.POSSIBLE_CANDIDATE, "Possible candidate"
    return MatchClassification.LOW_CONFIDENCE, "Low confidence"


def compute_match_score(
    found_item: dict[str, Any],
    lost_item: dict[str, Any],
    weights: ScoringWeights | None = None,
    thresholds: ScoringThresholds | None = None,
) -> MatchScoreResult:
    """Compute the deterministic match score and explanation for an item pair.

    Supports both cases:
    - Lost item has an image: 5-component weighted formula
    - Lost item lacks an image: 4-component weighted formula

    Never treats the score as proof of ownership.
    """
    w = weights or ScoringWeights()
    t = thresholds or ScoringThresholds()

    found_id = int(found_item.get("id", 0))
    lost_id = int(lost_item.get("id", 0))

    # Determine if lost image embedding exists
    lost_img_emb = lost_item.get("image_embedding_blob")
    has_lost_image = bool(lost_img_emb and str(lost_img_emb).strip())

    found_img_emb = found_item.get("image_embedding_blob")
    lost_desc_emb = lost_item.get("description_embedding_blob")

    all_reasons: list[str] = []

    # 1. Image / Text Semantic Similarity
    s_image_text = compute_image_text_similarity(found_img_emb, lost_desc_emb)
    if s_image_text >= 0.75:
        all_reasons.append(f"High visual and text semantic similarity ({round(s_image_text, 2)})")
    elif s_image_text >= 0.50:
        all_reasons.append("Moderate visual and text semantic similarity")

    # 2. Lost Image Similarity (if present)
    s_lost_image = 0.0
    if has_lost_image:
        s_lost_image = compute_image_image_similarity(found_img_emb, lost_img_emb)
        if s_lost_image >= 0.75:
            all_reasons.append(f"High image-to-image similarity ({round(s_lost_image, 2)})")

    # 3. Attribute Similarity
    s_attributes, attr_reasons = compute_attribute_similarity(found_item, lost_item)
    all_reasons.extend(attr_reasons)

    # 4. Location Compatibility
    s_location, loc_reasons = compute_location_compatibility(
        found_campus=found_item.get("campus"),
        found_location=found_item.get("location"),
        lost_campus=lost_item.get("campus"),
        lost_location=lost_item.get("location"),
    )
    all_reasons.extend(loc_reasons)

    # 5. Date Compatibility
    found_date = found_item.get("found_at") or found_item.get("found_date")
    lost_date = lost_item.get("lost_at") or lost_item.get("lost_date")
    s_date, date_reasons = compute_date_compatibility(found_date, lost_date)
    all_reasons.extend(date_reasons)

    # Calculate final weighted score
    components: dict[str, ComponentScore] = {}
    if has_lost_image:
        components["image_text"] = ComponentScore(
            score=round(s_image_text, 4),
            weight=w.image_text_with_image,
            contribution=round(s_image_text * w.image_text_with_image, 4),
        )
        components["lost_image"] = ComponentScore(
            score=round(s_lost_image, 4),
            weight=w.lost_image_with_image,
            contribution=round(s_lost_image * w.lost_image_with_image, 4),
        )
        components["attributes"] = ComponentScore(
            score=round(s_attributes, 4),
            weight=w.attributes_with_image,
            contribution=round(s_attributes * w.attributes_with_image, 4),
        )
        components["location"] = ComponentScore(
            score=round(s_location, 4),
            weight=w.location_with_image,
            contribution=round(s_location * w.location_with_image, 4),
        )
        components["date"] = ComponentScore(
            score=round(s_date, 4),
            weight=w.date_with_image,
            contribution=round(s_date * w.date_with_image, 4),
        )
    else:
        components["image_text"] = ComponentScore(
            score=round(s_image_text, 4),
            weight=w.image_text_without_image,
            contribution=round(s_image_text * w.image_text_without_image, 4),
        )
        components["attributes"] = ComponentScore(
            score=round(s_attributes, 4),
            weight=w.attributes_without_image,
            contribution=round(s_attributes * w.attributes_without_image, 4),
        )
        components["location"] = ComponentScore(
            score=round(s_location, 4),
            weight=w.location_without_image,
            contribution=round(s_location * w.location_without_image, 4),
        )
        components["date"] = ComponentScore(
            score=round(s_date, 4),
            weight=w.date_without_image,
            contribution=round(s_date * w.date_without_image, 4),
        )

    final_score = sum(c.contribution for c in components.values())
    final_score = float(max(0.0, min(1.0, round(final_score, 4))))

    classification, classification_label = classify_score(final_score, t)

    return MatchScoreResult(
        found_item_id=found_id,
        lost_item_id=lost_id,
        score=final_score,
        classification=classification,
        classification_label=classification_label,
        has_lost_image=has_lost_image,
        components=components,
        reasons=all_reasons,
        disclaimer=DISCLAIMER_TEXT,
    )


def score_candidates(
    found_item: dict[str, Any],
    candidates: list[dict[str, Any]],
    weights: ScoringWeights | None = None,
    thresholds: ScoringThresholds | None = None,
    min_score: float | None = None,
) -> list[MatchScoreResult]:
    """Score a batch of candidates for a given found item and sort by score desc."""
    results: list[MatchScoreResult] = []
    for candidate in candidates:
        result = compute_match_score(
            found_item=found_item,
            lost_item=candidate,
            weights=weights,
            thresholds=thresholds,
        )
        if min_score is not None and result.score < min_score:
            continue
        results.append(result)

    results.sort(key=lambda r: r.score, reverse=True)
    return results
