"""Small HTTP helper with browser-like headers and a per-run cache."""
import time
from urllib.parse import urljoin, urlparse

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")


class Fetcher:
    def __init__(self, timeout=20, max_requests=80):
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

    def get(self, url, accept=None, binary=False):
        """Return (final_url, content, content_type) or (url, None, None) on failure."""
        key = (url, binary)
        if key in self.cache:
            return self.cache[key]
        if self.count >= self.max_requests:
            return url, None, None
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
                if r.status_code in (403, 404, 410):
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
