"""Small HTTP helper with browser-like headers and a per-run cache."""
import base64
import time
from urllib.parse import urldefrag, urljoin, urlparse

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")


# Be a polite visitor: requests to the same site are spaced out and capped, and once the site
# pushes back (403/429/503) we stop asking it, so its anti-bot protection has no reason to kick in.
HOST_GAP = 1.0        # seconds between two requests to the same site
HOST_MAX = 40         # requests to the client's site per run (images on CDNs not counted)


class Fetcher:
    def __init__(self, timeout=20, max_requests=80, bundle=None):
        self.s = requests.Session()
        self.s.headers.update({
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "ro-RO,ro;q=0.9,en;q=0.8",
        })
        self.timeout = timeout
        self.cache = {}
        self.count = 0
        self.max_requests = max_requests
        self.log = []
        self.last_hit = {}     # host -> time of the last request
        self.host_count = {}   # host -> requests made
        self.refused = set()   # hosts that pushed back: not asked again in this run
        # pages/images captured in the team member's own browser (bookmarklet or saved page)
        self.bundle = {bkey(k): v for k, v in (bundle or {}).items()}

    def from_bundle(self, url, binary):
        item = self.bundle.get(bkey(url))
        if not item:
            return None
        ctype = (item.get("type") or "").lower()
        final = item.get("final") or url
        if binary:
            if "b64" in item:
                return final, base64.b64decode(item["b64"]), ctype
            return final, (item.get("text") or "").encode("utf-8"), ctype
        if "text" in item:
            return final, item["text"], ctype or "text/html"
        return None

    def get(self, url, accept=None, binary=False):
        """Return (final_url, content, content_type) or (url, None, None) on failure."""
        key = (url, binary)
        if key in self.cache:
            return self.cache[key]
        hit = self.from_bundle(url, binary)
        if hit:
            self.cache[key] = hit
            return hit
        if self.count >= self.max_requests:
            return url, None, None
        host = urlparse(url).netloc.lower().removeprefix("www.")
        if host in self.refused or self.host_count.get(host, 0) >= HOST_MAX:
            return url, None, None
        wait = HOST_GAP - (time.time() - self.last_hit.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        self.last_hit[host] = time.time()
        self.host_count[host] = self.host_count.get(host, 0) + 1
        self.count += 1
        headers = {"Accept": accept} if accept else {}
        res = (url, None, None)
        for attempt in range(2):
            try:
                r = self.s.get(url, timeout=self.timeout, headers=headers, allow_redirects=True)
                ctype = r.headers.get("content-type", "").lower()
                if r.status_code == 200:
                    if binary:
                        res = (r.url, r.content, ctype)
                    else:
                        if not r.encoding or r.encoding.lower() == "iso-8859-1":
                            r.encoding = r.apparent_encoding or "utf-8"
                        res = (r.url, r.text, ctype)
                    break
                self.log.append(f"{r.status_code} {url}")
                if r.status_code in (429, 503) and attempt == 0:
                    # "too many requests": wait as long as the site asks (max 20 s), then try once more
                    try:
                        pause = min(20.0, max(3.0, float(r.headers.get("retry-after", "8"))))
                    except ValueError:
                        pause = 8.0
                    time.sleep(pause)
                    self.last_hit[host] = time.time()
                    continue
                if r.status_code in (401, 403, 429, 503):
                    self.refused.add(host)  # the site said stop: we stop
                    break
                if r.status_code in (404, 410):
                    break
            except requests.RequestException as e:
                self.log.append(f"ERR {url}: {e.__class__.__name__}")
                time.sleep(1)
        self.cache[key] = res
        return res

    def json(self, url):
        import json
        _, text, ctype = self.get(url, accept="application/json")
        if not text:
            return None
        try:
            return json.loads(text)
        except ValueError:
            return None


def bkey(url):
    """Lookup key for captured pages: no fragment, no trailing slash, no www, http == https."""
    u = urldefrag(url or "")[0].strip()
    p = urlparse(u)
    host = p.netloc.lower().removeprefix("www.")
    path = p.path.rstrip("/")
    return f"{host}{path}" + (f"?{p.query}" if p.query else "")


def absolute(base, href):
    if not href:
        return None
    href = href.strip()
    if href.startswith(("javascript:", "data:", "#", "mailto:", "tel:")):
        return None
    return urljoin(base, href)


def same_site(a, b):
    ha = urlparse(a).netloc.lower().removeprefix("www.")
    hb = urlparse(b).netloc.lower().removeprefix("www.")
    return ha == hb or ha.endswith("." + hb) or hb.endswith("." + ha)
