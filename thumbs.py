"""Downloads product photos on our server and shrinks them.

Some stores refuse to show their pictures on other websites, so the app asks for them itself
(like a browser would), makes a small copy, and embeds that. Only public https addresses are fetched.
"""
import base64
import html
import http.client
import io
import ipaddress
import re
import socket
import ssl
import time
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0 Safari/537.36")
_failed: dict = {}  # address -> when it last failed, so a broken link isn't retried on every page load


def _public_addresses(host: str):
    try:
        rows = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        if not rows:
            return []
        addresses = []
        for family, _kind, _proto, _canon, sockaddr in rows:
            ip = ipaddress.ip_address(sockaddr[0])
            if not ip.is_global:
                return []
            addresses.append((family, sockaddr))
        return addresses
    except Exception:
        return []


def _public_host(host: str) -> bool:
    return bool(_public_addresses(host))


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """TLS connection to a prevalidated IP while retaining hostname verification and SNI."""
    def __init__(self, host: str, family: int, sockaddr, timeout: int):
        super().__init__(host, port=443, timeout=timeout, context=ssl.create_default_context())
        self._family, self._sockaddr = family, sockaddr

    def connect(self):
        sock = socket.socket(self._family, socket.SOCK_STREAM)
        try:
            sock.settimeout(self.timeout)
            sock.connect(self._sockaddr)
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
        except Exception:
            sock.close()
            raise


class _Response:
    def __init__(self, status: int, headers, content: bytes):
        self.status_code, self.headers, self.content = status, headers, content
        self.is_redirect = status in (301, 302, 303, 307, 308)

    def raise_for_status(self):
        if not 200 <= self.status_code < 300:
            raise ValueError(f"upstream returned HTTP {self.status_code}")


def _get(url: str, headers: dict, max_bytes: int = 8_000_000):
    """Fetch a bounded HTTPS response while pinning the socket to a validated public IP."""
    for _ in range(4):
        parts = urlparse(url)
        host = parts.hostname or ""
        if (parts.scheme != "https" or not host or parts.username or parts.password or
                parts.port not in (None, 443)):
            raise ValueError("blocked address")
        addresses = _public_addresses(host)
        if not addresses:
            raise ValueError("blocked address")
        family, sockaddr = addresses[0]
        conn = _PinnedHTTPSConnection(host, family, sockaddr, timeout=8)
        target = parts.path or "/"
        if parts.query:
            target += "?" + parts.query
        try:
            conn.request("GET", target, headers=headers)
            response = conn.getresponse()
            response_headers = {k: v for k, v in response.getheaders()}
            if response.status in (301, 302, 303, 307, 308):
                location = response.getheader("Location", "")
                conn.close()
                if not location:
                    raise ValueError("redirect without location")
                url = urljoin(url, location)
                continue
            content = response.read(max_bytes + 1)
            if len(content) > max_bytes:
                raise ValueError("response too large")
            return _Response(response.status, response_headers, content)
        finally:
            conn.close()
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
        print(f"[photo] could not fetch product image: {e}")
        return ""


class _MetadataParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta = {}
        self.title = []
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        values = {k.lower(): v for k, v in attrs if k and v is not None}
        if tag.lower() == "meta":
            key = (values.get("property") or values.get("name") or "").lower()
            content = values.get("content", "").strip()
            if key and content and key not in self.meta:
                self.meta[key] = content
        elif tag.lower() == "title":
            self.in_title = True

    def handle_endtag(self, tag):
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title.append(data)


def page_metadata(url: str) -> dict:
    """Read basic Open Graph metadata from a public HTTPS product page, with strict size limits."""
    response = _get(url, {"User-Agent": UA, "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.1"},
                    max_bytes=1_500_000)
    response.raise_for_status()
    content_type = response.headers.get("Content-Type", "").lower()
    if "html" not in content_type:
        raise ValueError("link did not return an HTML page")
    parser = _MetadataParser()
    parser.feed(response.content.decode("utf-8", errors="replace"))
    meta = parser.meta
    title = (meta.get("og:title") or meta.get("twitter:title") or " ".join(parser.title)).strip()
    description = (meta.get("og:description") or meta.get("description") or
                   meta.get("twitter:description") or "").strip()
    image = meta.get("og:image") or meta.get("twitter:image") or ""
    if image:
        image = urljoin(url, html.unescape(image))
        if not image.startswith("https://") or len(image) > 2000:
            image = ""
    price_text = (meta.get("product:price:amount") or meta.get("og:price:amount") or
                  meta.get("price") or "")
    match = re.search(r"\d[\d,]*(?:\.\d+)?", price_text)
    try:
        price = float(match.group(0).replace(",", "")) if match else None
    except ValueError:
        price = None
    return {"title": title[:500], "description": description[:5000],
            "image_url": image, "price": price}


def warm(pairs) -> None:
    """Fetches several photos at once, since doing them one by one makes the first page load slow."""
    pairs = list(pairs)
    if pairs:
        with ThreadPoolExecutor(8) as pool:
            list(pool.map(lambda p: photo(*p), pairs))
