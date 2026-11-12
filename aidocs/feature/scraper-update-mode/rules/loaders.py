"""Load the offline inputs the validation uses: sitemap snapshots, sites.toml, cached QA manifests.

Paths can be overridden with environment variables: SITES_TOML, MANIFEST_CACHE.
Hosts missing any input are skipped by callers, never invented.
"""
from __future__ import annotations

import glob
import gzip
import json
import os
import tomllib
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURES = HERE / "fixtures"
SNAP_OCT = FIXTURES / "sitemaps_2026-10-15.json.gz"
SNAP_JUL = FIXTURES / "sitemaps_2026-07-28.json.gz"
SITES_TOML = Path(os.environ.get("SITES_TOML", REPO.parent / "apo-mcp-server" / "sites.toml"))
MANIFEST_CACHE = Path(os.environ.get(
    "MANIFEST_CACHE", HERE.parent / "evidence" / "cadence-analysis" / "manifest-cache"))

# Hostnames that moved in the Harvard reorganization (old -> new); old names appear in the snapshots.
MOVED_HOSTS = {
    "oie.fas.harvard.edu": "studyabroad.college.harvard.edu",
    "summerfunding.college.harvard.edu": "sfsao.college.harvard.edu",
    "incomingstudents.college.harvard.edu": "firstyear.college.harvard.edu",
    "oaisc.fas.harvard.edu": "secretary.college.harvard.edu",
}


def load_snapshot(path: Path) -> dict[str, dict]:
    with gzip.open(path, "rt") as f:
        return json.load(f)


def sitemap_dict(snap_host: dict | None) -> dict[str, str | None] | None:
    """{url: lastmod or None} from a snapshot host record, or None if unreadable."""
    if not snap_host or snap_host.get("status") != "ok" or not snap_host.get("entries"):
        return None
    return {loc: (lm or None) for loc, lm in snap_host["entries"]}


def load_sites() -> dict[str, list[dict]]:
    """sites.toml entries grouped by hostname (live entries only; comments are ignored by the parser)."""
    with open(SITES_TOML, "rb") as f:
        sites = tomllib.load(f)["sites"]
    by: dict[str, list[dict]] = {}
    for s in sites:
        by.setdefault(s["hostname"], []).append(s)
    return by


def load_manifest(host: str) -> tuple[list[dict], datetime | None] | None:
    p = MANIFEST_CACHE / f"{host}.manifest.json"
    if not p.exists():
        return None
    m = json.load(open(p))
    files = m["files"]
    entries = list(files.values() if isinstance(files, dict) else files)
    try:
        gen = datetime.fromisoformat(m["generated_at"])
    except Exception:
        gen = None
    return entries, gen


def manifest_hosts() -> list[str]:
    return sorted(os.path.basename(f)[: -len(".manifest.json")] for f in glob.glob(str(MANIFEST_CACHE / "*.manifest.json")))
