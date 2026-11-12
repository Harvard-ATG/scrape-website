"""Canonical BASE URL identity (ported from corpus_crossover.norm_base):
scheme->https, host lowered, no fragment, no query, no trailing slash. Used to
compare sitemap URLs against manifest source_urls. Returns "" for empty input
or URLs without a host (relative paths) so they drop out of set math."""
from urllib.parse import urlparse, urlunparse


def norm_base(u: str | None) -> str:
    if not u:
        return ""
    p = urlparse(u.strip())
    if not p.netloc:
        return ""
    path = p.path.rstrip("/") or "/"
    return urlunparse(("https", p.netloc.lower(), path, "", "", ""))
