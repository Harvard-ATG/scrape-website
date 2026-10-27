# Sitemap-llm versus XML: dates, updates, content and scope

Run 2026-10-21. Offline parts use the 2026-07-28 and 2026-10-15 sitemap snapshots and the cached QA manifests (2026-07-22).
Live part: 20 pages from 4 Drupal 10 hosts (english.fas, sociology.fas, www.physics, philosophy.fas), HTML and `.md` copy of each
(40 requests, all 200), fetched from a local IP, two seconds apart. Scripts: `date_and_scope_analysis.py`, `sample20_fetch.py`,
`sample20_analyze.py`; data: `samples/sample20/`, `samples/sample20_analysis.json`.

## 1. Short answers

| Question | Answer |
| --- | --- |
| Can `/sitemap-llm` replace the XML sitemap? | **Not for change detection.** The list has no dates. Page `.md` copies carry a date only on dated page types (news, events, blog), as written text, and it is the publication or event date, not an edit time. File cards carry a date-only `Date` (MM/DD/YYYY). Each needs one request to read. Use XML for `lastmod`. |
| Do the card dates match the XML? | **Mostly: 14 of 19 cards (74%) on the same UTC date.** The 5 that differ are cards whose original date is years older than an XML `lastmod` that a bulk re-save moved (see section 4b). |
| Keep XML's date granularity? | **Yes.** 99.0% of XML entries have a timestamp to the second. Store the exact value per URL and refetch on any difference. |
| Does the website itself carry a finer date? | **Not in these 20 pages.** No modified-time meta tag, no JSON-LD, no visible "last updated". HTTP `Last-Modified` and `ETag` are render or cache times. |
| Does the date rounding in the earlier analyses matter? | **Not for the numbers reported** (7 and 30 day windows). It would for same-day questions. Details in section 3. |
| Are things listed by the sitemaps excluded by our regular pull? | **Yes, mostly by path scope.** 25,042 of the XML entries are out of scope, 24,477 of them because the host is path-scoped. Section 5. |
| Does our regular pull get things the sitemap does not list? | **Yes, a lot.** 56% of the saved pages are not in the XML sitemap: mostly query-string and `.ics` pages, plus 16,434 in-scope listing and legacy pages. Section 6. |

## 2. Date precision of the XML sitemap (2026-10-15 snapshot)

| Form | Entries | Share |
| --- | --- | --- |
| Timestamp to the second, with offset | 82,260 | 99.0% |
| Date only (`2026-10-15`) | 838 | 1.0% (all on two hosts: `www.gov` 705, `lpce` 133) |
| No `lastmod` | 286 | 0.3% |

Other fields in the XML entries: `priority` on most, `changefreq` rarely (on the `haa` sample only the homepage). Our parsers keep
`loc` and `lastmod` only.

Bulk edits: `iop.harvard.edu` has 2,910 of 7,016 URLs with one identical timestamp (2026-07-06T14:42:30-04:00), `music.fas` 138 of 480,
`lpce` 53 of 133 on one date. Hosts with a bulk save look "changed" together; the hash check at ingest absorbs the cost.

## 3. Morning edit, afternoon edit

When are edits made? From the 1,865 timestamped `lastmod` values in the 30 days before 2026-10-15 (America/New_York):

| | Share |
| --- | --- |
| At or after 05:00 ET | 99.7% |
| Between 08:00 and 18:00 ET | 93.2% |
| Peak hours | 11:00 (274), 14:00 (247), 15:00 (230) |

This only shows each page's last edit, so it says when edits tend to happen, not how often one page is edited twice in a day.

What each design catches:

| Compare by | Edit at 09:00 and again at 14:00, scrape at 05:00 next day | Edit at 03:00, scrape at 05:00, edit at 14:00 |
| --- | --- | --- |
| Full timestamp, refetch on any difference (R13, R14) | caught (both edits are before the scrape; the scrape sees the final state) | caught (14:00 differs from the stored 03:00) |
| Date only | caught | **missed** (both are the same date) |

So the afternoon edit is only lost when a scrape falls between two edits on the same date. With a 05:00 ET schedule that is
about 0.3% of last-edits (those before 05:00). A mid-day schedule would raise that sharply. Full timestamps remove the problem.

