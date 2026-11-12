# Samples: what each set was collected to show

All pages here were fetched on 2026-10-21 from a local IP (not AWS). The full sets were 184 saved pages. On 2026-11-12 the
folder was trimmed to a few exemplar pages plus every result file, because the tables in `../SITEMAP_LLM_VS_XML.md` already
tell the story. The scripts named below rebuild the full sets.

| Set | What it shows | Script | Summary | Finding or decision |
| --- | --- | --- | --- | --- |
| `sample20/` (2 of 20 pages kept) | Whether the page itself carries a date, and how the served `.md` copy compares with our own extraction | `sample20_fetch.py`, `sample20_analyze.py` | sections 4 and 7 | O17, O18, D4, D5 |
| `sample20_analysis.json`, `sample20_chunks.json` | The per-page table behind sections 4 and 7 (date found, words in each copy, chunk counts) | `sample20_analyze.py`, `evidence_pack_chunks.py` | sections 4 and 7 | O17, O18 |
| `typed19_table.md`, `typed19_extract.json`, `typed19_chunks.json` | Whether news, event, publication and blog `.md` copies carry a date, and what kind of date it is | `evidence_pack_fetch.py`, `evidence_pack_extract.py`, `evidence_pack_chunks.py` | section 4c | O17, O22 |
| `page_card_date_check.json`, `card_date_check.json` | The date on a page card or file card against the XML `lastmod` | `page_card_date_check.py`, `card_date_check.py` | sections 4b and 4c | O17 |
| `haa-about/`, `haa-about-extracted/`, `haa-about-COMPARE.md` | One page on haa.fas.harvard.edu in every form we can get it: HTML, served `.md`, our extraction, and all response headers | `evidence_pack_fetch.py` (single page) | section 4d | O21 |
| `trafilatura_dates.json`, `traf_200.json`, `traf_231.json` | Whether trafilatura finds a change date on these pages, and how its 2.0.0 output differs from 2.3.1 | `trafilatura_dates_check.py`, `trafilatura_versions_compare.py` | section 8c | O22, D3 |
| `robots_scope.json` | What each host's robots.txt asks of a crawler: crawl delay, disallow lines, whether anything in scope is blocked | `robots_scope_check.py` | `../DECISIONS.md` D2 | D2 |
| `bibcite-qa/` (1 of 6 hosts kept) | A bibcite citation export beside the publication page it was found on, to see what the export adds | `bibcite_value_check.py` | `../DECISIONS.md` D1 | D1, O23 |

Finding ids (O16 to O23) are in `../REVIEW_FINDINGS.md`. Decision ids (D1 to D5) are in `../DECISIONS.md`.

## The exemplars kept, and why

- `sample20/english.fas.harvard.edu/05-contact/`: our extraction returned the site navigation menu instead of the page, and the
  served `.md` copy was empty. The clearest case behind O18.
- `sample20/sociology.fas.harvard.edu/06-people-minjin-chae/`: the served `.md` copy keeps the taxonomy terms that our extraction
  drops. Shows what the platform copy adds.
- `haa-about/`: the one-page comparison that section 4d walks through.
- `bibcite-qa/sociology/`: the RIS export and the page it was found on. The page already shows the full citation with more authors
  than the export.

Each `sample20` folder holds `page.html` (as served), `page.md` (the platform's markdown copy), `ours.md` (our extraction) and
`meta.json` (URL, status codes, fetch time).

## Regenerating the full sets

Run from this `review/` folder, offline where the docstring says so. Each script's docstring gives the exact command.

- 20 recent pages on 4 hosts: `python -I sample20_fetch.py`, then `python -I sample20_analyze.py`.
- 19 typed pages: `python -I evidence_pack_fetch.py samples/page_card_date_check.json samples/typed19`, then
  `evidence_pack_extract.py` and `evidence_pack_chunks.py`.
- The bibcite pairs: `python -I bibcite_value_check.py qa_pick.json samples/bibcite-qa`.

The fetch scripts make one request per page, two seconds apart.
