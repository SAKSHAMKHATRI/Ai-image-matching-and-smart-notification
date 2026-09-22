import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import httpx


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


@lru_cache
def get_foundry_config() -> FoundryConfig:
    endpoint = os.getenv("FOUNDRY_PROJECT_ENDPOINT", "").strip().rstrip("/")
    api_key = os.getenv("FOUNDRY_API_KEY", "").strip()
    model_name = os.getenv("FOUNDRY_MODEL_NAME", "").strip()
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
    )


@dataclass(frozen=True)
class FoundryResponse:
    output_text: str
    raw: dict[str, Any]


class FoundryClient:
    def __init__(self, config: FoundryConfig | None = None) -> None:
        self.config = config or get_foundry_config()

    @property
    def responses_url(self) -> str:
        return f"{self.config.project_endpoint}/openai/v1/responses"

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


@lru_cache
def get_foundry_client() -> FoundryClient:
    return FoundryClient()
