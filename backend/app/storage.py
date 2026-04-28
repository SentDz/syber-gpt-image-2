from __future__ import annotations

import base64
import hashlib
import re
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse
from uuid import uuid4

import httpx
from fastapi import UploadFile

from .settings import Settings


DATA_URL_RE = re.compile(r"^data:image/(?P<kind>png|jpeg|jpg|webp);base64,(?P<data>.+)$", re.I | re.S)


async def save_upload(settings: Settings, upload: UploadFile) -> dict[str, str]:
    suffix = _suffix_from_name(upload.filename, ".png")
    filename = f"{uuid4().hex}{suffix}"
    path = settings.uploads_dir / filename
    content = await upload.read()
    path.write_bytes(content)
    return {
        "path": str(path),
        "url": f"/storage/uploads/{filename}",
        "filename": upload.filename or filename,
        "content_type": upload.content_type or "application/octet-stream",
    }


async def save_provider_image(settings: Settings, history_id: str, item: dict[str, Any]) -> dict[str, str | None]:
    b64_json = item.get("b64_json")
    if isinstance(b64_json, str) and b64_json.strip():
        extension, raw = _decode_base64_payload(b64_json)
        filename = f"{history_id}{extension}"
        path = settings.images_dir / filename
        path.write_bytes(raw)
        return {"path": str(path), "url": f"/storage/images/{filename}", "source_url": None}

    image_url = item.get("url")
    if isinstance(image_url, str) and image_url.strip():
        async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
            response = await client.get(image_url)
            response.raise_for_status()
        extension = _suffix_from_content_type(response.headers.get("content-type")) or _suffix_from_name(image_url, ".png")
        filename = f"{history_id}{extension}"
        path = settings.images_dir / filename
        path.write_bytes(response.content)
        return {"path": str(path), "url": f"/storage/images/{filename}", "source_url": image_url}

    raise ValueError("Provider response did not contain b64_json or url")


async def cache_remote_image(settings: Settings, image_url: str, client: httpx.AsyncClient) -> dict[str, str] | None:
    parsed = urlparse(image_url)
    if parsed.scheme not in {"http", "https"}:
        return None

    settings.inspirations_dir.mkdir(parents=True, exist_ok=True)
    image_hash = hashlib.sha256(image_url.encode("utf-8")).hexdigest()[:32]
    for suffix in (".png", ".jpg", ".jpeg", ".webp", ".avif", ".gif"):
        path = settings.inspirations_dir / f"{image_hash}{suffix}"
        if path.exists() and path.stat().st_size > 0:
            return {"path": str(path), "url": f"/storage/inspirations/{path.name}", "source_url": image_url}

    response = await client.get(
        image_url,
        headers={
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "User-Agent": "joko-image/1.0",
        },
    )
    response.raise_for_status()
    content_type = response.headers.get("content-type")
    normalized_type = content_type.split(";", 1)[0].strip().lower() if content_type else ""
    if normalized_type and not normalized_type.startswith("image/"):
        raise ValueError(f"Remote resource is not an image: {normalized_type}")

    extension = _suffix_from_content_type(content_type) or _suffix_from_name(image_url, ".jpg")
    filename = f"{image_hash}{extension}"
    path = settings.inspirations_dir / filename
    path.write_bytes(response.content)
    return {"path": str(path), "url": f"/storage/inspirations/{filename}", "source_url": image_url}


def delete_storage_files(settings: Settings, paths: Iterable[str]) -> dict[str, int]:
    storage_root = settings.storage_dir.resolve()
    deleted = 0
    missing = 0
    skipped = 0
    errors = 0
    for raw_path in sorted({str(path).strip() for path in paths if str(path).strip()}):
        try:
            path = Path(raw_path).expanduser()
            resolved = path.resolve(strict=False)
            resolved.relative_to(storage_root)
        except (OSError, ValueError):
            skipped += 1
            continue
        if not resolved.exists():
            missing += 1
            continue
        if not resolved.is_file():
            skipped += 1
            continue
        try:
            resolved.unlink()
            deleted += 1
        except OSError:
            errors += 1
    return {"deleted_files": deleted, "missing_files": missing, "skipped_files": skipped, "file_errors": errors}


def _decode_base64_payload(value: str) -> tuple[str, bytes]:
    stripped = value.strip()
    match = DATA_URL_RE.match(stripped)
    if match:
        kind = match.group("kind").lower()
        extension = ".jpg" if kind == "jpeg" else f".{kind}"
        stripped = match.group("data").strip()
    else:
        extension = ".png"
    return extension, base64.b64decode(stripped)


def _suffix_from_content_type(content_type: str | None) -> str | None:
    if not content_type:
        return None
    normalized = content_type.split(";", 1)[0].strip().lower()
    return {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/webp": ".webp",
        "image/avif": ".avif",
        "image/gif": ".gif",
    }.get(normalized)


def _suffix_from_name(name: str | None, default: str) -> str:
    if not name:
        return default
    suffix = Path(name.split("?", 1)[0]).suffix.lower()
    return suffix if suffix in {".png", ".jpg", ".jpeg", ".webp", ".avif", ".gif"} else default
