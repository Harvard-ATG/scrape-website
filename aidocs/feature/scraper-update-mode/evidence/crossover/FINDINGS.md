# Corpus crossover — findings & honest interpretation

**Date**: 2026-07-23 | **Scope**: 20 local hosts (old-schema `state.db`, Jun 2026 crawls)
**Raw evidence**: `SUMMARY.md` / `summary.json` (crossover), `ATRISK_SAMPLE.md` / `atrisk_sample.json` (canonicalization)
**Scripts (reproducible)**: `corpus_crossover.py`, `atrisk_canonicalize.py`

**IP caveat (do not overclaim)**: all sitemaps were fetched from a LOCAL/non-AWS IP. Sitemap *existence*, contents, and redirect behavior are IP-independent facts and stand. Production *reachability from AWS ECS* (the Akamai-gated environment) is NOT proven here and remains an open item.

---

## 1. Confirmed corpus-wide (the seas pattern generalizes)

- **Duplication is universal.** Raw `state.db` rows are 1.3–4.2× the distinct-page count on every host (economics 30,490 → 11,874; history 28,172 → 11,566; classics 4.2×). The scary "14k rows vs 5.7k sitemap" gap is mostly http/https + `?page=` + trailing-slash variants, not distinct content. Query-string bloat alone is thousands of rows per big site.
- **The sitemap recovers pages the BFS crawl missed — everywhere.** Sitemap-only-missed is large across the board: hscrb 1,939, **mcb 6,518** (crawl captured 808 distinct pages vs a 7,189-URL sitemap → ~8× coverage gain), seas 1,495. Sitemap-as-source is a net *page* improvement, not a loss, on these hosts.
- **The WordPress discovery gap is real.** `writingprogram.college` resolved only via `robots.txt` → `/wp-sitemap.xml`. Today's `_fetch_sitemap_urls` (which tries only `/sitemap.xml` + `/sitemap_index.xml`) would miss it. → Task 16.

## 2. The "at-risk file" scare is an ARTIFACT, not file loss

The crossover flagged large "at-risk" document counts (economics 606, sociology 614, history 583, statistics 363). The canonicalization sample resolves what they are:

- **100% of at-risk files have a `/search?...&page=N` referrer.** The `found_on LIKE '%/search%'` counts match the at-risk counts exactly (economics 606/606, history 583/583, sociology 613/614, statistics 363/363, linguistics 179/179, english 160/160). These are the **OpenScholar faceted-search trap** pages (`sites/g/files/omnuum...` platform) — the same search-feature pages Jeremy's exclusion work targets. They return 200, but `/search` is never in the sitemap, so a naive one-hop check labels them "orphan."
- **Why this is NOT file loss:** `found_on` records only the *first* referrer. The BFS crawl fell into the `/search?page=N` trap early, so it stamped search pages as the first-referrer for real files (course listings, seminar abstracts, syllabi) that are very likely *also* linked from real content pages in the sitemap. `found_on` (single first-referrer) cannot tell us a file is unreachable — only that BFS reached it via search first.
- **Correction to an earlier read in this analysis:** the raw at-risk counts were briefly framed as likely real file loss. That was an upper bound inflated by (a) a seas-specific junk classifier that matched 0 elsewhere, (b) non-canonical `/node/`, `/index.php/` referrers, and — dominant here — (c) BFS-into-search-trap first-referrer bias. The sample corrects it: at-risk ≠ orphaned.

## 3. What is genuinely unknown

- **True file-loss under strict sitemap-as-source is UNRESOLVED from `found_on` data.** To know whether these files are also linked from real sitemap pages, we'd need a link-graph pass: crawl the sitemap pages, extract their file links, and check whether the at-risk files appear. That's expensive (e.g. 5,946 economics page fetches) and is the only definitive test.
- **Some hosts' sitemaps may be genuinely incomplete** (large `distinct-path` non-crossover, not files): histlit (1,579 distinct-path non-crossover vs an 830-URL sitemap), classics (516), economics (1,317), history (1,795). These need type-sample-testing to confirm whether sitemap-as-source would drop *real pages* there. seas's non-crossover was dupes; these hosts may differ.

## 4. Design implications (feed into the scoping doc)

1. **File carry-forward safety net (Task 17) is REQUIRED, not optional.** Because `found_on` provenance is unreliable (single first-referrer, biased to the search trap), the robust defense is to carry forward known file URLs from the prior `state.db` and re-verify (200 → keep, 404 → drop). This moots the unanswerable "is the referrer good" question.
2. **Locked rule holds:** sitemap-as-source restricts the *page* frontier to sitemap URLs but must keep extracting + downloading file links from crawled pages (do not gate downloads on sitemap membership).
3. **sitemap-as-source is doubly validated:** it eliminates the `/search?page=N` trap (search pages aren't in the sitemap) that caused this entire mess, and recovers thousands of missed real pages.
4. **Sitemap-discovery robustness (Task 16) is a prerequisite** for both sitemap-as-source and `--update`.

## 5. Recommended follow-up (optional, higher cost)

- **Link-graph confirmation** on 1–2 big hosts (economics, sociology): crawl sitemap pages, extract file links, measure how many at-risk files are recovered. Definitively bounds real file loss. Parallelizable; read-only.
- **Type-sample-test the `distinct-path` non-crossover** on histlit/classics to confirm whether their sitemaps omit real pages (a sitemap-as-source loss risk) vs more dupes.
