import logging
from dataclasses import dataclass
from typing import Any, Protocol

from app.services.foundry_client import (
    FoundryClient,
    FoundryConfigurationError,
    FoundryServiceError,
    get_foundry_client,
)
from app.services.ocr_service import (
    FoundryOCRProvider,
    OCRProvider,
    UnavailableOCRProvider,
)
from app.services.storage_service import get_image_bytes

logger = logging.getLogger(__name__)


class AnalysisUnavailable(Exception):
    """Raised when no Phase 7/8 AI provider is configured."""


class AnalysisFailed(Exception):
    """Raised when AI analysis request fails or times out."""


@dataclass(frozen=True)
class AnalysisRequest:
    image_reference: str | None = None
    image_bytes: bytes | None = None
    content_type: str = "image/jpeg"


@dataclass(frozen=True)
class AnalysisResult:
    description: str
    attributes: dict[str, Any]
    embedding_reference: str | None = None


class ImageAnalysisProvider(Protocol):
    def analyze(self, request: AnalysisRequest) -> AnalysisResult:
        ...

    def analyze_bytes(self, image_bytes: bytes, content_type: str = "image/jpeg") -> AnalysisResult:
        ...


class FoundryImageAnalysisProvider:
    def __init__(
        self,
        client: FoundryClient | None = None,
        ocr_provider: OCRProvider | None = None,
    ) -> None:
        self.client = client or get_foundry_client()
        self.ocr_provider = ocr_provider or FoundryOCRProvider(self.client)

    def analyze_bytes(self, image_bytes: bytes, content_type: str = "image/jpeg") -> AnalysisResult:
        try:
            vision_result = self.client.analyze_image(image_bytes, mime_type=content_type)
            attributes = dict(vision_result.attributes)

            # Extract structured OCR evidence if OCR provider is available
            ocr_result_dict: dict[str, Any]
            try:
                ocr_result = self.ocr_provider.extract_ocr_bytes(image_bytes, content_type=content_type)
                ocr_result_dict = ocr_result.to_dict()

                # Merge sanitized OCR text into visible_text if OCR found details
                if ocr_result.sanitized_text and not attributes.get("visible_text"):
                    attributes["visible_text"] = ocr_result.text_blocks or [ocr_result.sanitized_text]
            except Exception as ocr_exc:
                logger.info("OCR extraction during image analysis omitted or failed: %s", ocr_exc)
                ocr_result_dict = {
                    "extracted_text": "",
                    "sanitized_text": "",
                    "text_blocks": [],
                    "detected_text_present": False,
                    "confidence": None,
                    "language": None,
                    "has_sensitive_pii": False,
                    "provider": "unavailable",
                    "status": "UNAVAILABLE",
                }

            attributes["ocr"] = ocr_result_dict

            return AnalysisResult(
                description=vision_result.description,
                attributes=attributes,
            )
        except FoundryConfigurationError as exc:
            raise AnalysisUnavailable("AI analysis is not configured.") from exc
        except FoundryServiceError as exc:
            raise AnalysisFailed("AI analysis request failed.") from exc

    def analyze(self, request: AnalysisRequest) -> AnalysisResult:
        if request.image_bytes is not None:
            return self.analyze_bytes(request.image_bytes, request.content_type)

        if not request.image_reference:
            raise ValueError("AnalysisRequest requires either image_bytes or image_reference.")

        try:
            image_bytes, content_type = get_image_bytes(request.image_reference)
        except Exception as exc:
            logger.warning("Could not download image for analysis: %s", exc)
            raise AnalysisFailed("Could not read image from storage.") from exc

        return self.analyze_bytes(image_bytes, content_type)


class UnavailableImageAnalysisProvider:
    def analyze(self, request: AnalysisRequest) -> AnalysisResult:
        raise AnalysisUnavailable("AI analysis provider is not configured yet.")

    def analyze_bytes(self, image_bytes: bytes, content_type: str = "image/jpeg") -> AnalysisResult:
        raise AnalysisUnavailable("AI analysis provider is not configured yet.")


def get_analysis_provider() -> ImageAnalysisProvider:
    try:
        return FoundryImageAnalysisProvider()
    except (FoundryConfigurationError, Exception) as exc:
        logger.info("Foundry client not available, using fallback provider: %s", exc)
        return UnavailableImageAnalysisProvider()
