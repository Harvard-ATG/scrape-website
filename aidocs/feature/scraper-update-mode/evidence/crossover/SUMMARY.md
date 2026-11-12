# Corpus-wide sitemap vs state.db crossover

**Date**: 2026-07-23, fetched from a local IP. Read `FINDINGS.md` for what this means; this file is the table behind it.

Read-only analysis confirming the seas pattern generalizes. Fetched from a LOCAL/non-AWS IP: sitemap existence + contents are IP-independent facts; production reachability from AWS is NOT proven here.

## Aggregate

| Host | Sitemap | SM base | Rows | Distinct | Dup× | Crossover | Non-x base | Query bloat | SM-only missed | Real docs at-risk (null / not-in-SM) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| www.economics.harvard.edu | 5946 | 5946 | 30490 | 11874 | 2.57 | 5263 | 6611 | 5962 | 683 | 889 / 606 |
| history.fas.harvard.edu | 5767 | 5767 | 28172 | 11566 | 2.44 | 4650 | 6916 | 4854 | 1117 | 1173 / 583 |
| seas.harvard.edu | 5709 | 5709 | 14901 | 5204 | 2.86 | 4214 | 990 | 2647 | 1495 | 20 / 2 |
| www.chemistry.harvard.edu | 2876 | 2876 | 10448 | 4067 | 2.57 | 2423 | 1644 | 6381 | 453 | 34 / 58 |
| statistics.fas.harvard.edu | 2299 | 2299 | 9898 | 3831 | 2.58 | 1755 | 2076 | 2063 | 544 | 287 / 363 |
| sociology.fas.harvard.edu | 2242 | 2242 | 8596 | 3132 | 2.74 | 1510 | 1622 | 2037 | 732 | 132 / 614 |
| tdm.fas.harvard.edu | 1454 | 1454 | 6296 | 2500 | 2.52 | 1361 | 1139 | 1191 | 93 | 85 / 42 |
| histlit.fas.harvard.edu | 830 | 830 | 6007 | 2579 | 2.33 | 595 | 1984 | 468 | 235 | 327 / 130 |
| hscrb.harvard.edu | 4975 | 4975 | 5589 | 3177 | 1.76 | 3036 | 141 | 35 | 1939 | 0 / 0 |
| astronomy.fas.harvard.edu | 1237 | 1237 | 5317 | 1791 | 2.97 | 1080 | 711 | 1071 | 157 | 176 / 115 |
| classics.fas.harvard.edu | 549 | 549 | 4132 | 984 | 4.2 | 377 | 607 | 1485 | 172 | 25 / 18 |
| linguistics.fas.harvard.edu | 1833 | 1833 | 3976 | 3051 | 1.3 | 1437 | 1614 | 925 | 396 | 195 / 179 |
| slavic.fas.harvard.edu | 1079 | 1079 | 3688 | 1639 | 2.25 | 943 | 696 | 492 | 136 | 103 / 0 |
| dso.college.harvard.edu | 818 | 818 | 3104 | 1029 | 3.02 | 661 | 368 | 591 | 157 | 53 / 82 |
| ofa.fas.harvard.edu | 1081 | 1081 | 2888 | 1343 | 2.15 | 877 | 466 | 282 | 204 | 84 / 115 |
| english.fas.harvard.edu | 1635 | 1635 | 2713 | 1792 | 1.51 | 1248 | 544 | 921 | 387 | 53 / 160 |
| wgs.fas.harvard.edu | 1038 | 1038 | 2391 | 1513 | 1.58 | 973 | 540 | 878 | 65 | 11 / 49 |
| www.mcb.harvard.edu | 7189 | 7189 | 1721 | 808 | 2.13 | 671 | 137 | 864 | 6518 | 22 / 0 |
| anthropology.fas.harvard.edu | 831 | 831 | 1684 | 1149 | 1.47 | 727 | 422 | 536 | 104 | 14 / 74 |
| writingprogram.college.harvard.edu | 106 | 106 | 185 | 130 | 1.42 | 94 | 36 | 81 | 12 | 0 / 1 |

### No sitemap discovered (degrade-to-discover fallback applies)

- careerservices.fas.harvard.edu (rows=3068, distinct=1775)

## Hosts worth a second look

- www.economics.harvard.edu and history.fas.harvard.edu: about 30,000 and 28,000 state rows collapse to 11,900 and 11,600 distinct
  pages. Most of the rest is query-string bloat (6,000 and 4,900 rows). Each has over 1,000 documents with no known referrer.
- classics.fas.harvard.edu: the worst duplication, 4.2 rows per distinct page.
- www.mcb.harvard.edu: the sitemap lists 7,189 pages but the crawl saved 808. 6,518 sitemap pages were never reached by following links.
- hscrb.harvard.edu: the same pattern, 1,939 sitemap pages the crawl missed.
- careerservices.fas.harvard.edu: no sitemap at all (3,068 rows, 1,775 distinct); it falls back to link discovery.

Per-host detail for all 20 hosts is printed by `corpus_crossover.py`, which also writes `summary.json`.
