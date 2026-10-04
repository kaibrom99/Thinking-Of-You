"""Downloads product photos on our server and shrinks them.

Some stores refuse to show their pictures on other websites, so the app asks for them itself
(like a browser would), makes a small copy, and embeds that. Only public https addresses are fetched.
"""
import base64
import io
import ipaddress
import socket
import time
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from urllib.parse import urljoin, urlparse

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0 Safari/537.36")
_failed: dict = {}  # address -> when it last failed, so a broken link isn't retried on every page load


def _public_host(host: str) -> bool:
    try:
        return all(ipaddress.ip_address(a[4][0]).is_global for a in socket.getaddrinfo(host, 443))
    except Exception:
        return False


def _get(url: str, headers: dict):
    """Fetches a picture, following a few redirects but never to a private or internal address."""
    for _ in range(4):
        parts = urlparse(url)
        if parts.scheme != "https" or not _public_host(parts.hostname or ""):
            raise ValueError("blocked address")
        r = requests.get(url, headers=headers, timeout=8, allow_redirects=False)
        if r.is_redirect:
            url = urljoin(url, r.headers.get("Location", ""))
            continue
        return r
    raise ValueError("too many redirects")


@lru_cache(maxsize=400)
def _download(url: str, referer: str) -> str:
    r = _get(url, {"User-Agent": UA, "Referer": referer,
                   "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8"})
    r.raise_for_status()
    kind = r.headers.get("Content-Type", "").split(";")[0].strip().lower()
    data = r.content
    if not kind.startswith("image/") or len(data) > 8_000_000:
        raise ValueError(f"not a usable image ({kind or 'no type'}, {len(data)} bytes)")
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(data))
        im.thumbnail((240, 240))
        im = im.convert("RGBA")
        page = Image.new("RGBA", im.size, "white")
        page.alpha_composite(im)
        out = io.BytesIO()
        page.convert("RGB").save(out, "JPEG", quality=82)
        data, kind = out.getvalue(), "image/jpeg"
    except Exception:  # couldn't shrink it: keep the original only if it's small and safe
        if len(data) > 300_000 or kind == "image/svg+xml":
            raise
    return f"data:{kind};base64,{base64.b64encode(data).decode()}"


def photo(url: str, store_url: str = "") -> str:
    """A small embedded copy of the photo, or "" if it can't be fetched."""
    if time.time() - _failed.get(url, 0) < 600:
        return ""
    p = urlparse(store_url or url)
    try:
        return _download(url, f"{p.scheme}://{p.netloc}/")
    except Exception as e:
        _failed[url] = time.time()
        print(f"[photo] could not fetch {url[:150]}: {e}")
        return ""


def warm(pairs) -> None:
    """Fetches several photos at once, since doing them one by one makes the first page load slow."""
    pairs = list(pairs)
    if pairs:
        with ThreadPoolExecutor(8) as pool:
            list(pool.map(lambda p: photo(*p), pairs))