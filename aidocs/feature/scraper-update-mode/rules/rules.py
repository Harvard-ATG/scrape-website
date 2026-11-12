"""Reference implementation of the scraping rules in RULES.md.

Pure functions, no network, no database. It reuses the scraper's own scope helpers so the two
cannot drift apart. Rules marked PROPOSED are open decisions in the Scraping Decisions Log and are
only applied when adopt_proposed=True.

Rule ids (R1, R2, ...) match RULES.md.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urlsplit

from scrape_website.scraper import (
    DOWNLOADABLE_EXTENSIONS,
    _DEFAULT_EXCLUDE_PATTERNS,
    _normalize_url,
    _url_excluded,
    _url_within_path_prefix,
)

# --- PROPOSED excludes (decisions 6, 7, 43); applied only when adopt_proposed=True -----------------
PROPOSED_EXCLUDES: dict[str, str] = {
    "event_feed": r"\.ics(\?|$)",   # /node/N/event-feed.ics iCal feeds, not pages (decision 6)
    "http_dup": r"^http://",        # http twin of an https page (decision 7, PR #9)
    "search": r"/search\?",         # search-result pages (decision 6)
    "wp_admin": r"/wp-admin/",      # WordPress admin and ical duplicates (decision 6)
}

_EVENT_PAGE = re.compile(r"/(events?|calendar[_-]?events?)/[^/]+$", re.I)   # individual event pages
_PAGINATION = re.compile(r"/page/\d+", re.I)
_TAG_ARCHIVE = re.compile(r"/(tag|author|category)/", re.I)
_DATE_ARCHIVE = re.compile(r"^/\d{4}(/\d{2}){0,2}$")
_ADMIN = re.compile(r"/(wp-admin|cdn-cgi)/|wp-sitemap[^/]*\.xml$", re.I)


# --- R1: normalization ------------------------------------------------------------------------------
def normalize_key(url: str) -> str:
    """Canonical comparison key: https, lowercase host, no fragment, no trailing slash, query kept."""
    p = urlsplit(url.strip())
    path = p.path.rstrip("/")
    return f"https://{p.netloc.lower()}{path}" + (f"?{p.query}" if p.query else "")


def parse_lastmod(value: str | None) -> datetime | None:
    """Parse a sitemap lastmod into an aware UTC datetime (R14: full timestamps, never dates only).

    A bare date (YYYY-MM-DD, optionally followed by Z) carries no time, so it is read as the END of that day:
    a page edited later on the baseline day is then still seen as changed instead of being missed.
    Trailing text after a date is not accepted.
    """
    if not value:
        return None
    s = value.strip().replace("Z", "+00:00")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}(\+00:00)?", s):
        try:
            d = datetime.strptime(s[:10], "%Y-%m-%d")
        except ValueError:
            return None
        return d.replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
    try:
        d = datetime.fromisoformat(s)
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


# --- Taxonomy: what kind of URL is this? ------------------------------------------------------------
def url_kind(url: str) -> str:
    """Primary kind of a URL. See the URL taxonomy in RULES.md."""
    p = urlsplit(url)
    path = p.path.lower()
    if _ADMIN.search(path):
        return "admin"
    if path.endswith(".ics"):
        return "event_feed"
    if any(path.endswith(ext) for ext in DOWNLOADABLE_EXTENSIONS):
        return "file_binary"
    if "/resource/" in path:
        return "resource_page"
    if _TAG_ARCHIVE.search(path):
        return "tag_archive"
    if _PAGINATION.search(path) or _DATE_ARCHIVE.match(path):
        return "archive_listing"
    if p.query:
        return "query_variant"
    if _EVENT_PAGE.search(path):
        return "event_page"
    return "page"


# --- R2-R7: scope -----------------------------------------------------------------------------------
@dataclass(frozen=True)
class Decision:
    in_scope: bool
    reason: str          # 'ok', 'seed', 'foreign_host', 'outside_path', 'include_miss', 'excluded', 'proposed:<name>'
    kind: str = "page"


def _entry_decision(url: str, host: str, entry: dict, adopt_proposed: bool, exclude_events: bool) -> Decision:
    n = _normalize_url(url)
    p = urlsplit(n)
    kind = url_kind(n)
    if p.netloc.lower() != host.lower():
        return Decision(False, "foreign_host", kind)                                     # R2
    if entry.get("scope_to_path", False):                                                # R3
        prefix = urlsplit(entry["url"]).path
        if not _url_within_path_prefix(p.path, prefix):
            return Decision(False, "outside_path", kind)
    inc = [re.compile(x) for x in entry.get("include_patterns", [])]                     # R4
    if inc and not any(x.search(n) for x in inc):
        return Decision(False, "include_miss", kind)
    exc = [re.compile(x) for x in list(_DEFAULT_EXCLUDE_PATTERNS) + entry.get("exclude_patterns", [])]
    if _url_excluded(n, exc):                                                            # R5
        return Decision(False, "excluded", kind)
    if adopt_proposed:                                                                   # R6 (PROPOSED)
        for name, pat in PROPOSED_EXCLUDES.items():
            if re.search(pat, url):
                return Decision(False, f"proposed:{name}", kind)
    if exclude_events and kind == "event_page":                                          # R7 (PROPOSED)
        return Decision(False, "proposed:event_policy", kind)
    return Decision(True, "ok", kind)


def evaluate(url: str, host: str, entries: list[dict], *, adopt_proposed: bool = False,
             exclude_events: bool = False) -> Decision:
    """Scope decision for one URL on one host. A host with several entries takes the union (R8);
    every entry's seed URL is always in scope (R9)."""
    key = normalize_key(url)
    for e in entries:
        if normalize_key(e["url"]) == key:
            return Decision(True, "seed", url_kind(url))
    best = Decision(False, "no_entry", url_kind(url))
    for e in entries:
        d = _entry_decision(url, host, e, adopt_proposed, exclude_events)
        if d.in_scope:
            return d
        best = d
    return best