Where full timestamps are not available:
- `www.gov` (705) and `lpce` (133) give dates only. A second same-day edit is invisible. Rule to add: for a page whose stored
  `lastmod` is a date, refetch it again the next run when that date equals the date of the last scrape.
- The file card's `Date: 09/05/2018` is date only; the XML `lastmod` of the card's landing page has the time (section 4b).

Earlier analyses revisited:

| Earlier result | Rounding to a date? | Still valid? |
| --- | --- | --- |
| Cadence tool, changed in last 7 and 30 days (`dateparse.parse_iso_date` floors to a date) | yes | Yes: with windows starting at midnight UTC, timestamp and date floor give identical counts (1d 229, 2d 312, 7d 471, 30d 2,039). Do not reuse the floor for planning or for sub-day questions. |
| `rules.py` plan (R13, R14) | no, full UTC timestamps | Yes. My fix reads a bare date as the end of that day for the first-run baseline. |
| First-run counts (4,339 pages) | baseline is the manifest `generated_at` | Pages edited on the baseline day are counted by timestamp; fine. |
| Jul to Oct snapshots | | 79,206 URLs with dates in both, 2,548 changed (3.2%). No change fell on one calendar day, as expected from snapshots three months apart; they cannot show intra-day behavior. |

## 4. Dates on the website itself (20 sampled pages)

| Source | What we found |
| --- | --- |
| XML `lastmod` | seconds precision; the only machine-readable "changed" time |
| HTML meta tags (`article:modified_time`, `og:updated_time`, `date`, `dcterms`) | none on any of the 20 |
| JSON-LD (`dateModified`, `datePublished`) | none |
| Visible "last updated" text | none |
| `<time datetime>` | 3 news pages: `2023-04-01T12:00:00Z`, `2022-12-08T12:00:00Z`, `2014-02-28T12:00:00Z`; a publication date with a placeholder noon time, differing from the XML `lastmod` (2023-04-03 on the first) |
| HTML `Last-Modified` header | render or cache time (all 2026-10-20 or 21), not an edit time |
| `.md` `Last-Modified` header | the minute of the fetch |
| `ETag` | the render time as epoch seconds |
| Served `.md` of a page | a written date (`April 01, 2023`) on news, events and blog pages: the publication or event date; none on people, course, FAQ, contact or about pages (section 4c) |
| File card body (`/resource/<slug>.md`) | `Date: MM/DD/YYYY`, date only; matches the XML `lastmod` date on 14 of 19 cards (section 4b) |
| Our front matter `date` | a heuristic guess (the `haa` page said `2026-01-01`) |

So there is no finer date on the page than the XML `lastmod`. Sample: 4 Drupal 10 hosts only.

## 4b. File cards: the Date on the card against the XML `lastmod`

Cards are the `.md` pages that `/sitemap-llm` links to for files (`/resource/<slug>.md`); the body gives size, format, date and the
download path. Checked on 2026-10-21: 20 random in-scope cards from 5 hosts (4 each), one request each; the XML side is the 2026-10-15
snapshot. Data: `samples/card_date_check.json`, script `card_date_check.py`.

| Result | Cards |
| --- | --- |
| Card has a `Date` | 19 of 20 (one card had no Date, size or format) |
| Card date equals the XML `lastmod` date (UTC) | **14 of 19** |
| Equals it in America/New_York | 13 of 19 (one `lastmod` is 01:58 UTC, still the previous evening in New York; the card uses the UTC date) |
| Card date older than the XML `lastmod` | 5 of 19 |

The 5 that differ: `history` card 2014-12-05 against `lastmod` 2024-11-14T10:22:57; two `sociology` cards (2013-08-19 and 2013-09-24)
against the same `lastmod` 2024-06-27T12:04:38; two `nelc` cards (2014-09-09 and 2015-07-20) against the same `lastmod`
2024-11-15T09:00:29. Identical timestamps across cards point to a bulk re-save of the pages in 2024. So:

- The card `Date` looks like the file's own date and stays put when the page is re-saved.
- The XML `lastmod` is the page's changed time and moves on any re-save, including bulk ones.
- Where both agree (14 of 19) the card adds nothing but the date-only form. Where they differ, the card is the steadier "file date" and
  the XML is the safer trigger (a re-saved page is refetched, which is wasteful but not lossy).
