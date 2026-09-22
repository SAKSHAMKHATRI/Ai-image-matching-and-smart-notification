from dataclasses import dataclass
from hashlib import sha256
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status

from app.auth.firebase import get_storage_bucket

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
    blob = get_storage_bucket().blob(path)
    blob.upload_from_string(contents, content_type=content_type)
    blob.metadata = {"firebase_uid": firebase_uid, "lost_item_id": str(item_id)}
    blob.patch()
    return StoredImage(path=path, content_type=content_type, size=len(contents))


def get_image_bytes(image_reference: str) -> tuple[bytes, str]:
    """Retrieve stored image bytes and content-type from Firebase Storage."""
    if not image_reference:
        raise ValueError("Image reference cannot be empty.")

    blob = get_storage_bucket().blob(image_reference)
    contents = blob.download_as_bytes()
    if not contents:
        raise ValueError("Image content is empty.")

    # Infer content type from extension or blob
    content_type = blob.content_type
    if not content_type:
        ext = image_reference.rsplit(".", 1)[-1].lower() if "." in image_reference else ""
        if ext in ("jpg", "jpeg"):
            content_type = "image/jpeg"
        elif ext == "png":
            content_type = "image/png"
        elif ext == "webp":
            content_type = "image/webp"
        else:
            content_type = "image/jpeg"

    return contents, content_type
