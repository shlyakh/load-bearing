"""Offline checks of the Crossref, PyPI and GitHub listings in tools/feeds.py.

uv run --project core pytest tests/test_feeds.py -q
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tools.feeds as feeds  # noqa: E402

START, END = date(2026, 7, 17), date(2026, 11, 14)


class Reply:
    def __init__(self, status=200, payload=None, text=""):
        self.status_code, self._payload, self.text = status, payload, text

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise feeds.requests.HTTPError(str(self.status_code))


def test_crossref_filters_by_title_and_uses_registration_date(monkeypatch):
    items = [
        {
            "DOI": "10.1/a",
            "title": ["Probabilistic  net load forecasting"],
            "created": {"date-time": "2026-08-20T10:00:00Z"},
            "author": [{"given": "A.", "family": "Author"}],
            "container-title": ["Applied Energy"],
        },
        {
            "DOI": "10.1/b",
            "title": ["Forecasting crude oil"],
            "created": {"date-time": "2026-09-01T00:00:00Z"},
        },
        {
            "DOI": "10.1/c",
            "title": ["Load shedding policy"],
            "created": {"date-time": "2026-09-01T00:00:00Z"},
        },
    ]
    monkeypatch.setattr(
        feeds, "get", lambda url, params: Reply(payload={"message": {"items": items}})
    )
    monkeypatch.setattr(feeds.time, "sleep", lambda s: None)
    cfg = {
        "issns": ["0306-2619"],
        "query": "load forecasting",
        "must_match": ["forecast"],
        "any_of": ["load"],
    }
    rows = feeds.crossref(cfg, START, END)
    assert [r["url"] for r in rows] == ["https://doi.org/10.1/a"]
    assert rows[0]["published_at"] == "2026-08-20"
    assert rows[0]["title"] == "Probabilistic net load forecasting"
    assert rows[0]["authors_or_owner"] == "A. Author"


RSS = """<rss><channel>
<item><title>2.3.2</title><link>https://pypi.org/project/pkg/2.3.2/</link>
<author>someone@example.com</author><pubDate>Tue, 08 Sep 2026 14:07:20 GMT</pubDate></item>
<item><title>2.0.0</title><link>https://pypi.org/project/pkg/2.0.0/</link>
<pubDate>Mon, 05 Jan 2026 10:00:00 GMT</pubDate></item>
</channel></rss>"""


def test_pypi_keeps_window_and_stores_no_email(monkeypatch, capsys):
    def fake(url, **kw):
        return Reply(404) if "missing" in url else Reply(text=RSS)

    monkeypatch.setattr(feeds.requests, "get", fake)
    rows = feeds.pypi({"packages": ["pkg", "missing"]}, START, END)
    assert [r["title"] for r in rows] == ["pkg 2.3.2"]
    assert rows[0]["published_at"] == "2026-09-08"
    assert "@" not in str(rows)
    assert "no package named missing" in capsys.readouterr().out


def test_github_releases_window_drafts_and_missing_repo(monkeypatch, capsys):
    rels = [
        {
            "tag_name": "v1.1",
            "name": "",
            "published_at": "2026-09-08T14:06:51Z",
            "html_url": "https://github.com/o/r/releases/tag/v1.1",
        },
        {
            "tag_name": "v1.2",
            "name": "Draft",
            "published_at": "2026-10-01T00:00:00Z",
            "html_url": "x",
            "draft": True,
        },
        {
            "tag_name": "v1.0",
            "name": "Old",
            "published_at": "2026-06-18T11:30:31Z",
            "html_url": "y",
        },
    ]

    def fake(url, **kw):
        return Reply(404) if "gone" in url else Reply(payload=rels)

    monkeypatch.setattr(feeds.requests, "get", fake)
    rows = feeds.github_releases({"repos": ["o/r", "o/gone"]}, START, END)
    assert [(r["title"], r["published_at"], r["authors_or_owner"]) for r in rows] == [
        ("o/r v1.1", "2026-09-08", "o")
    ]
    assert "no repository named o/gone" in capsys.readouterr().out
