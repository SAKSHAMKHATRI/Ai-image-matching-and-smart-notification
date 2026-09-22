import logging
import re
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.services.foundry_client import (
    FoundryClient,
    FoundryConfigurationError,
    FoundryServiceError,
    get_foundry_client,
)
from app.services.storage_service import get_image_bytes

logger = logging.getLogger(__name__)

# Sensitive PII Regex patterns for university context
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_PATTERN = re.compile(
    r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b|\b\+?\d{10,13}\b"
)
SSN_GOVT_PATTERN = re.compile(
    r"\b\d{3}-\d{2}-\d{4}\b|\b\d{4}[-\s]\d{4}[-\s]\d{4}\b"
)
STUDENT_ID_LABEL_PATTERN = re.compile(
    r"(?i)\b(student\s*id|roll(?:\s*no\.?|\s*number)?|id\s*(?:no\.?|number)?|card(?:\s*no\.?|number)?|reg(?:\s*no\.?|number)?|enrollment(?:\s*no\.?)?)[:\s#]*([A-Za-z0-9-]+)",
)
CAMPUS_ROLL_NUMBER_PATTERN = re.compile(r"\b(?:20\d{2}[A-Za-z0-9]{4,10})\b")


class OCRError(Exception):
    """Base exception for OCR errors."""


class OCRUnavailable(OCRError):
    """Raised when the OCR provider is not configured or unavailable."""


class OCRFailed(OCRError):
    """Raised when an OCR extraction request fails or times out."""


@dataclass(frozen=True)
class OCRRequest:
    image_reference: str | None = None
    image_bytes: bytes | None = None
    content_type: str = "image/jpeg"


@dataclass(frozen=True)
class OCRResult:
    extracted_text: str = ""
    sanitized_text: str = ""
    text_blocks: list[str] = field(default_factory=list)
    detected_text_present: bool = False
    confidence: float | None = None
    language: str | None = None
    has_sensitive_pii: bool = False
    provider: str = "unknown"
    status: str = "SUCCESS"  # SUCCESS | NO_TEXT_DETECTED | UNAVAILABLE | FAILED

    def to_dict(self) -> dict[str, Any]:
        return {
            "extracted_text": self.extracted_text,
            "sanitized_text": self.sanitized_text,
            "text_blocks": self.text_blocks,
            "detected_text_present": self.detected_text_present,
            "confidence": self.confidence,
            "language": self.language,
            "has_sensitive_pii": self.has_sensitive_pii,
            "provider": self.provider,
            "status": self.status,
        }


def sanitize_ocr_text(text: str) -> tuple[str, bool]:
    """Sanitize student IDs, roll numbers, phone numbers, and emails from extracted OCR text."""
    if not text or not text.strip():
        return "", False

    sanitized = text
    had_pii = False

    if EMAIL_PATTERN.search(sanitized):
        sanitized = EMAIL_PATTERN.sub("[REDACTED-EMAIL]", sanitized)
        had_pii = True

    if SSN_GOVT_PATTERN.search(sanitized):
        sanitized = SSN_GOVT_PATTERN.sub("[REDACTED-ID]", sanitized)
        had_pii = True

    if STUDENT_ID_LABEL_PATTERN.search(sanitized):
        sanitized = STUDENT_ID_LABEL_PATTERN.sub(r"\1: [REDACTED-ID]", sanitized)
        had_pii = True

    if CAMPUS_ROLL_NUMBER_PATTERN.search(sanitized):
        sanitized = CAMPUS_ROLL_NUMBER_PATTERN.sub("[REDACTED-ID]", sanitized)
        had_pii = True

    if PHONE_PATTERN.search(sanitized):
        sanitized = PHONE_PATTERN.sub("[REDACTED-PHONE]", sanitized)
        had_pii = True

    return sanitized, had_pii


class OCRProvider(Protocol):
    def extract_ocr(self, request: OCRRequest) -> OCRResult:
        ...

    def extract_ocr_bytes(self, image_bytes: bytes, content_type: str = "image/jpeg") -> OCRResult:
        ...


class FoundryOCRProvider:
    def __init__(self, client: FoundryClient | None = None) -> None:
        self.client = client or get_foundry_client()

    def extract_ocr_bytes(self, image_bytes: bytes, content_type: str = "image/jpeg") -> OCRResult:
        if not image_bytes:
            raise ValueError("Image bytes cannot be empty.")

        try:
            raw_ocr = self.client.extract_ocr(image_bytes, mime_type=content_type)
            extracted_text = str(raw_ocr.get("extracted_text", "") or "").strip()
            raw_blocks = raw_ocr.get("text_blocks")
            if isinstance(raw_blocks, list):
                text_blocks = [str(b).strip() for b in raw_blocks if isinstance(b, str) and b.strip()]
            else:
                text_blocks = [extracted_text] if extracted_text else []

            if not extracted_text and text_blocks:
                extracted_text = "\n".join(text_blocks)

            detected = bool(raw_ocr.get("detected_text_present", False)) or bool(extracted_text)
            if not extracted_text:
                detected = False

            confidence_raw = raw_ocr.get("confidence")
            confidence: float | None = None
            if isinstance(confidence_raw, (int, float)):
                confidence = float(max(0.0, min(1.0, confidence_raw)))

            language_raw = raw_ocr.get("language")
            language: str | None = str(language_raw).strip() if isinstance(language_raw, str) and language_raw.strip() else None

            sanitized_text, has_pii = sanitize_ocr_text(extracted_text)

            status = "SUCCESS" if detected else "NO_TEXT_DETECTED"

            return OCRResult(
                extracted_text=extracted_text,
                sanitized_text=sanitized_text,
                text_blocks=text_blocks,
                detected_text_present=detected,
                confidence=confidence,
                language=language,
                has_sensitive_pii=has_pii,
                provider="microsoft-foundry-vision",
                status=status,
            )
        except FoundryConfigurationError as exc:
            raise OCRUnavailable("AI OCR is not configured.") from exc
        except FoundryServiceError as exc:
            raise OCRFailed("AI OCR request failed.") from exc

    def extract_ocr(self, request: OCRRequest) -> OCRResult:
        if request.image_bytes is not None:
            return self.extract_ocr_bytes(request.image_bytes, request.content_type)

        if not request.image_reference:
            raise ValueError("OCRRequest requires either image_bytes or image_reference.")

        try:
            image_bytes, content_type = get_image_bytes(request.image_reference)
        except Exception as exc:
            logger.warning("Could not download image for OCR: %s", exc)
            raise OCRFailed("Could not read image from storage.") from exc

        return self.extract_ocr_bytes(image_bytes, content_type)


class UnavailableOCRProvider:
    def extract_ocr(self, request: OCRRequest) -> OCRResult:
        raise OCRUnavailable("OCR provider is not configured yet.")

    def extract_ocr_bytes(self, image_bytes: bytes, content_type: str = "image/jpeg") -> OCRResult:
        raise OCRUnavailable("OCR provider is not configured yet.")


def get_ocr_provider() -> OCRProvider:
    try:
        return FoundryOCRProvider()
    except (FoundryConfigurationError, Exception) as exc:
        logger.info("Foundry client not available for OCR, using fallback provider: %s", exc)
        return UnavailableOCRProvider()
