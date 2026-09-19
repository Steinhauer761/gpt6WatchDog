import hashlib
import io
from typing import Any

from fastapi import HTTPException, UploadFile
from PIL import ExifTags, Image, UnidentifiedImageError

MAX_UPLOAD_BYTES = 25 * 1024 * 1024


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    try:
        return float(value)
    except (TypeError, ValueError, OverflowError):
        return str(value)


async def inspect_media_file(upload: UploadFile) -> dict:
    raw = await upload.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File is larger than the 25 MB inspection limit")
    if not raw:
        raise HTTPException(status_code=400, detail="The uploaded file is empty")

    result = {
        "filename": upload.filename or "unnamed",
        "content_type": upload.content_type or "application/octet-stream",
        "size_bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "image": None,
        "note": "Hashes and metadata describe the submitted file. Metadata can be missing, altered or forged and is not proof of authorship or authenticity.",
    }

    try:
        with Image.open(io.BytesIO(raw)) as image:
            image.verify()
        with Image.open(io.BytesIO(raw)) as image:
            exif = image.getexif()
            tags = {}
            for tag_id, value in exif.items():
                name = ExifTags.TAGS.get(tag_id, str(tag_id))
                tags[str(name)] = _json_safe(value)
            result["image"] = {
                "format": image.format,
                "width": image.width,
                "height": image.height,
                "mode": image.mode,
                "exif": tags,
                "exif_tag_count": len(tags),
            }
    except (UnidentifiedImageError, OSError, ValueError):
        pass

    return result
