# Do the four "no sitemap" hosts really have none?

Probe run on 2026-07-28 from a local IP. The earlier AWS reachability test (`aidocs/feature/scraper-update-mode/evidence/aws-reachability/`)
found 4 of 83 hosts with no sitemap at the three standard paths. This probe tried much harder before accepting that.

**What was tried on each host:** 46 candidate paths (every common XML sitemap spelling, HTML sitemap pages, `http://` as well as
`https://`), on both the apex name and `www.`; links to a sitemap on the homepage; the HTTP `Link:` header; and RSS or Atom feeds at
`/feed`, `/rss.xml` and `/atom.xml`.

| Host | Homepage | robots.txt | Any sitemap | Feed found |
| --- | --- | --- | --- | --- |
| ces.fas.harvard.edu | 200 | 200 | none | none |
| daviscenter.fas.harvard.edu | 200 | 200 | none | none |
| careerservices.fas.harvard.edu | 200 | 200 | none | `/feed/` (11 dated items) |
| www.hio.harvard.edu | 200 | 200 | none | `/rss.xml` (10 dated items) |

**What it showed.** All four are real negatives: the homepage and robots.txt answer 200, so this is not an Akamai block. Two of
the four expose a feed, which gives a partial freshness signal for recent items only.

**What it fed.** Decision D6 in `aidocs/feature/scraper-update-mode/evidence/cadence-analysis/DESIGN_scrape-cadence-analysis.md`:
these hosts get a fixed monthly full scrape instead of a sitemap-driven cadence, and are flagged "no sitemap" in the report.

**To rerun:** `python -I deep_probe_v2.py` from this folder writes `result_v2.json`. It makes about 100 requests per host.
