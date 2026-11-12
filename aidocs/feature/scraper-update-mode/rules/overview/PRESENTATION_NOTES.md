# Presentation notes: how scraping and keeping pages updated get better

Key question: **how should scraping, and keeping pages up to date, get better?**

One-line answer: a full re-scrape stays as the backstop, but it gets cleaner; the sitemap lets us do cheap intermediate
updates between full scrapes; and sites that moved in the Harvard reorganization are recognized instead of being
mistaken for deletions.

All counts below come from the July QA manifests (77 hosts, 143,477 saved pages) and the 2026-10-15 sitemaps, unless
stated. "Saved pages" means pages listed in a manifest; I did not check how many reached the vector store.

---

## 1. A full re-scrape is still needed, and it gets cleaner

PR #10 carries PR #4's two changes. Run over every saved URL with the PR's own code, they remove or merge **73,101 of
143,477 saved pages (50.9%)**:

| What goes | Saved pages | Example (a real saved page) | Biggest host |
| --- | --- | --- | --- |
| `/search?` result pages | 23,896 (16.7%) | `linguistics.fas.harvard.edu/search?page=0` | economics, 6,932 |
| `.ics` calendar feeds | 10,012 (7.0%) | `socialstudies.fas.harvard.edu/node/1127886/event-feed.ics` | economics, 3,869 |
| Twin URLs merged into one (http vs https, trailing slash) | 39,193 (27.3%) | `http://espp.fas.harvard.edu/pages/field-trips` | economics, 8,371 |

Still to come: 19,823 query-string pages (13,464 pagination, 580 filters, 5,779 other) once decision 8's rule is
written, and event pages (about a third of sitemap pages; decision 43). Kept after all of this: 50,553 pages (35.2%).

Visual: the stacked bar "A cleaner full scrape" in the explainer page.

Code (PR #4, `scrape_website/scraper.py`):

```python
_DEFAULT_EXCLUDE_PATTERNS = [
    # ...existing patterns...
    r"/search\?",
    r"\.ics$",
]

# in _normalize_url: one line makes the http and https copies the same key
scheme = "https" if parsed.scheme == "http" else parsed.scheme
```

## 2. The sitemap files give us a map

| Kind | Where | Hosts | Has dates |
| --- | --- | --- | --- |
| XML sitemap | `/sitemap.xml` (often an index) | 79 of 83 | Yes: last-modified per URL |
| Markdown sitemap | `/sitemap-llm` | 52 (Drupal 10) | No: title and link only; also lists files |
| Per-page `.md` copy | page URL plus `.md` | the same 52 | No (response dates are render time) |

Only the XML sitemap can tell us what changed. Example entries:

```xml
<url>
  <loc>https://haa.fas.harvard.edu/contact</loc>
  <lastmod>2025-06-06T21:49:27+00:00</lastmod>
</url>
```

```markdown
- [Contact](https://haa.fas.harvard.edu/contact.md)
```

## 3. Intermediate updates: fetch only what changed

Worked example, `english.fas.harvard.edu` (plan from `validate_hosts.py`):

- 1,643 URLs in the sitemap.
- 1,151 unchanged since the July manifest: skipped.
- 69 to fetch on a first run: 16 new and 53 changed.
- 423 never captured: listed for a separate backfill, not fetched.
- 16 pages changed in the last 7 days. A weekly update fetches about 16 pages, not 1,643.

`economics`: 6,235 URLs; first run 455 pages (297 new, 158 changed); about 39 a week.

Across the 71 hosts that can be planned: 56,992 in-scope pages for a full re-crawl (about 17 to 27 hours serial at 1.1 to
1.7 s per page); 4,339 pages on a first update run (about 1.3 to 2 hours); 341 a week (about 6 to 10 minutes).

Visuals: the update-flow diagram, the "what it saves" log-scale chart, and the one-URL gates diagram.

Code (`rules.py`, `plan_update`, simplified):

```python
cur, old = parse_lastmod(lm), parse_lastmod(st.get("lastmod"))
if old is None or (cur is not None and cur != old):
    plan.fetch[key] = "changed"      # any difference, not only "newer"
else:
    plan.skip.append(key)            # same date: keep what we have
```

Its test (`tests/test_plan.py`):

```python
def test_newer_lastmod_is_changed():
    plan = plan_update(sm(("/a", "2026-03-01")), state(("/a", "2026-01-01")), H, E)
    assert plan.fetch[k("/a")] == "changed"
```

## 4. Sites that moved in the Harvard reorganization

| Old host | New host |
| --- | --- |
| `oie.fas.harvard.edu` | `studyabroad.college.harvard.edu` |
| `summerfunding.college.harvard.edu` | `sfsao.college.harvard.edu` |
| `incomingstudents.college.harvard.edu` | `firstyear.college.harvard.edu` |
| `oaisc.fas.harvard.edu` | `secretary.college.harvard.edu` |

The trap: the old host's sitemap now lists only the new host's URLs (oie: 1,182 of 1,182). Compared with July, that looks
like every page vanished: 1,377 "departures" across the four hosts. Unguarded, a sitemap-driven delete would retire four
sites.

How it is handled:

- Rule R12 spots a sitemap that lists only another host and blocks the host instead of proposing removals.
- `sites.toml` gets the new hostname, with the old entry kept as a commented record.

```python
def host_moved(prev_urls, new_urls):
    ph = {urlsplit(u).netloc.lower() for u in prev_urls if "://" in u}
    nh = {urlsplit(u).netloc.lower() for u in new_urls if "://" in u}
    return bool(ph) and bool(nh) and ph.isdisjoint(nh)
```

```toml
# MOVED (Harvard reorganization): oie.fas.harvard.edu now 301-redirects to studyabroad.college.harvard.edu.
# [[sites]]
# hostname = "oie.fas.harvard.edu"
[[sites]]
resource.name = "Office of International Education"
hostname = "studyabroad.college.harvard.edu"
url = "https://studyabroad.college.harvard.edu/"
```

Not settled yet: what to do with files already ingested under the old hostnames (decision 27), and the scope for
`secretary.college` (decision 30).

## 5. Deleting safely

Today a page is retired when a crawl did not reach it. With the sitemap, a page is a candidate only if it was listed last
time and has now disappeared, and a fetch has to agree:

```python
def classify_confirmation(status, location=None):
    if status in (404, 410): return "retire"
    if status == 403:        return "hold"     # likely unpublished; review first
    if status in (301, 302, 303, 307, 308) and location: return "follow"
    if status == 200:        return "keep"     # dropped from the sitemap but still live
    return "unknown"                           # 5xx, timeouts: never retire on an error
```

Evidence: of 64 sampled departed pages, 41% returned 404, 47% returned 403 (likely unpublished), 11% redirected and 2%
were still live. Visual: the "Deleting a page" diagram.

## 6. What exists and what does not

Exists: PR #4, #7 and #8 work, the taxonomy and 20 rules, a tested reference implementation, and the cross-host report.
Not built: the update flag, a stored last-modified date and saved sitemap snapshot per run, the departures and
confirmation-fetch step, the backfill run, and the monthly full refresh schedule.
