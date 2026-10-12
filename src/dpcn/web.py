"""Polite, cached fetcher for lab websites (S01). HTML is cached under data/cache/web/."""
from __future__ import annotations

import hashlib
import logging
import time
from pathlib import Path

import requests

log = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (compatible; DPCN-course-research-mapping/0.1; academic project)"


class WebFetcher:
    def __init__(self, cache_dir: str | Path, delay_s: float = 1.0, timeout: int = 45,
                 refresh: bool = False, session: requests.Session | None = None):
        self.refresh = refresh   # True: ignore cached HTML and re-download (cache is overwritten)
        self.cache = Path(cache_dir)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.delay_s = delay_s
        self.timeout = timeout
        self.s = session or requests.Session()
        self.s.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "en"})
        self.live = 0
        self.cached = 0
        self._last = 0.0

    def get(self, url: str) -> str:
        cp = self.cache / (hashlib.sha1(url.encode("utf-8")).hexdigest() + ".html")
        if cp.exists() and not self.refresh:
            self.cached += 1
            return cp.read_text(encoding="utf-8")
        wait = self.delay_s - (time.time() - self._last)
        if wait > 0:
            time.sleep(wait)
        for attempt in range(3):
            try:
                r = self.s.get(url, timeout=self.timeout)
                self._last = time.time()
                r.raise_for_status()
                break
            except requests.RequestException as e:
                if attempt == 2:
                    raise
                log.warning("fetch failed (%s), retrying: %s", e, url)
                time.sleep(3 * (attempt + 1))
        r.encoding = r.apparent_encoding if not r.encoding or r.encoding.lower() == "iso-8859-1" else r.encoding
        cp.write_text(r.text, encoding="utf-8")
        self.live += 1
        return r.text
