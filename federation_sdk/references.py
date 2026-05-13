from __future__ import annotations

import base64
import os
from pathlib import Path

from federation_sdk.models import Reference, ReferenceType, ImageRef, WebPageRef, ProjectRef


def _image_to_base64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def _get_image_size(path: str) -> tuple[int, int]:
    try:
        from PIL import Image
        with Image.open(path) as img:
            return img.size
    except ImportError:
        size = os.path.getsize(path)
        estimated_pixels = size // 3
        width = int(estimated_pixels ** 0.5 * 1.5)
        height = int(estimated_pixels ** 0.5 / 1.5)
        return (max(width, 100), max(height, 100))


def resolve_reference(source: str, description: str = "") -> Reference:
    if source.startswith("http://") or source.startswith("https://"):
        return WebPageRef(source=source, description=description)
    path = Path(source)
    if path.is_dir():
        return ProjectRef(source=str(path.resolve()), description=description)
    ext = path.suffix.lower()
    if ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"):
        return ImageRef(source=str(path.resolve()), description=description)
    if ext in (".url", ".txt"):
        return WebPageRef(source=str(path.resolve()), description=description)
    return ProjectRef(source=str(path.resolve()), description=description)


def prepare_image_payload(image_ref: ImageRef) -> dict:
    b64 = _image_to_base64(image_ref.source)
    width, height = _get_image_size(image_ref.source)
    _, ext = os.path.splitext(image_ref.source)
    mime_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp"}
    return {
        "type": "image",
        "source": image_ref.source,
        "description": image_ref.description,
        "data": f"data:{mime_map.get(ext.lower(), 'image/png')};base64,{b64}",
        "width": width,
        "height": height,
    }


def estimate_reference_tokens(refs: list[Reference]) -> tuple[int, list[str]]:
    total = 0
    warnings: list[str] = []
    for ref in refs:
        if isinstance(ref, ImageRef):
            try:
                w, h = _get_image_size(ref.source)
                tokens = (w * h) // 64
                total += tokens
                if w * h > 800 * 600:
                    warnings.append(f"图片 {ref.source} 较大 ({w}x{h})，解析需额外 token")
            except Exception:
                total += 5000
                warnings.append(f"无法读取图片 {ref.source}，使用默认估算")
        elif isinstance(ref, WebPageRef):
            total += 5000
            if ref.source.startswith("http"):
                total += 2000
        elif isinstance(ref, ProjectRef):
            try:
                file_count = sum(1 for _ in Path(ref.source).rglob("*") if _.is_file())
                total += 2000 + file_count * 500
            except Exception:
                total += 5000
    return total, warnings
