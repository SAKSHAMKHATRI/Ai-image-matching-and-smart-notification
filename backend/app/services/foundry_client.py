import base64
import json
import logging
import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from dotenv import load_dotenv
import httpx

load_dotenv()

logger = logging.getLogger(__name__)

DEFAULT_SYSTEM_PROMPT = (
    "You are an AI assistant analyzing photographs of lost and found items on a university campus. "
    "Analyze the image carefully and extract visible attributes only. "
    "Do NOT invent or assume details that are not visible in the image. "
    "Use null for any attribute that cannot be determined with confidence. "
    "Return a valid JSON object with the following schema:\n"
    "{\n"
    '  "description": string (a concise 1-2 sentence description of the item),\n'
    '  "object_type": string or null (e.g., "water bottle", "backpack", "umbrella", "earbuds", "keys", "student ID", "jacket", "laptop", etc.),\n'
    '  "category": string or null (e.g., "Electronics", "Bags & Backpacks", "Clothing & Accessories", "Documents & Cards", "Keys & Eyewear", "Books & Stationery", "Bottles & Containers", "Personal Items", "Jewelry & Watches", "Sports & Recreation", "Other"),\n'
    '  "primary_color": string or null,\n'
    '  "secondary_colors": list of strings,\n'
    '  "brand": string or null,\n'
    '  "visible_features": list of strings (e.g., stickers, scratches, patterns, logos, straps),\n'
    '  "visible_text": list of strings (any visible text printed or written on the item),\n'
    '  "confidence": float between 0.0 and 1.0\n'
    "}"
)


class FoundryConfigurationError(RuntimeError):
    """Raised when the backend Foundry configuration is missing or invalid."""


class FoundryServiceError(RuntimeError):
    """Raised when the Foundry service cannot complete a request."""


@dataclass(frozen=True)
class FoundryConfig:
    project_endpoint: str
    api_key: str = field(repr=False)
    model_name: str
    timeout_seconds: float
    max_retries: int
    embedding_model_name: str = "text-embedding-3-small"


@lru_cache
def get_foundry_config() -> FoundryConfig:
    endpoint = os.getenv("FOUNDRY_PROJECT_ENDPOINT", "").strip().rstrip("/")
    api_key = os.getenv("FOUNDRY_API_KEY", "").strip()
    model_name = os.getenv("FOUNDRY_MODEL_NAME", "").strip()
    embedding_model_name = os.getenv("FOUNDRY_EMBEDDING_MODEL_NAME", "text-embedding-3-small").strip() or "text-embedding-3-small"

    if not endpoint or not endpoint.startswith("https://"):
        raise FoundryConfigurationError("FOUNDRY_PROJECT_ENDPOINT is not configured.")
    if not api_key or api_key.startswith("replace-with-"):
        raise FoundryConfigurationError("FOUNDRY_API_KEY is not configured.")
    if not model_name or model_name.startswith("replace-with-"):
        raise FoundryConfigurationError("FOUNDRY_MODEL_NAME is not configured.")

    try:
        timeout_seconds = float(os.getenv("FOUNDRY_TIMEOUT_SECONDS", "20"))
        max_retries = int(os.getenv("FOUNDRY_MAX_RETRIES", "2"))
    except ValueError as exc:
        raise FoundryConfigurationError("Foundry timeout/retry settings are invalid.") from exc
    if timeout_seconds <= 0 or max_retries < 0 or max_retries > 5:
        raise FoundryConfigurationError("Foundry timeout/retry settings are out of range.")

    return FoundryConfig(
        project_endpoint=endpoint,
        api_key=api_key,
        model_name=model_name,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        embedding_model_name=embedding_model_name,
    )


@dataclass(frozen=True)
class FoundryResponse:
    output_text: str
    raw: dict[str, Any]


@dataclass(frozen=True)
class FoundryVisionResult:
    description: str
    attributes: dict[str, Any]
    raw: dict[str, Any]


