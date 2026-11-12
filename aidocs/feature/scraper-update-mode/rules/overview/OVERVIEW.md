# Scrape and update: how it works

Companion to `RULES.md`. These diagrams render on GitHub. Solid boxes exist in the scraper today. Anything labelled
proposed is reference code and tests in this folder, not wired into the scraper yet.

## 1. Today: one scrape

```mermaid
flowchart LR
  E["sites.toml entry<br/>seed URL + scope rules"] -- seed --> C["Crawl<br/>follow links on one host,<br/>random order"]
  C -. "new links" .-> C
  C -- URL --> F["Fetch<br/>3 tiers, escalate on 403 and 429"]
  F -- page --> S["Save<br/>pages, text, files, state.db"]
  S -- rows --> M["Manifest + S3<br/>only if complete and not capped"]
  M -- files --> I["Ingest<br/>unchanged: skip<br/>missing from this run: retire"]
```

Two ways to run it:

| Run | What it does |
| --- | --- |
| `--fresh` | Clears the host's local data, re-crawls everything, then ingest retires whatever the crawl did not reach |
| Normal | Pulls the last run from S3, skips URLs already visited, adds new pages only; changed pages stay stale; nothing is retired |

Where it hurts: crawl order is random (the same settings saved 45 to 136 pages on one site), nothing refreshes a single
changed page, and "removed" means "the crawl did not reach it" with no check on how many pages that is.

## 2. Proposed: an update run

```mermaid
flowchart TD
  E["sites.toml entry"] --> SC["Scope rules<br/>host, seed path, include, exclude"]
  SC --> RS["Read the sitemap<br/>every URL with its last-modified date"]
  SC -. "tiny path-scoped section (R10)" .-> SE["Refetch the seeds only"]
  RS -. "unreadable or lists another host (R11, R12)" .-> X["Skip this host"]
  RS --> PL{"Plan<br/>compare each date with what is stored"}
  PL -- "new, changed, no date" --> FE["Fetch only these"]
  PL -- unchanged --> SK["Skip"]
  PL -- "never captured (R20)" --> BF["Backfill list<br/>separate, capped run"]
  SE --> FE
  FE --> SV["Save<br/>changed pages replaced, unchanged files kept"]
  SV --> ST["Record state<br/>date and fetch time per URL"]
  ST --> IN["Ingest<br/>unchanged: hash skip"]
```

## 3. What happens to one URL

```mermaid
flowchart TD
  U["URL from the sitemap"] --> N["Normalize (R1)<br/>https, no trailing slash"]
  N --> H{"Same host as the entry? (R2)"}
  H -- no --> OUT["skip: out of scope"]
  H -- yes --> P{"Inside the seed path? (R3)<br/>path-scoped entries only"}
  P -- no --> OUT
  P -- yes --> I{"Matches an include pattern? (R4)<br/>entries with patterns only"}
  I -- no --> OUT
  I -- yes --> X{"Hits an exclude? (R5, R6, R7)"}
  X -- yes --> OUT
  X -- no --> D{"Compare with what is stored (R13)"}
  D --> NEW["New: fetch"]
  D --> CH["Changed: fetch"]
  D --> ND["No date: fetch every run"]
  D --> UN["Unchanged: keep"]
  D --> NC["Never captured: backfill list (R20)"]
```

## 4. Deleting a page

```mermaid
flowchart LR
  subgraph T["Today: a full crawl decides"]
    direction TB
    T1["Full (fresh) crawl"] --> T2["Files on disk = active set"] --> T3["Ingest retires every record<br/>not in the active set"] --> T4["Soft retire: hidden from search"]
  end
  subgraph U["Proposed: the sitemap decides"]
    direction TB
    U1["Compare sitemap snapshots"] --> U2["Departures: listed before, gone now (R15)"] --> U3["Guards: unreadable, moved host,<br/>over 30% gone (R11, R12, R15)"] --> U4["Confirm each by fetching (R16)<br/>404 or 410 retire, 403 hold,<br/>redirect follow, 200 keep, 5xx never"] --> U5["Retire after a complete,<br/>uncapped run (R17)"]
  end
```

A page the crawl never reached is retired today even though it still exists. Under the proposed path only pages that were
listed and then vanished are candidates, and a fetch must agree. Pages that were never in a sitemap are covered by a
monthly full refresh (R19).

## What is in this PR

| Piece | Where it sits | Status |
| --- | --- | --- |
| 429 escalation (2 commits) | Fetch | In the scraper |
| PR #4: https canonicalization, search and `.ics` excludes | Normalize, scope | In the scraper |
| PR #7: crawl-generation columns, `_should_fetch`, manifest guard | Save, manifest | In the scraper; fetch behavior unchanged |
| PR #8: tiered sitemap discovery, cadence tooling | Read the sitemap | Discovery in the scraper; cadence is analysis |
| This folder: taxonomy, `rules.py`, tests, `validate_hosts.py` | Scope, plan, departures | Reference code and tests only |

Not built yet: the update flag itself; a stored last-modified date and saved sitemap snapshot per run; the departures and
confirmation-fetch step; the backfill run; scheduling the monthly full refresh.
