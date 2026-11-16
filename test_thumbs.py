import base64
import io

import pytest

pytest.importorskip("PIL")
from PIL import Image  # noqa: E402

import thumbs  # noqa: E402


class FakeResponse:
    is_redirect = False

    def __init__(self, data, kind="image/png"):
        self.content, self.headers = data, {"Content-Type": kind}

    def raise_for_status(self):
        pass


def png(size=(800, 600)):
    buf = io.BytesIO()
    Image.new("RGB", size, "red").save(buf, "PNG")
    return buf.getvalue()


def test_photo_is_shrunk(monkeypatch):
    thumbs._download.cache_clear()
    thumbs._failed.clear()
    monkeypatch.setattr(thumbs, "_get", lambda url, headers: FakeResponse(png()))
    uri = thumbs.photo("https://img.example.com/a.png", "https://www.example.com/p/1")
    assert uri.startswith("data:image/jpeg;base64,")
    im = Image.open(io.BytesIO(base64.b64decode(uri.split(",")[1])))
    assert max(im.size) <= 240


def test_non_images_are_rejected(monkeypatch):
    thumbs._download.cache_clear()
    thumbs._failed.clear()
    monkeypatch.setattr(thumbs, "_get", lambda url, headers: FakeResponse(b"<html></html>", "text/html"))
    assert thumbs.photo("https://img.example.com/not-a-photo") == ""


def test_private_addresses_are_blocked():
    assert thumbs._public_host("localhost") is False
    assert thumbs._public_host("127.0.0.1") is False


def test_page_preview_extracts_open_graph_metadata(monkeypatch):
    page = b'''<html><head><meta property="og:title" content="Soft Wool Scarf">
    <meta property="og:description" content="Warm and cozy">
    <meta property="og:image" content="/images/scarf.jpg">
    <meta property="product:price:amount" content="48.50"></head></html>'''
    monkeypatch.setattr(thumbs, "_get", lambda url, headers, max_bytes=8_000_000: FakeResponse(page, "text/html"))
    data = thumbs.page_metadata("https://shop.example.com/products/scarf")
    assert data == {"title": "Soft Wool Scarf", "description": "Warm and cozy",
                    "image_url": "https://shop.example.com/images/scarf.jpg", "price": 48.5}
