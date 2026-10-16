# AWS sitemap-reachability test — results
**Date**: 2026-07-23 | **Where**: ECS `atg-prod-default`, task def `atg-apo-mcp-qa-task-definition:12` (branch image w/ tiered fetch), private subnets, `assignPublicIp=DISABLED` → egress via the **Akamai-gated NAT IP**. Task `065e34b7bd3e463ab15737c245c11303`, exit 0.
**Method**: for each sites.toml host, discover sitemap (robots.txt `Sitemap:` → `/sitemap.xml` → `/sitemap_index.xml` → `/wp-sitemap.xml`), then fetch two ways from the NAT IP — **Tier 1** (plain urllib, naive client) and **Tier 2** (curl_cffi `impersonate='chrome'`). Results written to `s3://atg-apo-mcp-qa-scrape/_sitemap_reachability/result.json` (container logs are Splunk-only).
**Scripts/data (reproducible)**: `sitemap_reachability_probe.py`, `result.json`.
## Headline
- **Total hosts**: 83
- **Reachable sitemap (200)**: 79
- **Passed naive Tier 1 (200)**: 28
- **Tier 1 = 403, rescued by Tier 2 (200)**: 51
- **No sitemap (404 at both tiers, all paths)**: 4

**The Akamai gate is live from AWS** — 51 hosts 403 a naive client. **Tier 2 curl_cffi chrome impersonation defeats it on 51/51** → every gated sitemap returns 200 with valid content. Tier 3 (Playwright) NOT needed to fetch sitemaps. The 4 'unreachable' are genuine no-sitemap hosts (404 at BOTH tiers on every candidate path), not blocks.

## Design consequence (LOCKED)
`_fetch_sitemap_urls` (scraper.py:217-220) fetches via the plain `aiohttp.ClientSession` — **Tier 1 only, no escalation**. From AWS it 403s on these 51 hosts and silently returns `[]`. → **Today's sitemap-seeding is a no-op on production AWS for every Akamai-gated host** (likely why seas, which HAS a sitemap, still crawls as unbounded BFS from AWS). **Requirement**: sitemap discovery/fetch (`_fetch_sitemap_urls`, Task 16 robots.txt+wp-sitemap discovery, and the future `--update` `<lastmod>` fetch) MUST route through the tier-escalating fetcher, not a naive aiohttp session — otherwise sitemap-as-source and `--update` are dead-on-arrival in production.

## Tier-2-rescued hosts (Tier 1 = 403 → Tier 2 = 200) — 51
| Host | T1 | T2 | locs | index? |
|---|---|---|---:|---|
| aaas.fas.harvard.edu | 403 | 200 | 1403 | False |
| afvs.fas.harvard.edu | 403 | 200 | 805 | False |
| anthropology.fas.harvard.edu | 403 | 200 | 831 | False |
| archaeology.harvard.edu | 403 | 200 | 521 | False |
| astronomy.fas.harvard.edu | 403 | 200 | 1237 | False |
| celtic.fas.harvard.edu | 403 | 200 | 177 | False |
| classics.fas.harvard.edu | 403 | 200 | 549 | False |
| dso.college.harvard.edu | 403 | 200 | 818 | False |
| eas.fas.harvard.edu | 403 | 200 | 93 | False |
| edsecondary.fas.harvard.edu | 403 | 200 | 381 | False |
| english.fas.harvard.edu | 403 | 200 | 1635 | False |
| espp.fas.harvard.edu | 403 | 200 | 458 | False |
| folkmyth.fas.harvard.edu | 403 | 200 | 151 | False |
| german.fas.harvard.edu | 403 | 200 | 433 | False |
| ghhp.fas.harvard.edu | 403 | 200 | 474 | False |
| haa.fas.harvard.edu | 403 | 200 | 2 | True |
| handbook.college.harvard.edu | 403 | 200 | 3 | False |
| heb.fas.harvard.edu | 403 | 200 | 446 | False |
| histlit.fas.harvard.edu | 403 | 200 | 830 | False |
| history.fas.harvard.edu | 403 | 200 | 3 | True |
| histsci.fas.harvard.edu | 403 | 200 | 865 | False |
| incomingstudents.college.harvard.edu | 403 | 200 | 30 | False |
| language.fas.harvard.edu | 403 | 200 | 25 | False |
| linguistics.fas.harvard.edu | 403 | 200 | 1833 | False |
| mbb.harvard.edu | 403 | 200 | 986 | False |
| medieval.fas.harvard.edu | 403 | 200 | 1523 | False |
| msi.harvard.edu | 403 | 200 | 105 | False |
| music.fas.harvard.edu | 403 | 200 | 463 | False |
| nelc.fas.harvard.edu | 403 | 200 | 1687 | False |
| ofa.fas.harvard.edu | 403 | 200 | 1081 | False |
| oie.fas.harvard.edu | 403 | 200 | 1179 | False |
| philosophy.fas.harvard.edu | 403 | 200 | 976 | False |
| publicservice.fas.harvard.edu | 403 | 200 | 939 | False |
| registrar.fas.harvard.edu | 403 | 200 | 881 | False |
| rll.fas.harvard.edu | 403 | 200 | 441 | False |
| scienceeducation.fas.harvard.edu | 403 | 200 | 2 | True |
| seo.harvard.edu | 403 | 200 | 184 | False |
| slavic.fas.harvard.edu | 403 | 200 | 1079 | False |
| socialstudies.fas.harvard.edu | 403 | 200 | 269 | False |
| sociology.fas.harvard.edu | 403 | 200 | 2 | True |
| specialconcentrations.fas.harvard.edu | 403 | 200 | 184 | False |
| statistics.fas.harvard.edu | 403 | 200 | 2 | True |
| summerfunding.college.harvard.edu | 403 | 200 | 131 | False |
| tdm.fas.harvard.edu | 403 | 200 | 1454 | False |
| undergrad.psychology.fas.harvard.edu | 403 | 200 | 1755 | False |
| uraf.harvard.edu | 403 | 200 | 436 | False |
| wgs.fas.harvard.edu | 403 | 200 | 1038 | False |
| writingcenter.fas.harvard.edu | 403 | 200 | 95 | False |
| www.chemistry.harvard.edu | 403 | 200 | 2 | True |
| www.economics.harvard.edu | 403 | 200 | 3 | True |
| www.physics.harvard.edu | 403 | 200 | 840 | False |

