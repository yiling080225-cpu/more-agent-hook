"""测试: 参考素材解析"""
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from federation_sdk.models import ImageRef, WebPageRef, ProjectRef, Reference, ReferenceType
from federation_sdk.references import (
    resolve_reference, estimate_reference_tokens,
    _image_to_base64, _get_image_size,
)


class TestResolveReference:
    def test_url_is_webpage(self):
        ref = resolve_reference("https://example.com/page")
        assert ref.type == ReferenceType.WEB_PAGE

    def test_png_is_image(self):
        ref = resolve_reference("/tmp/test.png")
        assert ref.type == ReferenceType.IMAGE

    def test_jpg_is_image(self):
        ref = resolve_reference("/tmp/photo.jpg")
        assert ref.type == ReferenceType.IMAGE

    def test_directory_is_project(self):
        ref = resolve_reference("/tmp")
        assert ref.type == ReferenceType.PROJECT


class TestEstimateTokens:
    def test_image_ref(self):
        import os
        png_path = os.path.join(tempfile.gettempdir(), "_test_minimal.png")
        with open(png_path, "wb") as f:
            f.write(b'\x89PNG\r\n\x1a\n' + b'\x00' * 200)
        ref = ImageRef(source=png_path, description="test")
        tokens, warnings = estimate_reference_tokens([ref])
        assert tokens > 0

    def test_webpage_ref(self):
        ref = WebPageRef(source="https://example.com")
        tokens, warnings = estimate_reference_tokens([ref])
        assert tokens > 0

    def test_multiple_refs(self):
        ref1 = WebPageRef(source="https://a.com")
        ref2 = WebPageRef(source="https://b.com")
        tokens, _ = estimate_reference_tokens([ref1, ref2])
        assert tokens >= 10000


class TestImageToBase64:
    def test_valid_png(self):
        import os
        png_path = os.path.join(tempfile.gettempdir(), "_test_b64.png")
        with open(png_path, "wb") as f:
            f.write(b'\x89PNG\r\n\x1a\n' + b'\x00' * 100)
        b64 = _image_to_base64(png_path)
        assert len(b64) > 0
        assert len(b64) > 10