def _normalize_attributes(raw_attrs: dict[str, Any]) -> dict[str, Any]:
    """Ensure attributes conform to expected types and schema."""
    description = raw_attrs.get("description")
    if not isinstance(description, str) or not description.strip():
        description = "Item photo analyzed."

    object_type = raw_attrs.get("object_type")
    if not isinstance(object_type, str) or not object_type.strip():
        object_type = None

    category = raw_attrs.get("category")
    if not isinstance(category, str) or not category.strip():
        category = None

    primary_color = raw_attrs.get("primary_color")
    if not isinstance(primary_color, str) or not primary_color.strip():
        primary_color = None

    secondary_colors = raw_attrs.get("secondary_colors")
    if not isinstance(secondary_colors, list):
        secondary_colors = []
    else:
        secondary_colors = [str(c) for c in secondary_colors if isinstance(c, str) and c.strip()]

    brand = raw_attrs.get("brand")
    if not isinstance(brand, str) or not brand.strip():
        brand = None

    visible_features = raw_attrs.get("visible_features")
    if not isinstance(visible_features, list):
        visible_features = []
    else:
        visible_features = [str(f) for f in visible_features if isinstance(f, str) and f.strip()]

    visible_text = raw_attrs.get("visible_text")
    if not isinstance(visible_text, list):
        visible_text = []
    else:
        visible_text = [str(t) for t in visible_text if isinstance(t, str) and t.strip()]

    confidence = raw_attrs.get("confidence")
    if isinstance(confidence, (int, float)):
        confidence = float(max(0.0, min(1.0, confidence)))
    else:
        confidence = 0.8

    return {
        "description": description.strip(),
        "object_type": object_type,
        "category": category,
        "primary_color": primary_color,
        "secondary_colors": secondary_colors,
        "brand": brand,
        "visible_features": visible_features,
        "visible_text": visible_text,
        "confidence": confidence,
    }


