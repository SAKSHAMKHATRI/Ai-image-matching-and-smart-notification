from dataclasses import dataclass
from typing import Protocol


class AnalysisUnavailable(Exception):
    """Raised when no Phase 7 AI provider is configured."""


@dataclass(frozen=True)
class AnalysisRequest:
    image_reference: str


@dataclass(frozen=True)
class AnalysisResult:
    attributes: dict[str, object]
    embedding_reference: str | None = None


class ImageAnalysisProvider(Protocol):
    def analyze(self, request: AnalysisRequest) -> AnalysisResult:
        ...


class UnavailableImageAnalysisProvider:
    def analyze(self, request: AnalysisRequest) -> AnalysisResult:
        raise AnalysisUnavailable("AI analysis provider is not configured yet.")


def get_analysis_provider() -> ImageAnalysisProvider:
    return UnavailableImageAnalysisProvider()
