import hashlib
import json
import logging
import math
import re
from dataclasses import dataclass
from typing import Any, Protocol

from app.services.foundry_client import (
    FoundryClient,
    FoundryConfigurationError,
    FoundryServiceError,
    get_foundry_client,
)

logger = logging.getLogger(__name__)

DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_EMBEDDING_DIMENSIONS = 1536


def generate_semantic_feature_vector(
    text: str,
    dim: int = DEFAULT_EMBEDDING_DIMENSIONS,
) -> list[float]:
    """Generate a deterministic, multi-signal normalized semantic vector embedding.

    Extracts word unigrams, stems, subword character n-grams, and bigrams projected
    into a unit-normalized vector of dimension `dim` (default: 1536).
    """
    if not text or not text.strip():
        return [0.0] * dim

    clean_text = text.lower().strip()
    words = [w for w in re.findall(r"[a-z0-9]+", clean_text) if len(w) > 1]
    if not words:
        return [0.0] * dim

    vec = [0.0] * dim
    stopwords = {
        "the", "a", "an", "and", "or", "in", "on", "at", "with", "for",
        "of", "to", "is", "it", "this", "that", "was", "my", "your",
    }

    for w in words:
        weight = 0.5 if w in stopwords else 2.5
        h = int(hashlib.sha256(f"w:{w}".encode("utf-8")).hexdigest(), 16)
        vec[h % dim] += weight

        stem = w.rstrip("s") if len(w) > 3 else w
        h_stem = int(hashlib.sha256(f"s:{stem}".encode("utf-8")).hexdigest(), 16)
        vec[h_stem % dim] += weight * 0.8

        if len(w) >= 3 and w not in stopwords:
            for n in (3, 4):
                if len(w) >= n:
                    for i in range(len(w) - n + 1):
                        ngram = w[i : i + n]
                        h_ng = int(hashlib.sha256(f"ng:{ngram}".encode("utf-8")).hexdigest(), 16)
                        vec[h_ng % dim] += 0.8

    for i in range(len(words) - 1):
        if words[i] not in stopwords or words[i + 1] not in stopwords:
            bg = f"{words[i]}_{words[i+1]}"
            h_bg = int(hashlib.sha256(f"bg:{bg}".encode("utf-8")).hexdigest(), 16)
            vec[h_bg % dim] += 2.0

    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0:
        return [float(x / norm) for x in vec]
    return [0.0] * dim


class EmbeddingError(RuntimeError):
    """Base exception for embedding service failures."""


class EmbeddingUnavailable(EmbeddingError):
    """Raised when the backend embedding service is not configured or offline."""


class EmbeddingFailed(EmbeddingError):
    """Raised when embedding generation fails due to provider error or timeout."""


@dataclass(frozen=True)
class EmbeddingResult:
    vector: list[float]
    model: str
    dimensions: int
    input_type: str  # "text" or "image"
    status: str      # "SUCCESS", "UNAVAILABLE", or "FAILED"


def serialize_embedding(vector: list[float] | None) -> str | None:
    """Serialize a list of float values to a JSON string for SQLite storage."""
    if vector is None:
        return None
    if not isinstance(vector, list):
        raise ValueError("Vector must be a list of float values.")
    return json.dumps([float(x) for x in vector])


def deserialize_embedding(blob: str | None) -> list[float] | None:
    """Deserialize a JSON string back into a list of float values."""
    if not blob or not blob.strip():
        return None
    try:
        data = json.loads(blob.strip())
        if isinstance(data, list) and all(isinstance(x, (int, float)) for x in data):
            return [float(x) for x in data]
        return None
    except (json.JSONDecodeError, ValueError, TypeError):
        logger.warning("Failed to deserialize embedding JSON blob.")
        return None


def cosine_similarity(a: list[float] | None, b: list[float] | None) -> float:
    """Calculate the cosine similarity between two float vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0

    dot_product = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    similarity = dot_product / (norm_a * norm_b)
    return float(max(-1.0, min(1.0, similarity)))


class EmbeddingProvider(Protocol):
    def embed_text(self, text: str) -> EmbeddingResult:
        ...

    def embed_image(
        self,
        image_bytes: bytes,
        mime_type: str = "image/jpeg",
        fallback_text: str | None = None,
    ) -> EmbeddingResult:
        ...


class FoundryEmbeddingProvider:
    def __init__(self, client: FoundryClient | None = None) -> None:
        self.client = client or get_foundry_client()

    def embed_text(self, text: str) -> EmbeddingResult:
        if not text or not text.strip():
            raise ValueError("Input text for embedding cannot be empty.")

        try:
            vector = self.client.generate_embedding(text)
            return EmbeddingResult(
                vector=vector,
                model=self.client.config.embedding_model_name,
                dimensions=len(vector),
                input_type="text",
                status="SUCCESS",
            )
        except FoundryServiceError as exc:
            logger.error("Text embedding generation failed: %s", exc)
            raise EmbeddingFailed("Failed to generate text embedding from Microsoft Foundry.") from exc

    def embed_image(
        self,
        image_bytes: bytes,
        mime_type: str = "image/jpeg",
        fallback_text: str | None = None,
    ) -> EmbeddingResult:
        if not image_bytes and not fallback_text:
            raise ValueError("Image bytes or fallback description text must be provided.")

        description_text = ""
        if image_bytes:
            try:
                vision_result = self.client.analyze_image(image_bytes, mime_type=mime_type)
                description_text = vision_result.description
                # Combine description with key visual attributes for rich embedding representation
                attrs = vision_result.attributes
                components = [description_text]
                if attrs.get("object_type"):
                    components.append(f"Type: {attrs['object_type']}")
                if attrs.get("category"):
                    components.append(f"Category: {attrs['category']}")
                if attrs.get("primary_color"):
                    components.append(f"Color: {attrs['primary_color']}")
                if attrs.get("brand"):
                    components.append(f"Brand: {attrs['brand']}")
                if attrs.get("visible_text"):
                    components.append(f"Text: {', '.join(attrs['visible_text'])}")
                description_text = ". ".join(components)
            except Exception as exc:
                logger.warning("Vision analysis before image embedding failed: %s", exc)
                if not fallback_text:
                    raise EmbeddingFailed("Image vision analysis failed and no fallback text provided.") from exc
                description_text = fallback_text
        elif fallback_text:
            description_text = fallback_text

        text_result = self.embed_text(description_text)
        return EmbeddingResult(
            vector=text_result.vector,
            model=text_result.model,
            dimensions=text_result.dimensions,
            input_type="image",
            status="SUCCESS",
        )


class UnavailableEmbeddingProvider:
    def embed_text(self, text: str) -> EmbeddingResult:
        raise EmbeddingUnavailable("Microsoft Foundry embedding service is not configured.")

    def embed_image(
        self,
        image_bytes: bytes,
        mime_type: str = "image/jpeg",
        fallback_text: str | None = None,
    ) -> EmbeddingResult:
        raise EmbeddingUnavailable("Microsoft Foundry embedding service is not configured.")


def get_embedding_provider() -> EmbeddingProvider:
    try:
        client = get_foundry_client()
        return FoundryEmbeddingProvider(client=client)
    except FoundryConfigurationError:
        logger.warning("Foundry embedding provider unavailable due to missing config.")
        return UnavailableEmbeddingProvider()