## Passed naive Tier 1 — 28
| Host | T1 | locs | index? |
|---|---|---:|---|
| academicresourcecenter.harvard.edu | 200 | 7 | True |
| advising.college.harvard.edu | 200 | 6 | True |
| college.harvard.edu | 200 | 2 | True |
| collegehousing.fas.harvard.edu | 200 | 4 | True |
| complit.fas.harvard.edu | 200 | 29 | True |
| courses.my.harvard.edu | 200 | 0 | False |
| csadvising.seas.harvard.edu | 200 | 38 | False |
| dao.fas.harvard.edu | 200 | 6 | True |
| emr.fas.harvard.edu | 200 | 7 | True |
| engagedscholarship.fas.harvard.edu | 200 | 5 | True |
| eps.harvard.edu | 200 | 13 | True |
| firstyearseminarprogram.college.harvard.edu | 200 | 6 | True |
| gened.college.harvard.edu | 200 | 4 | True |
| hscrb.harvard.edu | 200 | 13 | True |
| iop.harvard.edu | 200 | 4 | True |
| library.harvard.edu | 200 | 258 | False |
| lpce.college.harvard.edu | 200 | 8 | True |
| oaisc.fas.harvard.edu | 200 | 5 | True |
| oue.fas.harvard.edu | 200 | 8 | True |
| placement.college.harvard.edu | 200 | 3 | True |
| qrd.college.harvard.edu | 200 | 4 | True |
| sas.fas.harvard.edu | 200 | 6 | True |
| seas.harvard.edu | 200 | 3 | True |
| studyofreligion.fas.harvard.edu | 200 | 9 | True |
| writingprogram.college.harvard.edu | 200 | 5 | True |
| www.gov.harvard.edu | 200 | 16 | True |
| www.math.harvard.edu | 200 | 15 | True |
| www.mcb.harvard.edu | 200 | 14 | True |

## No sitemap (genuine 404, not a block) — 4
- `careerservices.fas.harvard.edu` — all candidates 404 (t1=404, t2=404)
- `ces.fas.harvard.edu` — all candidates 404 (t1=404, t2=404)
- `daviscenter.fas.harvard.edu` — all candidates 404 (t1=404, t2=404)
- `www.hio.harvard.edu` — all candidates 404 (t1=404, t2=404)

**Note on low `loc` counts**: hosts showing 2–5 locs (economics, history, sociology, statistics, seas, chemistry, haa, and the wp-sitemap WordPress hosts) are **sitemap indexes** (`index?=True`) — the `<loc>` entries point to child sitemaps holding the real URLs (e.g. economics's child sitemaps sum to ~5,946). Not thin sitemaps.