def is_path_scoped(entries: list[dict]) -> bool:
    """True when every entry of the host is path-scoped (R10: re-fetch the seeds, skip the sitemap)."""
    return bool(entries) and all(e.get("scope_to_path", False) for e in entries)


# R10 threshold: a path-scoped host whose section has at most this many sitemap pages besides the seed is handled by
# refetching its seeds each run; a larger section is planned from the sitemap.
SECTION_PAGE_THRESHOLD = 5


# --- R11-R14: update planning -----------------------------------------------------------------------
@dataclass
class Plan:
    fetch: dict[str, str] = field(default_factory=dict)       # key -> reason: new|changed|no_lastmod|seed
    skip: list[str] = field(default_factory=list)             # unchanged
    out_of_scope: int = 0
    backfill: dict[str, str] = field(default_factory=dict)    # never captured: not fetched unless backfill=True (R20)
    departures: list[str] = field(default_factory=list)       # removal candidates (need confirmation, R16)
    blocked: str | None = None                                # whole-host reason to do nothing
    removal_blocked: str | None = None                        # reason removals are held, fetches still fine

    def counts(self) -> dict[str, int]:
        c: dict[str, int] = {}
        for r in self.fetch.values():
            c[r] = c.get(r, 0) + 1
        c["skip"] = len(self.skip)
        c["backfill"] = c.get("backfill", 0) + len(self.backfill)   # fetched (backfill=True) plus held
        c["departures"] = len(self.departures)
        return c


