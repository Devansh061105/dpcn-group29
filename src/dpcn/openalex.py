"""Cached, budget-aware OpenAlex client (plan D22, guide §5.2).

Every response is cached as gzip JSON keyed by path + sorted params (excluding api_key),
so re-runs are free and team members share a cache regardless of whose key fetched it.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Iterable, Iterator

import requests

log = logging.getLogger(__name__)

WORK_SELECT = (
    "id,doi,title,publication_year,publication_date,type,cited_by_count,is_retracted,"
    "primary_location,authorships,referenced_works,primary_topic,topics"
)


def short_id(x: str | None) -> str | None:
    """'https://openalex.org/W123' -> 'W123'."""
    return x.rsplit("/", 1)[-1] if x else x


def batches(seq: Iterable, n: int = 100) -> Iterator[list]:
    seq = list(seq)
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


class BudgetExceeded(RuntimeError):
    pass


class OpenAlex:
    def __init__(self, api_key: str = "", cache_dir: str | Path = "data/cache/openalex",
                 base_url: str = "https://api.openalex.org", budget_stop_fraction: float = 0.9,
                 sleep_s: float = 0.12, max_retries: int = 6, session: requests.Session | None = None):
        self.key = api_key
        self.base = base_url.rstrip("/")
        self.cache = Path(cache_dir)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.stop_frac = budget_stop_fraction
        self.sleep_s = sleep_s
        self.max_retries = max_retries
        self.s = session or requests.Session()
        self.live_calls = 0
        self.cache_hits = 0
        self.last_budget: tuple[float, float] | None = None   # (remaining_usd, limit_usd)

    @classmethod
    def from_config(cls, cfg) -> "OpenAlex":
        o = cfg.openalex
        return cls(api_key=cfg.api_key, cache_dir=cfg.path(o.cache_dir), base_url=o.base_url,
                   budget_stop_fraction=o.budget_stop_fraction, sleep_s=o.sleep_s,
                   max_retries=o.max_retries)

    def cache_path(self, path: str, params: dict) -> Path:
        p = {k: v for k, v in params.items() if k != "api_key"}
        raw = path.strip("/") + "?" + "&".join(f"{k}={p[k]}" for k in sorted(p))
        return self.cache / (hashlib.sha1(raw.encode("utf-8")).hexdigest() + ".json.gz")

    def _check_budget(self):
        if not self.last_budget:
            return
        rem, lim = self.last_budget
        if lim and (1 - rem / lim) >= self.stop_frac:
            raise BudgetExceeded(
                f"OpenAlex daily budget nearly used: ${rem:.4f} of ${lim} left. "
                "Resets at midnight UTC; cached progress is kept.")

    def get(self, path: str, **params) -> dict:
        cp = self.cache_path(path, params)
        if cp.exists():
            self.cache_hits += 1
            with gzip.open(cp, "rt", encoding="utf-8") as f:
                return json.load(f)

        self._check_budget()
        q = dict(params)
        if self.key:
            q["api_key"] = self.key
        url = f"{self.base}/{path.strip('/')}"
        for attempt in range(self.max_retries):
            r = self.s.get(url, params=q, timeout=90)
            if r.status_code == 200:
                break
            if r.status_code in (429, 500, 502, 503, 504):
                wait = float(r.headers.get("Retry-After") or 2 ** attempt)
                log.warning("HTTP %s from OpenAlex, retrying in %.1fs", r.status_code, wait)
                time.sleep(wait)
                continue
            shown = r.url.replace(self.key, "***") if self.key else r.url
            raise RuntimeError(f"HTTP {r.status_code} for {shown}\n{r.text[:500]}")
        else:
            raise RuntimeError(f"OpenAlex: gave up after {self.max_retries} retries: {url}")

        self.live_calls += 1
        try:
            self.last_budget = (float(r.headers["X-RateLimit-Remaining-USD"]),
                                float(r.headers["X-RateLimit-Limit-USD"]))
        except (KeyError, TypeError, ValueError):
            pass
        data = r.json()
        tmp = cp.with_suffix(".tmp")
        with gzip.open(tmp, "wt", encoding="utf-8") as f:
            json.dump(data, f)
        tmp.replace(cp)   # atomic: an interrupted write never leaves a corrupt cache entry
        time.sleep(self.sleep_s)
        return data

    def entity(self, path_with_id: str, select: str | None = None) -> dict:
        """Single-entity lookup, e.g. 'institutions/I185638415' (free under OpenAlex pricing)."""
        return self.get(path_with_id, **({"select": select} if select else {}))

    def count(self, path: str, filter: str) -> int:
        return self.get(path, filter=filter, per_page=1)["meta"]["count"]

    def group_by(self, path: str, filter: str, key: str, per_page: int = 200) -> list[dict]:
        return self.get(path, filter=filter, group_by=key, per_page=per_page)["group_by"]

    def paginate(self, path: str, filter: str, select: str | None = None,
                 per_page: int = 200, **extra) -> Iterator[dict]:
        """Yield every result of a list query using cursor paging."""
        cursor = "*"
        while cursor:
            params = {"filter": filter, "per_page": per_page, "cursor": cursor, **extra}
            if select:
                params["select"] = select
            d = self.get(path, **params)
            if not d["results"]:
                break
            yield from d["results"]
            cursor = d["meta"].get("next_cursor")

    def report(self) -> str:
        budget = "unknown (all cached)" if not self.last_budget else \
            f"${self.last_budget[0]:.4f} of ${self.last_budget[1]} left today"
        return f"OpenAlex calls: {self.live_calls} live, {self.cache_hits} cached | budget: {budget}"