- Open: whether replacing a PDF changes the card `Date`; not tested.
- Cost: reading the card date for 9,624 in-scope file entries is 9,624 requests, against zero for the XML, which already lists all
  10,775 file landing pages with a full timestamp.

Card also gives what XML does not: size, format and the download path (needed to link a card to the file the crawl saved).

## 4c. Dates on page cards (the `.md` copy of a page)

Two checks. The first 20 pages (4 hosts, sampled by recency) were scanned for dates in every written form; only the 3 news pages had one.
Then 19 more `.md` copies, sampled by page type: 5 news, 5 events, 5 publications, 4 blog (`samples/page_card_date_check.json`,
`page_card_date_check.py`, 19 requests on 2026-10-21).

| Page type | Cards with a date | What the date is | XML `lastmod` against it |
| --- | --- | --- | --- |
| News (5, plus 3 earlier) | 5 of 5 (3 of 3) | publication date, written out (`February 08, 2024`) | same day on 1 of 5; later on 4 (7 to 55 days) |
| Events (5) | 5 of 5 | the event date (`March 24, 2026`) | earlier than the event on 4 (event is in the future of the last edit); later on 1 |
| Blog (4) | 4 of 4 | publication date | same day on 3 of 4; 2,939 days later on 1 |
| People, courses, FAQ, contact, about (17 earlier) | 0 of 17 | none | |
| Publications (5) | 0: all returned **403** | the response says `Language 'en' is not enabled for Markdownify for entity type 'bibcite_reference'`; the HTML page loads (200) with no date tag | |

What this says:
- Dated page types do carry a date in the markdown copy. It is a day, in text, with no time.
- It is a **created or event date**, not a modification date. When a post is never edited it equals the XML `lastmod` date (blog 3 of
  4, one news page); when it is edited later the card date stays and the XML `lastmod` moves on. For events it is when the event
  happens, which can be after the last edit.
- So the card date cannot replace the XML `lastmod` to detect an edit to a published page.
- Most page types in the sample have no date at all.
- Publication entries have no markdown copy on the five hosts tried (403). `haa` lists 3 publication pages in its markdown sitemap, so a
  listed page can lack a usable `.md`; the sitemap-llm is not a guarantee that the copy is served.

## 4d. A date hunt on one site (haa.fas.harvard.edu)

Goal: check that no date source is being overlooked. Offline: the whole `/sitemap-llm` (2,785 lines, 405 KB) and the full HTML of one page
(`/about`). Live, 8 requests on 2026-10-21: the sitemap-llm, the page, its `.md`, and five standard Drupal endpoints. Data:
`samples/haa-date-hunt/` (bodies and all response headers), `samples/haa-about/`.

**The sitemap-llm file itself**
- Every one of the 2,785 lines is a list item `- [title](url.md)`. No header, no front matter, no comments, no second column, no query
  strings, no fragments. All links are `.md` URLs on the same host.
- Date-like text appears only inside editors' titles, with no consistent format: `[4/22/2020] ...`, `Spring 2020 grading update: 4/10/2020`
  (9 lines), `... September 10–December 13, 2018` (5), `... June 2018 issue` (5), 4-digit years in 194 lines (many are ranges
  such as `2015-16`). Some slugs embed dates (`spring-2020-grading-update-4102020`, `may-5-2020-...`). None of this is machine-readable metadata
  and none says when the page changed.
- Response headers: no `Last-Modified`, no `ETag`; `cache-control: private, must-revalidate, max-age=300`; `x-drupal-dynamic-cache: UNCACHEABLE`.
  Only `date` (the response time).

**One page (`/about`)**
- `<head>`: `canonical`, and `<link rel="alternate" type="text/markdown" href=".../about.md">`; the same alternate is in an HTTP `Link:` header.
  The only meta tags are `og:type`, `og:url`, `og:title`, `twitter:card`, `Generator`, viewport. No `article:modified_time`, no `og:updated_time`,
  no JSON-LD, no `<time>`, no `data-*` date attributes, no HTML comments.
