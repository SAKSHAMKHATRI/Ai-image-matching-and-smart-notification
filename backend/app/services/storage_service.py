import logging
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status

from app.auth.firebase import get_storage_bucket

logger = logging.getLogger(__name__)

MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def _matches_image_signature(contents: bytes, content_type: str) -> bool:
    if content_type == "image/jpeg":
        return contents.startswith(b"\xff\xd8\xff")
    if content_type == "image/png":
        return contents.startswith(b"\x89PNG\r\n\x1a\n")
    if content_type == "image/webp":
        return len(contents) >= 12 and contents[:4] == b"RIFF" and contents[8:12] == b"WEBP"
    return False


@dataclass(frozen=True)
class StoredImage:
    path: str
    content_type: str
    size: int


async def validate_and_read_image(upload: UploadFile) -> tuple[bytes, str]:
    content_type = upload.content_type or ""
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only JPEG, PNG, and WebP images are supported.",
        )

    contents = await upload.read(MAX_IMAGE_BYTES + 1)
    if len(contents) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Image exceeds the 5 MB size limit.",
        )
    if not contents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image file cannot be empty.",
        )
    if not _matches_image_signature(contents, content_type):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Image content does not match its declared type.",
        )
    return contents, content_type


def store_image(
    contents: bytes,
    content_type: str,
    firebase_uid: str,
    item_id: int,
    collection: str = "lost-items",
) -> StoredImage:
    extension = ALLOWED_IMAGE_TYPES[content_type]
    owner_key = sha256(firebase_uid.encode("utf-8")).hexdigest()
    if collection not in {"lost-items", "found-items"}:
        raise ValueError("Unsupported image collection.")
    path = f"{collection}/{owner_key}/{item_id}/{uuid4().hex}{extension}"

    try:
        bucket = get_storage_bucket()
        blob = bucket.blob(path)
        blob.upload_from_string(contents, content_type=content_type)
        blob.metadata = {"firebase_uid": firebase_uid, "lost_item_id": str(item_id)}
        blob.patch()
        return StoredImage(path=path, content_type=content_type, size=len(contents))
    except Exception as exc:
        # Resilient local fallback when remote storage bucket is unprovisioned (404) or offline
        logger.warning("Firebase Storage upload failed (%s). Saving to local storage fallback.", exc)
        local_dir = Path("data") / "uploads" / collection / owner_key / str(item_id)
        local_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{uuid4().hex}{extension}"
        local_file_path = local_dir / filename
        with open(local_file_path, "wb") as f:
            f.write(contents)
        rel_path = f"{collection}/{owner_key}/{item_id}/{filename}"
        return StoredImage(path=rel_path, content_type=content_type, size=len(contents))


def get_image_bytes(image_reference: str) -> tuple[bytes, str]:
    """Retrieve stored image bytes and content-type from Firebase Storage or local fallback."""
    if not image_reference:
        raise ValueError("Image reference cannot be empty.")

    # Try local storage fallback first if file exists on disk
    local_path = Path("data") / "uploads" / image_reference
    if local_path.exists():
        contents = local_path.read_bytes()
        ext = image_reference.rsplit(".", 1)[-1].lower() if "." in image_reference else ""
        content_type = "image/png" if ext == "png" else ("image/webp" if ext == "webp" else "image/jpeg")
        return contents, content_type

    try:
        blob = get_storage_bucket().blob(image_reference)
        contents = blob.download_as_bytes()
        if contents:
            content_type = blob.content_type
            if not content_type:
                ext = image_reference.rsplit(".", 1)[-1].lower() if "." in image_reference else ""
                content_type = "image/png" if ext == "png" else ("image/webp" if ext == "webp" else "image/jpeg")
            return contents, content_type
    except Exception as exc:
        logger.warning("Failed to retrieve image from Firebase Storage: %s", exc)

    raise ValueError("Image file could not be found or read.")