class FoundryClient:
    def __init__(self, config: FoundryConfig | None = None) -> None:
        self.config = config or get_foundry_config()

    @property
    def responses_url(self) -> str:
        base = self.config.project_endpoint.rstrip("/")
        return f"{base}/openai/v1/responses"

    @property
    def chat_completions_url(self) -> str:
        base = self.config.project_endpoint.rstrip("/")
        if "/api/projects" in base:
            base = base.split("/api/projects")[0]
        if base.endswith("/openai/v1"):
            return f"{base}/chat/completions"
        return f"{base}/openai/v1/chat/completions"

    @property
    def embeddings_url(self) -> str:
        base = self.config.project_endpoint.rstrip("/")
        if "/api/projects" in base:
            base = base.split("/api/projects")[0]
        if base.endswith("/openai/v1"):
            return f"{base}/embeddings"
        return f"{base}/openai/v1/embeddings"

    def generate_embedding(self, text: str) -> list[float]:
        """Generate vector embedding using Azure OpenAI / Foundry embedding endpoint."""
        if not text or not text.strip():
            raise ValueError("Embedding input text cannot be empty.")

        payload = {
            "model": self.config.embedding_model_name,
            "input": text.strip(),
        }
        headers = {
            "api-key": self.config.api_key,
            "Content-Type": "application/json",
        }

        last_error: Exception | None = None
        for attempt in range(self.config.max_retries + 1):
            try:
                response = httpx.post(
                    self.embeddings_url,
                    headers=headers,
                    json=payload,
                    timeout=self.config.timeout_seconds,
                )
                if response.status_code in (400, 404):
                    logger.info(
                        "Foundry embedding deployment unavailable (%d); generating semantic feature vector.",
                        response.status_code,
                    )
                    from app.services.embedding_service import generate_semantic_feature_vector
                    return generate_semantic_feature_vector(text.strip())

                response.raise_for_status()
                body = response.json()

                data = body.get("data")
                if isinstance(data, list) and len(data) > 0:
                    embedding = data[0].get("embedding")
                    if isinstance(embedding, list) and all(isinstance(x, (int, float)) for x in embedding):
                        return [float(x) for x in embedding]
                raise FoundryServiceError("Foundry embeddings response missing or malformed vector data.")
            except (httpx.HTTPError, ValueError, FoundryServiceError) as exc:
                last_error = exc
                logger.warning(
                    "Foundry embedding attempt %d/%d failed: %s",
                    attempt + 1,
                    self.config.max_retries + 1,
                    type(exc).__name__,
                )
                if attempt < self.config.max_retries:
                    continue

        raise FoundryServiceError("Microsoft Foundry embedding request failed.") from last_error

    def analyze_text(self, prompt: str) -> FoundryResponse:
        payload = {
            "model": self.config.model_name,
            "input": prompt,
        }
        headers = {
            "api-key": self.config.api_key,
            "Content-Type": "application/json",
        }
        last_error: Exception | None = None
        for attempt in range(self.config.max_retries + 1):
            try:
                response = httpx.post(
                    self.responses_url,
                    headers=headers,
                    json=payload,
                    timeout=self.config.timeout_seconds,
                )
                response.raise_for_status()
                body = response.json()
                output_text = body.get("output_text")
                if not isinstance(output_text, str):
                    raise FoundryServiceError("Foundry returned an invalid response shape.")
                return FoundryResponse(output_text=output_text, raw=body)
            except (httpx.HTTPError, ValueError, FoundryServiceError) as exc:
                last_error = exc
                if attempt < self.config.max_retries:
                    continue
        raise FoundryServiceError("Microsoft Foundry request failed.") from last_error

    def analyze_image(
        self,
        image_bytes: bytes,
        mime_type: str = "image/jpeg",
        prompt: str | None = None,
    ) -> FoundryVisionResult:
        """Call Microsoft Foundry vision model to analyze an image."""
        if not image_bytes:
            raise ValueError("Image bytes cannot be empty.")

        encoded_image = base64.b64encode(image_bytes).decode("utf-8")
        data_uri = f"data:{mime_type};base64,{encoded_image}"

        user_content: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": prompt or "Analyze this lost or found item photo and extract visible attributes.",
            },
            {
                "type": "image_url",
                "image_url": {"url": data_uri},
            },
        ]

        payload = {
            "model": self.config.model_name,
            "messages": [
                {
                    "role": "system",
                    "content": DEFAULT_SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": user_content,
                },
            ],
            "response_format": {"type": "json_object"},
        }
        headers = {
            "api-key": self.config.api_key,
            "Content-Type": "application/json",
        }

        last_error: Exception | None = None
        for attempt in range(self.config.max_retries + 1):
            try:
                response = httpx.post(
                    self.chat_completions_url,
                    headers=headers,
                    json=payload,
                    timeout=self.config.timeout_seconds,
                )
                response.raise_for_status()
                body = response.json()

                choices = body.get("choices")
                if not isinstance(choices, list) or not choices:
                    raise FoundryServiceError("Foundry vision response missing choices.")

                message_content = choices[0].get("message", {}).get("content", "")
                if not isinstance(message_content, str) or not message_content.strip():
                    raise FoundryServiceError("Foundry vision response returned empty content.")

                try:
                    parsed_json = json.loads(message_content)
                except json.JSONDecodeError as exc:
                    raise FoundryServiceError("Foundry vision response is not valid JSON.") from exc

                if not isinstance(parsed_json, dict):
                    raise FoundryServiceError("Foundry vision response JSON is not an object.")

                normalized = _normalize_attributes(parsed_json)
                return FoundryVisionResult(
                    description=normalized["description"],
                    attributes=normalized,
                    raw=body,
                )
            except (httpx.HTTPError, ValueError, FoundryServiceError) as exc:
                last_error = exc
                logger.warning(
                    "Foundry vision attempt %d/%d failed: %s",
                    attempt + 1,
                    self.config.max_retries + 1,
                    type(exc).__name__,
                )
                if attempt < self.config.max_retries:
                    continue

        raise FoundryServiceError("Microsoft Foundry vision request failed.") from last_error


@lru_cache
def get_foundry_client() -> FoundryClient:
    return FoundryClient()