def plan_update(sitemap: dict[str, str | None] | None, state: dict[str, dict], host: str, entries: list[dict],
                *, prev_sitemap: dict[str, str | None] | None = None, departure_cap: float = 0.30,
                adopt_proposed: bool = False, exclude_events: bool = False,
                baseline: datetime | None = None, backfill: bool = False) -> Plan:
    """What an update run should do for one host.

    sitemap       current {url: lastmod}; None or empty means unreadable (R11)
    state         stored {key: {'lastmod': iso|None}} for URLs already scraped (R13)
    prev_sitemap  previous snapshot, used only to find departures (R15)
    backfill      False (default): pages never captured (not stored, lastmod not later than the baseline) are
                  listed in plan.backfill and not fetched; True: fetch them with reason 'backfill' (R20)
    baseline      first run only, when no per-URL lastmod is stored yet: a URL counts as changed when
                  its lastmod is later than this instant (the manifest's generated_at) (R13b)
    """
    plan = Plan()
    seeds = {normalize_key(e["url"]): e["url"] for e in entries}

    if is_path_scoped(entries):                                                   # R10
        in_section = in_scope_total = 0
        for u in (sitemap or {}):
            full = u if "://" in u else f"https://{host}{u}"
            d = evaluate(full, host, entries, adopt_proposed=adopt_proposed, exclude_events=exclude_events)
            if d.in_scope:
                in_scope_total += 1
                if d.reason != "seed":
                    in_section += 1
        if in_section <= SECTION_PAGE_THRESHOLD:       # tiny section (0 to 2 pages on 13 hosts): refetch the seeds
            plan.fetch = {k: "seed" for k in seeds}
            plan.out_of_scope = len(sitemap or {}) - in_scope_total   # report the sitemap pages outside the section
            return plan
        # a real section (mcb has 182 pages): plan it from the sitemap like any other host

    if not sitemap:                                                               # R11
        plan.blocked = "sitemap_unreadable"
        return plan
    if not any(urlsplit(u if "://" in u else f"https://{host}{u}").netloc.lower() == host.lower() for u in sitemap):
        plan.blocked = "sitemap_foreign_host"                                     # R12 host moved
        return plan

    current: dict[str, str | None] = {}
    for u, lm in sitemap.items():
        full = u if "://" in u else f"https://{host}{u}"
        d = evaluate(full, host, entries, adopt_proposed=adopt_proposed, exclude_events=exclude_events)
        if not d.in_scope:
            plan.out_of_scope += 1
            continue
        current[normalize_key(full)] = lm

    for key, lm in current.items():
        st = state.get(key)
        cur0 = parse_lastmod(lm)
        if st is None:
            if baseline is not None and cur0 is not None and cur0 <= baseline:     # R20 never captured
                if backfill:
                    plan.fetch[key] = "backfill"
                else:
                    plan.backfill[key] = "never_captured"
            else:
                plan.fetch[key] = "new"
        elif st.get("fetched") is False:                                            # R20 recorded, still unfetched
            old0 = parse_lastmod(st.get("lastmod"))
            if cur0 is not None and old0 is not None and cur0 != old0:
                plan.fetch[key] = "changed"
            elif backfill:
                plan.fetch[key] = "backfill"
            else:
                plan.backfill[key] = "never_captured"
        elif not lm or cur0 is None:
            plan.fetch[key] = "no_lastmod"                                        # missing or unusable date: refetch (R13)
        else:
            cur, old = cur0, parse_lastmod(st.get("lastmod"))
            if old is None and baseline is not None:                              # R13b bootstrap
                if cur > baseline:
                    plan.fetch[key] = "changed"
                else:
                    plan.skip.append(key)
            elif old is None or cur != old:
                plan.fetch[key] = "changed"                                       # inequality, not just newer
            else:
                plan.skip.append(key)
    for k in seeds:                                                               # R9
        plan.fetch.setdefault(k, "seed")

    if prev_sitemap:                                                              # R15
        prev = {}
        for u in prev_sitemap:
            full = u if "://" in u else f"https://{host}{u}"
            if evaluate(full, host, entries, adopt_proposed=adopt_proposed, exclude_events=exclude_events).in_scope:
                prev[normalize_key(full)] = 1
        gone = sorted(set(prev) - set(current) - set(seeds))   # a seed is always refetched (R9), never a departure
        if prev and len(gone) / len(prev) > departure_cap:
            plan.removal_blocked = f"departure_cap:{len(gone)}/{len(prev)}"
        else:
            plan.departures = gone
    return plan


# --- R16-R17: confirming a departure ----------------------------------------------------------------
def classify_confirmation(status: int | None, location: str | None = None) -> str:
    """What a confirmation fetch of a departed URL means. retire | hold | follow | keep | unknown."""
    if status in (404, 410):
        return "retire"
    if status == 403:
        return "hold"        # likely unpublished; review at first (decision 41)
    if status in (301, 302, 303, 307, 308) and location:
        return "follow"      # retire the old URL once the target is captured
    if status == 200:
        return "keep"        # dropped from the sitemap but still live
    return "unknown"          # 5xx, timeouts: never retire on an error


def host_moved(prev_urls: list[str], new_urls: list[str]) -> bool:
    """R12: the whole URL set changed host (oie -> studyabroad.college)."""
    ph = {urlsplit(u).netloc.lower() for u in prev_urls if "://" in u}
    nh = {urlsplit(u).netloc.lower() for u in new_urls if "://" in u}
    return bool(ph) and bool(nh) and ph.isdisjoint(nh)
