import pytest

from dpcn.openalex import BudgetExceeded, OpenAlex, batches, short_id


class FakeResponse:
    def __init__(self, payload, status=200, headers=None):
        self._payload, self.status_code = payload, status
        self.headers = headers or {"X-RateLimit-Remaining-USD": "0.9", "X-RateLimit-Limit-USD": "1"}
        self.url, self.text = "https://api.openalex.org/fake", ""

    def json(self):
        return self._payload


class FakeSession:
    """Serves queued responses and records the params of each call."""
    def __init__(self, responses):
        self.responses, self.calls = list(responses), []

    def get(self, url, params=None, timeout=None):
        self.calls.append(dict(params or {}))
        return self.responses.pop(0)


def client(tmp_path, responses, key="secret"):
    return OpenAlex(api_key=key, cache_dir=tmp_path, sleep_s=0, session=FakeSession(responses))


def test_short_id_and_batches():
    assert short_id("https://openalex.org/W123") == "W123"
    assert short_id("A5") == "A5"
    assert short_id(None) is None
    assert [len(b) for b in batches(range(250), 100)] == [100, 100, 50]


def test_cache_key_ignores_api_key(tmp_path):
    oa = OpenAlex(cache_dir=tmp_path)
    assert oa.cache_path("works", {"filter": "x", "api_key": "a"}) == \
        oa.cache_path("works", {"filter": "x", "api_key": "b"}) == oa.cache_path("works", {"filter": "x"})
    assert oa.cache_path("works", {"a": 1, "b": 2}) == oa.cache_path("works", {"b": 2, "a": 1})


def test_second_call_is_served_from_cache(tmp_path):
    oa = client(tmp_path, [FakeResponse({"meta": {"count": 7}, "results": []})])
    assert oa.count("works", "x") == 7
    assert oa.count("works", "x") == 7
    assert oa.live_calls == 1 and oa.cache_hits == 1
    assert oa.s.calls[0]["api_key"] == "secret"
    assert oa.last_budget == (0.9, 1.0)


def test_paginate_follows_cursor(tmp_path):
    pages = [
        FakeResponse({"meta": {"next_cursor": "c2"}, "results": [{"id": 1}, {"id": 2}]}),
        FakeResponse({"meta": {"next_cursor": "c3"}, "results": [{"id": 3}]}),
        FakeResponse({"meta": {"next_cursor": None}, "results": []}),
    ]
    oa = client(tmp_path, pages)
    assert [r["id"] for r in oa.paginate("works", "f", select="id")] == [1, 2, 3]
    assert [c["cursor"] for c in oa.s.calls] == ["*", "c2", "c3"]
    # fully cached replay makes no live calls
    oa2 = client(tmp_path, [])
    assert [r["id"] for r in oa2.paginate("works", "f", select="id")] == [1, 2, 3]
    assert oa2.live_calls == 0


def test_budget_guard_stops_live_calls(tmp_path):
    low = {"X-RateLimit-Remaining-USD": "0.05", "X-RateLimit-Limit-USD": "1"}
    oa = client(tmp_path, [FakeResponse({"meta": {"count": 1}, "results": []}, headers=low)])
    oa.count("works", "a")
    with pytest.raises(BudgetExceeded):
        oa.count("works", "b")
    assert oa.count("works", "a") == 1     # cached reads still work


def test_retries_then_raises_on_400(tmp_path):
    ok = FakeResponse({"meta": {"count": 3}, "results": []})
    oa = client(tmp_path, [FakeResponse({}, status=503, headers={"Retry-After": "0"}), ok])
    assert oa.count("works", "x") == 3
    bad = client(tmp_path / "b", [FakeResponse({}, status=400, headers={})])
    with pytest.raises(RuntimeError, match="HTTP 400"):
        bad.count("works", "bad-filter")
