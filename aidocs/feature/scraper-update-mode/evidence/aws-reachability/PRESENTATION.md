---
marp: true
theme: default
paginate: true
size: 16:9
header: "AWS Sitemap Reachability — Scraper Scope-Limiting Work Stream"
footer: "Harvard ATG · 2026-07-23"
style: |
  section { font-size: 24px; }
  h1 { color: #A51C30; }
  h2 { color: #A51C30; }
  table { font-size: 22px; }
  th { background: #A51C30; color: #fff; }
  strong { color: #A51C30; }
  section.lead h1 { font-size: 44px; }
  section.lead { text-align: center; }
---

<!-- _class: lead -->

# Can the scraper reach the sitemaps from AWS?

### Testing sitemap reachability through the real Akamai-gated NAT

**Result: Yes — with Tier 2. And we found a production bug.**

Harvard ATG · Scraper scope-limiting & `--update` work stream · 2026-07-23

---

## Why this test existed

- The `--update` and **sitemap-as-source** designs both depend on one assumption: **the scraper can actually fetch the sitemaps in production.**
- All prior sitemap evidence was gathered from a **local / non-AWS IP.**
- But Akamai's bot gate is **harshest on AWS IP ranges** — the very environment that produces the FAS 403s. Existence facts are IP-independent; **reachability is not.**
- **Open question:** does a sitemap that returns 200 locally also return 200 from the production NAT? Unknown → blocking risk for the whole design.

---

## The test

- Fired an **ephemeral ECS task** in `atg-prod-default` using the branch image (`atg-apo-mcp-qa-task-definition:12`, has the tiered fetcher).
- **Private subnets, `assignPublicIp=DISABLED`** → egress via the **same Akamai-gated NAT IP** the real scraper uses. This is the authoritative path.
- For all **83 sites.toml hosts**: discover the sitemap (`robots.txt` → `/sitemap.xml` → `/sitemap_index.xml` → `/wp-sitemap.xml`), then fetch it **two ways**:
  - **Tier 1** — plain client (naive)
  - **Tier 2** — `curl_cffi` Chrome impersonation
- Container logs go to **Splunk (unreadable from here)** → probe wrote results to **S3**, pulled back for analysis.

---

## Headline result

| Outcome | Hosts |
|---|---:|
| **Sitemap reachable (200)** | **79 / 83** |
| Passed naive **Tier 1** (200) | 28 |
| **Tier 1 = 403 → Tier 2 = 200** (curl_cffi rescued) | **51** |
| **No sitemap** (404 at *both* tiers, every path) | 4 |

> **51 of 83 hosts block a naive client from AWS. Tier 2 recovers every one of them.**

---

## What it proves

1. **The Akamai gate is live from AWS.** 51 hosts 403 a naive client through the production NAT — the FAS-403 gate, reproduced (not just inferred).
2. **Tier 2 `curl_cffi` defeats it 51 / 51.** Every gated sitemap returns 200 with valid XML. **Tier 3 / Playwright is *not* needed for sitemaps.**
3. **sitemap-as-source and `--update` are viable in production** — provided the fetch escalates to Tier 2.
4. **The 4 "unreachable" hosts are not blocked** — `ces`, `daviscenter`, `careerservices`, `www.hio` return 404 at *both* tiers on every path = genuinely no sitemap. They need the "degrade to discover-new" fallback.

---

## The bonus finding — a real production bug

**`_fetch_sitemap_urls` (scraper.py:217-220) fetches through the plain client — Tier 1 only, no escalation.**

- From AWS that **403s on 51 hosts and silently returns `[]`.**
- → **Today's sitemap-seeding is a no-op in production for every Akamai-gated host.**
- **Most likely why `seas` — which has a 5,709-URL sitemap — still crawls as unbounded BFS from AWS.** Its seed 403s and returns nothing.

> A silent failure hiding in plain sight: the sitemap logic "works" locally and does nothing in prod.

---

## Design consequences (locked)

- **Requirement:** sitemap & `robots.txt` fetches — `_fetch_sitemap_urls`, discovery, and the future `--update` `<lastmod>` fetch — **MUST route through the tier-escalating fetcher**, not a naive session. Otherwise sitemap-as-source and `--update` are **dead-on-arrival in production.**
- Folded into the scoping doc: **§8.4** (reachability confirmed) and **Task 16(c)** (tier-escalating discovery).
- **Detail that reconciles the data:** low `<loc>` counts (economics, history, sociology, statistics, seas…) are **sitemap indexes** — children hold the real URLs. Not thin sitemaps.

---

## Next steps

- **Build Task 16 with tier-escalating fetch** as an explicit acceptance criterion — this is now a prerequisite, not a nice-to-have.
- **Remaining open item:** a handful of sitemaps may be genuinely *incomplete* (histlit, classics, economics, history) — type-sample-test before relying on sitemap-as-source there.
- **File preservation** stays required: carry forward known file URLs on `--update` (file provenance is unreliable).

---

<!-- _class: lead -->

## Evidence (reproducible)

`aidocs/feature/scraper-update-mode/evidence/aws-reachability/`

**`AWS_REACHABILITY.md`** — full per-host tables
**`result.json`** — raw probe output (from S3)
**`sitemap_reachability_probe.py`** — the probe

ECS task `065e34b7…` · `atg-prod-default` · exit 0