- `drupalSettings` (the page's inline JSON): `path.currentPath` = `node/1074311` (the node id), `nodeBundle` = `hwp_page`, `nodeTitle`,
  `baseFullUrl`, language, an `extlink` config block and a user permissions hash. No timestamps.
- Headers: `Last-Modified` 2026-10-20 17:36:07 GMT with `ETag "1792517767"`, which is that same instant as epoch seconds, and `x-age: 65928`
  (about 18 hours): this is when the cached copy was built, not when the page was edited. The `.md` has `Last-Modified` and `ETag` equal to the
  minute of the request.

**Standard Drupal endpoints tried (not advertised by the page)**

| Path | Result |
| --- | --- |
| `/jsonapi` | 404 (JSON:API not enabled) |
| `/node/1074311?_format=json` | 406: "only supports the HTML format" |
| `/feed` | 404 |
| `/rss.xml` | **200**, a feed of front-page-promoted nodes only: 2 items, each with `pubDate` and `<time datetime="2025-07-24T18:50:32+00:00">` (the authored date, full timestamp, plus the node id in `guid`) |
| `/sitemap.xml` | 200, a sitemap index whose child entries carry `lastmod` (the XML source we already use) |

**Every date source found on this site**

| Source | Date | Precision | Meaning | Covers |
| --- | --- | --- | --- | --- |
| XML sitemap `<lastmod>` | yes | seconds | node changed time | every listed URL |
| XML sitemap index child `<lastmod>` | yes | seconds | when that sitemap file changed | per child file |
| `/rss.xml` `pubDate` | yes | seconds | authored (created) time | only promoted nodes (2 here) |
| Written date in page text, `<time datetime>` | on news, events, blog | day (noon placeholder in the tag) | publication or event date | dated page types |
| File card `Date` | yes | day | the file's own date | file cards |
| Typed dates in titles and slugs | sometimes | day or month | whatever the editor typed | scattered |
| HTTP `Last-Modified`, `ETag`, `Date` | yes | seconds | cache or render time | all responses, none are edit times |
| `/sitemap-llm` list | **none** | | | |
| Page meta tags, JSON-LD, drupalSettings | **none** | | | |

Conclusion for this site: the XML `<lastmod>` is the only source of when a page changed. Nothing in the sitemap-llm, in the page markup or in
the page's inline settings carries a modification date.

Not covered: one site and one page; custom feeds a site may define (for example a `/news/rss.xml` view) were not probed; other Drupal
back-end routes would need credentials.

## 5. What the sitemaps list that our scope rules exclude

XML and sitemap-llm list the same pages within a few (earlier finding), so this applies to both. Of the XML entries across the
hosts in `sites.toml`, run through `rules.evaluate`:

| Reason | Entries |
| --- | --- |
| outside the seed path (`scope_to_path`) | 24,477 |
| include patterns do not match | 472 |
| default excludes | 56 |
| another host | 38 |

Largest: `mcb` 7,144, `iop` 7,015, `haa` 2,813, `college` 2,494, `medieval` 1,555, `histsci` 886, `mbb` 829,
`archaeology` 520. By kind: 14,354 pages, 9,307 event pages, 751 file landing pages, 598 tag archives. The 751 file entries of
sitemap-llm that are out of scope are all on path-scoped hosts or dropped by include patterns (earlier result).

## 6. What our regular pull saves that the sitemap does not list

Of 131,491 webpages in the July QA manifests (hosts with a snapshot), 73,854 (56%) are not in the XML sitemap:

| Kind | Pages |
| --- | --- |
| query-string pages (`?page=`, search) | 46,755 |
| `.ics` calendar feeds | 9,724 |
| plain pages | 16,715 (16,434 in scope) |
| event pages, archive listings, tags, nodes, resource pages | about 660 |

After PR #4 (search and `.ics` excludes, http to https) most of the first two groups disappear. The 16,434 in-scope plain pages
are mostly listing and category pages (`/people` 1,666, `/news` 587, `/blog` 478, `/about` 453, `/core` 325, `/writer` 300,
`/collections` 288, `/class`, `/directory`) and some legacy paths. Largest hosts: economics 17,745, history 15,413, chemistry 6,630,
seas 5,959, histlit 4,123, tdm 3,839, sociology 3,336, ofa 2,000. If a sitemap replaced the crawl as the page source these would
be lost; listing pages are what the monthly full run (R19) is for. This was not checked page by page.

## 7. Served markdown against our extraction (20 pages)

| Result | Pages |
| --- | --- |
| Both usable | 16 |
| Our extraction returned the **site navigation menu** instead of the page ("Skip to main content ... Menu ...") | 4: `english` Contact, `physics` two people pages and News and Events |
| Served `.md` nearly empty (under 10 words) | 2: `english` Contact, `physics` News and Events |
| Words in the 20 pages: served md / ours | 3,149 / 3,482 |

- **Where the served copy is better:** it keeps structured fields as text: taxonomy lists (Countries, Geographic Areas, Research
  Clusters, Graduate Students by Academic Advisor and Cohort), Role, and labelled contact details (email, phone, location). Our
  extraction drops these on the people pages (31 to 35 words missing on the sociology people pages; 16 people cards on `haa`).
- **Where ours is better:** body text on pages whose content is assembled by blocks or views (served `.md` empty on two).
- **Where ours fails badly:** it returns navigation menu text as the page. That is worse than no file, because it gets ingested.
  Cause not checked (`favor_recall=True` is the likely lever; unverified).
- **Where served `.md` is noisy:** share links (facebook, linkedin, twitter), icon names (`laptop_windows`, `location_on`), image links
  and hundreds of blank lines.

Neither source wins. The two fail on different pages, so comparing them is a check on extraction quality, and the pages where
they disagree most are the ones to look at.

## 8. Recommendations

1. **XML for dates, always.** Store each URL's exact `lastmod` string and refetch on any difference. Do not floor to a date.
2. **Date-only hosts** (`www.gov`, `lpce`): refetch pages whose stored `lastmod` date equals the last scrape date.
3. **Sitemap-llm as a second list**, for files and the `.md` copies, with scope rules applied; it is not a replacement. It needs a
   `sites.toml` sitemap-kind field and a parser (not built).
4. **Guard against navigation-only extraction**: flag any extracted page that starts with the site's skip-link and menu, or whose
   text is mostly menu items, instead of ingesting it. This is a cheap check and the 4 of 20 rate is high enough to matter.
5. **Compare both copies on a larger sample** before choosing a content source; use disagreement to find bad extractions.

## 8b. What the platform says (HarvardSites documentation)

Source: https://drupal.harvardsites.harvard.edu/resource/optimizing-your-site-search-engines-and-artificial-intelligence
(read 2026-10-21; plain fetch returns 403, browser-impersonating fetch returns 200; copy in `samples/harvardsites-optimizing/`).
This is the HarvardSites platform's own guidance for site owners on search engines and AI. Relevant statements:

- "HarvardSites Drupal pages now provide a markdown version of their content that can be accessed by appending `.md` to any page URL.
  Sites also include an AI-focused sitemap available at `/sitemap-llm`, making it easier for AI tools and large language models to
  discover and process site content."
- Markdown is described as "a simpler text version of a page that keeps the important structure, such as headings, links, lists, and body
  content, while leaving out much of the visual design."
- The page tells site owners to write for answer engines: question-style headings, a short answer first (under 40 words), numbered steps,
  tables, descriptive links, titles under 60 characters, a meta description of 150 to 160 characters, and to "keep content fresh". It says
  nothing about modification dates, `lastmod`, or any freshness signal for crawlers.

What this means here:
- The `.md` copies and `/sitemap-llm` are a **documented platform feature**, not an accident. That makes them a stable interface on the 52
  Drupal 10 hosts, though "any page URL" is not exact: 5 of 5 publication pages returned 403 (section 4c).
- The platform names AI tools as the audience, and the page's recommended content patterns (question headings, short answers) suit
  retrieval; headings are kept by both the `.md` copy and our extraction.
- This page is itself a `/resource/` page, but it is an **article** (a body and related resources), not a file card with size, format and a
  download link. So `/resource/` entries are not always files; earlier counts of "file entries" (10,375 in sitemap-llm, 10,775 in XML)
  likely include articles like this one. The 20 random cards checked in section 4b were 19 files and 1 image; how many resources are
  articles was not measured.
- `drupal.harvardsites.harvard.edu` is not in `sites.toml`. It is the platform's own help site; whether it belongs in the knowledge base is
  a separate question.

## 8c. Does trafilatura capture change dates? (trafilatura 2.0.0, htmldate 1.9.4)

Evidence: installed source, the upstream docs, and a run over the 38 saved pages (`trafilatura_dates_check.py`, `samples/trafilatura_dates.json`).

- **Defaults.** `trafilatura.settings.set_date_params` sets `original_date: True`, `max_date` today, and extensive search on. Docs
  ([usage-python](https://trafilatura.readthedocs.io/en/latest/usage-python.html)): "By default, focus is on original dates"; `original_date` is
  "to look for the original publication date". Output is `%Y-%m-%d`. The page does not mention modification dates.
- **htmldate** ([options](https://htmldate.readthedocs.io/en/latest/options.html)) has `original_date`; with it off it prefers the most recent
  date. Its source reads `article:modified_time`, `dateModified`, `og:updated_time`, `lastmod`, `last-modified`. It returns a day, not a time.
- **Our call** is `trafilatura.extract_metadata(html, default_url=url)` with no date configuration, so we get the defaults above.

Result on 38 saved pages (20 sample20, 5 each of news, events, publications, 4 blog; the history news page that returned 404 is excluded):

| Measure | Result |
| --- | --- |
| Default `date` returned | 38 of 38 |
| Pages that show a date (13): returned date equals the shown date | 13 of 13 |
| Pages with no shown date: `YYYY-01-01` | 20 (a year-only guess, for example `2026-01-01` on every english page) |
| Equals the XML `lastmod` date | 3 of 38 |
| With `original_date=False` and a time format | values are `...T00:00:00`: no time of day on any page |
| htmldate strict (`extensive_search=False`, structured sources only) | returns a date on 16 of 38 (blog 4, events 5, news 4, 3 others); each is a publication or event date; equals the XML `lastmod` day on 3 |

So trafilatura captures the date a page displays (publication or event date), at day precision, and guesses a year when none is shown. It does not
capture change dates here, because by default it prefers the original date and because the pages expose no modification signal (section 4d).
Our front matter `date` is therefore unreliable as a change date.

## 8d. `trafilatura.sitemaps.sitemap_search` (2.0.0) against our `_fetch_sitemap_urls`

From the installed source (the upstream docs page [crawls](https://trafilatura.readthedocs.io/en/latest/crawls.html) does not document the function's
arguments or return value; it only mentions the command-line `--sitemap` and `--explore`).

| | `sitemap_search` | ours (`scraper.py:228`) |
| --- | --- | --- |
| Returns | sorted unique list of links only; the source has no `lastmod`, `changefreq` or `priority` | list of URLs, no dates |
| Finds sitemaps | `robots.txt` `Sitemap:` lines, else `sitemap.xml`, `sitemap.xml.gz`, `sitemap`, `sitemap_index.xml`, `sitemap_news.xml` | `robots.txt`, then `/sitemap.xml`, `/sitemap_index.xml`, `/wp-sitemap.xml` |
| Nesting | queue of sitemaps up to `max_sitemaps=10000` | one level |
| Limits | `MAX_LINKS` 1,000,000 | 5,000 |
| Formats | XML, plain-text URL lists, `.gz` (the source handles gz) | XML only |
| Parsing | regex `<loc>...</loc>` (handles CDATA); no XML parser, so no entity-expansion risk | `ET.fromstring`, no DOCTYPE guard |
| Extras | `target_lang` (hreflang filter), `external`, a path filter when given a non-homepage URL, `sleep_time=2.0` | none |
| Fetching | its own downloader (`fetch_url`) and an `is_live_page` check; not pluggable | our tier-escalating fetch (handles Akamai 403s) |

What it adds: nested and gz and text sitemaps, a path filter, language filter, a regex parse with no XML-parser risk. What it lacks: dates, and our WAF
escalation. It would not solve change detection and would hit 403s on Akamai hosts unless its fetching were replaced.

## 9. Not covered

- Only date shapes with a month name, ISO or MM/DD/YYYY were scanned in the markdown; other layouts were not.
- Whether editing a published page changes the date written on it was not tested.
- Only 4 hosts, all Drupal 10, all fetched from a local IP, not AWS.
- Last-edit times only; no intra-day history exists in the snapshots.
- The 16,434 unlisted pages were grouped by path, not opened.
- Why our extractor returned navigation on 4 pages was not diagnosed.
