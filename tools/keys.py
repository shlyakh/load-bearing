"""Stable identifiers for the works the scans find.

A candidate's `candidate_id` is a slug an agent made up, and the same paper has been
given three different slugs in three scans. A key is derived from a URL instead, so it
is the same every time:

    arxiv:2611.07784            arXiv abstract, PDF or HTML page, any version; arXiv DOIs
    zenodo:24161799             Zenodo record page or Zenodo DOI
    doi:10.1016/j.ijforecast... any other DOI
    hf:amazon/chronos-2         Hugging Face model repository (hfd: for datasets)
    gh:owner/repo               GitHub repository; gh:owner/repo@v3.0.0 for a release
    pypi:name                   PyPI project
    url:host/path               anything else, after normalising

LinkedIn URLs never become a key (CLAUDE.md rule 10).
"""

from __future__ import annotations

import re

REPO_LEVEL = ("gh:", "hf:", "hfd:", "pypi:")  # one key can cover several releases


def norm_url(url: str) -> str:
    u = re.sub(r"^https?://(www\.)?", "", url.strip().lower()).rstrip("/")
    m = re.match(r"arxiv\.org/(?:abs|pdf|html)/(\d{4}\.\d{4,5})(?:v\d+)?(?:\.pdf)?$", u)
    return f"arxiv.org/abs/{m.group(1)}" if m else u


def norm_title(title: str) -> str:
    return re.sub(r"\W+", " ", title.lower()).strip()


def is_linkedin(url: str) -> bool:
    host = re.sub(r"^https?://", "", url.strip().lower()).split("/")[0]
    return host == "linkedin.com" or host.endswith(".linkedin.com")


def url_key(url: str) -> str | None:
    """The stable key of one URL, or None for a LinkedIn or empty URL."""
    if not url or not url.strip() or is_linkedin(url):
        return None
    u = norm_url(url).split("#")[0]
    path = u.split("?")[0].rstrip("/")
    m = re.match(r"arxiv\.org/abs/(\d{4}\.\d{4,5})$", path)
    if m:
        return f"arxiv:{m.group(1)}"
    m = re.match(r"(?:dx\.)?doi\.org/(10\.\d{4,9}/\S+)$", path)
    if m:
        doi = m.group(1)
        z = re.match(r"10\.5281/zenodo\.(\d+)$", doi)
        if z:
            return f"zenodo:{z.group(1)}"
        a = re.match(r"10\.48550/arxiv\.(\d{4}\.\d{4,5})(?:v\d+)?$", doi)
        return f"arxiv:{a.group(1)}" if a else f"doi:{doi}"
    m = re.match(r"zenodo\.org/records?/(\d+)", path)
    if m:
        return f"zenodo:{m.group(1)}"
    m = re.match(r"huggingface\.co/(?:api/models/)?([\w.-]+)/([\w.-]+)", path)
    if m and m.group(1) not in ("spaces", "datasets", "docs", "blog", "papers", "api"):
        return f"hf:{m.group(1)}/{m.group(2)}"
    m = re.match(r"huggingface\.co/(?:api/)?datasets/([\w.-]+)/([\w.-]+)", path)
    if m:
        return f"hfd:{m.group(1)}/{m.group(2)}"
    m = re.match(r"github\.com/([\w.-]+)/([\w.-]+)(?:/releases/tag/([^/]+))?", path)
    if m:
        repo = f"gh:{m.group(1)}/{re.sub(r'\.git$', '', m.group(2))}"
        return f"{repo}@{m.group(3)}" if m.group(3) else repo
    m = re.match(r"pypi\.org/project/([\w.-]+)", path)
    if m:
        return f"pypi:{m.group(1)}"
    return f"url:{u}"


def title_key(title: str) -> str | None:
    t = norm_title(title or "")
    return f"t:{t}" if t else None


def stable_key(primary_url: str, title: str = "") -> str | None:
    """The key of a work: from its primary URL, else from its title."""
    return url_key(primary_url) or title_key(title)


def repo_level(key: str) -> bool:
    """True for a key that names a repository or package, not one release of it."""
    return key.startswith(REPO_LEVEL) and "@" not in key
