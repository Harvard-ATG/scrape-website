# Corpus-wide sitemap vs state.db crossover

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

## Per-host detail

### www.economics.harvard.edu
- sitemap source: `standard:https://www.economics.harvard.edu/sitemap.xml`
- rows 30490 -> distinct 11874 (dup collapse 2.57x); sitemap 5946
- crossover 5263; non-crossover base 6611; query bloat 5962; sitemap-only missed 683
- non-crossover by type: {'file': 5198, 'distinct-path': 1317, 'query-string (pagination/facet)': 96}
- real docs (pdf/doc/xls/ppt) not in sitemap: 1645 total, 150 recoverable via good found_on, 889 null found_on, 606 at-risk, 0 derivative junk
- images not in sitemap: 18 total, 0 derivative junk, 18 null found_on

### history.fas.harvard.edu
- sitemap source: `standard:https://history.fas.harvard.edu/sitemap.xml`
- rows 28172 -> distinct 11566 (dup collapse 2.44x); sitemap 5767
- crossover 4650; non-crossover base 6916; query bloat 4854; sitemap-only missed 1117
- non-crossover by type: {'file': 4938, 'distinct-path': 1795, 'query-string (pagination/facet)': 183}
- real docs (pdf/doc/xls/ppt) not in sitemap: 2135 total, 379 recoverable via good found_on, 1173 null found_on, 583 at-risk, 0 derivative junk
- images not in sitemap: 85 total, 0 derivative junk, 85 null found_on

### seas.harvard.edu
- sitemap source: `robots:https://seas.harvard.edu/sitemap.xml`
- rows 14901 -> distinct 5204 (dup collapse 2.86x); sitemap 5709
- crossover 4214; non-crossover base 990; query bloat 2647; sitemap-only missed 1495
- non-crossover by type: {'file': 174, 'distinct-path': 680, 'query-string (pagination/facet)': 133, 'garbage/local-path': 3}
- real docs (pdf/doc/xls/ppt) not in sitemap: 97 total, 29 recoverable via good found_on, 20 null found_on, 2 at-risk, 46 derivative junk
- images not in sitemap: 242 total, 0 derivative junk, 242 null found_on

### www.chemistry.harvard.edu
- sitemap source: `standard:https://www.chemistry.harvard.edu/sitemap.xml`
- rows 10448 -> distinct 4067 (dup collapse 2.57x); sitemap 2876
- crossover 2423; non-crossover base 1644; query bloat 6381; sitemap-only missed 453
- non-crossover by type: {'file': 1424, 'distinct-path': 151, 'query-string (pagination/facet)': 69}
- real docs (pdf/doc/xls/ppt) not in sitemap: 417 total, 325 recoverable via good found_on, 34 null found_on, 58 at-risk, 0 derivative junk
- images not in sitemap: 10 total, 0 derivative junk, 10 null found_on

### statistics.fas.harvard.edu
- sitemap source: `standard:https://statistics.fas.harvard.edu/sitemap.xml`
- rows 9898 -> distinct 3831 (dup collapse 2.58x); sitemap 2299
- crossover 1755; non-crossover base 2076; query bloat 2063; sitemap-only missed 544
- non-crossover by type: {'distinct-path': 246, 'file': 1809, 'query-string (pagination/facet)': 21}
- real docs (pdf/doc/xls/ppt) not in sitemap: 710 total, 60 recoverable via good found_on, 287 null found_on, 363 at-risk, 0 derivative junk
- images not in sitemap: 4 total, 0 derivative junk, 4 null found_on

### sociology.fas.harvard.edu
- sitemap source: `standard:https://sociology.fas.harvard.edu/sitemap.xml`
- rows 8596 -> distinct 3132 (dup collapse 2.74x); sitemap 2242
- crossover 1510; non-crossover base 1622; query bloat 2037; sitemap-only missed 732
- non-crossover by type: {'file': 1253, 'distinct-path': 309, 'query-string (pagination/facet)': 60}
- real docs (pdf/doc/xls/ppt) not in sitemap: 755 total, 9 recoverable via good found_on, 132 null found_on, 614 at-risk, 0 derivative junk
- images not in sitemap: 4 total, 0 derivative junk, 4 null found_on

### tdm.fas.harvard.edu
- sitemap source: `standard:https://tdm.fas.harvard.edu/sitemap.xml`
- rows 6296 -> distinct 2500 (dup collapse 2.52x); sitemap 1454
- crossover 1361; non-crossover base 1139; query bloat 1191; sitemap-only missed 93
- non-crossover by type: {'file': 734, 'query-string (pagination/facet)': 123, 'distinct-path': 282}
- real docs (pdf/doc/xls/ppt) not in sitemap: 153 total, 26 recoverable via good found_on, 85 null found_on, 42 at-risk, 0 derivative junk
- images not in sitemap: 6 total, 0 derivative junk, 6 null found_on

### histlit.fas.harvard.edu
- sitemap source: `standard:https://histlit.fas.harvard.edu/sitemap.xml`
- rows 6007 -> distinct 2579 (dup collapse 2.33x); sitemap 830
- crossover 595; non-crossover base 1984; query bloat 468; sitemap-only missed 235
- non-crossover by type: {'file': 276, 'distinct-path': 1579, 'query-string (pagination/facet)': 129}
- real docs (pdf/doc/xls/ppt) not in sitemap: 477 total, 18 recoverable via good found_on, 327 null found_on, 130 at-risk, 0 derivative junk
- images not in sitemap: 0 total, 0 derivative junk, 0 null found_on

### hscrb.harvard.edu
- sitemap source: `standard:https://hscrb.harvard.edu/sitemap.xml`
- rows 5589 -> distinct 3177 (dup collapse 1.76x); sitemap 4975
- crossover 3036; non-crossover base 141; query bloat 35; sitemap-only missed 1939
- non-crossover by type: {'file': 59, 'distinct-path': 80, 'query-string (pagination/facet)': 2}
- real docs (pdf/doc/xls/ppt) not in sitemap: 5 total, 5 recoverable via good found_on, 0 null found_on, 0 at-risk, 0 derivative junk
- images not in sitemap: 53 total, 0 derivative junk, 53 null found_on

### astronomy.fas.harvard.edu
- sitemap source: `standard:https://astronomy.fas.harvard.edu/sitemap.xml`
- rows 5317 -> distinct 1791 (dup collapse 2.97x); sitemap 1237
- crossover 1080; non-crossover base 711; query bloat 1071; sitemap-only missed 157
- non-crossover by type: {'file': 527, 'distinct-path': 155, 'query-string (pagination/facet)': 29}
- real docs (pdf/doc/xls/ppt) not in sitemap: 301 total, 10 recoverable via good found_on, 176 null found_on, 115 at-risk, 0 derivative junk
- images not in sitemap: 44 total, 0 derivative junk, 44 null found_on

### classics.fas.harvard.edu
- sitemap source: `standard:https://classics.fas.harvard.edu/sitemap.xml`
- rows 4132 -> distinct 984 (dup collapse 4.2x); sitemap 549
- crossover 377; non-crossover base 607; query bloat 1485; sitemap-only missed 172
- non-crossover by type: {'distinct-path': 516, 'query-string (pagination/facet)': 17, 'file': 74}
- real docs (pdf/doc/xls/ppt) not in sitemap: 98 total, 55 recoverable via good found_on, 25 null found_on, 18 at-risk, 0 derivative junk
- images not in sitemap: 0 total, 0 derivative junk, 0 null found_on

### linguistics.fas.harvard.edu
- sitemap source: `standard:https://linguistics.fas.harvard.edu/sitemap.xml`
- rows 3976 -> distinct 3051 (dup collapse 1.3x); sitemap 1833
- crossover 1437; non-crossover base 1614; query bloat 925; sitemap-only missed 396
- non-crossover by type: {'distinct-path': 338, 'file': 1259, 'query-string (pagination/facet)': 17}
- real docs (pdf/doc/xls/ppt) not in sitemap: 423 total, 49 recoverable via good found_on, 195 null found_on, 179 at-risk, 0 derivative junk
- images not in sitemap: 38 total, 0 derivative junk, 38 null found_on

### slavic.fas.harvard.edu
- sitemap source: `standard:https://slavic.fas.harvard.edu/sitemap.xml`
- rows 3688 -> distinct 1639 (dup collapse 2.25x); sitemap 1079
- crossover 943; non-crossover base 696; query bloat 492; sitemap-only missed 136
- non-crossover by type: {'file': 603, 'distinct-path': 80, 'query-string (pagination/facet)': 13}
- real docs (pdf/doc/xls/ppt) not in sitemap: 190 total, 87 recoverable via good found_on, 103 null found_on, 0 at-risk, 0 derivative junk
- images not in sitemap: 78 total, 0 derivative junk, 78 null found_on

### dso.college.harvard.edu
- sitemap source: `standard:https://dso.college.harvard.edu/sitemap.xml`
- rows 3104 -> distinct 1029 (dup collapse 3.02x); sitemap 818
- crossover 661; non-crossover base 368; query bloat 591; sitemap-only missed 157
- non-crossover by type: {'file': 100, 'distinct-path': 240, 'query-string (pagination/facet)': 28}
- real docs (pdf/doc/xls/ppt) not in sitemap: 139 total, 4 recoverable via good found_on, 53 null found_on, 82 at-risk, 0 derivative junk
- images not in sitemap: 1 total, 0 derivative junk, 1 null found_on

### ofa.fas.harvard.edu
- sitemap source: `standard:https://ofa.fas.harvard.edu/sitemap.xml`
- rows 2888 -> distinct 1343 (dup collapse 2.15x); sitemap 1081
- crossover 877; non-crossover base 466; query bloat 282; sitemap-only missed 204
- non-crossover by type: {'distinct-path': 227, 'file': 224, 'query-string (pagination/facet)': 15}
- real docs (pdf/doc/xls/ppt) not in sitemap: 239 total, 40 recoverable via good found_on, 84 null found_on, 115 at-risk, 0 derivative junk
- images not in sitemap: 8 total, 0 derivative junk, 8 null found_on

### english.fas.harvard.edu
- sitemap source: `standard:https://english.fas.harvard.edu/sitemap.xml`
- rows 2713 -> distinct 1792 (dup collapse 1.51x); sitemap 1635
- crossover 1248; non-crossover base 544; query bloat 921; sitemap-only missed 387
- non-crossover by type: {'file': 372, 'distinct-path': 137, 'query-string (pagination/facet)': 35}
- real docs (pdf/doc/xls/ppt) not in sitemap: 241 total, 28 recoverable via good found_on, 53 null found_on, 160 at-risk, 0 derivative junk
- images not in sitemap: 5 total, 0 derivative junk, 5 null found_on

### wgs.fas.harvard.edu
- sitemap source: `standard:https://wgs.fas.harvard.edu/sitemap.xml`
- rows 2391 -> distinct 1513 (dup collapse 1.58x); sitemap 1038
- crossover 973; non-crossover base 540; query bloat 878; sitemap-only missed 65
- non-crossover by type: {'file': 440, 'distinct-path': 88, 'query-string (pagination/facet)': 12}
- real docs (pdf/doc/xls/ppt) not in sitemap: 63 total, 3 recoverable via good found_on, 11 null found_on, 49 at-risk, 0 derivative junk
- images not in sitemap: 4 total, 0 derivative junk, 4 null found_on

### www.mcb.harvard.edu
- sitemap source: `robots:https://www.mcb.harvard.edu/sitemap_index.xml`
- rows 1721 -> distinct 808 (dup collapse 2.13x); sitemap 7189
- crossover 671; non-crossover base 137; query bloat 864; sitemap-only missed 6518
- non-crossover by type: {'query-string (pagination/facet)': 15, 'distinct-path': 100, 'file': 22}
- real docs (pdf/doc/xls/ppt) not in sitemap: 22 total, 0 recoverable via good found_on, 22 null found_on, 0 at-risk, 0 derivative junk
- images not in sitemap: 0 total, 0 derivative junk, 0 null found_on

### anthropology.fas.harvard.edu
- sitemap source: `standard:https://anthropology.fas.harvard.edu/sitemap.xml`
- rows 1684 -> distinct 1149 (dup collapse 1.47x); sitemap 831
- crossover 727; non-crossover base 422; query bloat 536; sitemap-only missed 104
- non-crossover by type: {'file': 335, 'query-string (pagination/facet)': 22, 'distinct-path': 65}
- real docs (pdf/doc/xls/ppt) not in sitemap: 107 total, 19 recoverable via good found_on, 14 null found_on, 74 at-risk, 0 derivative junk
- images not in sitemap: 62 total, 0 derivative junk, 62 null found_on

### writingprogram.college.harvard.edu
- sitemap source: `robots:https://writingprogram.college.harvard.edu/wp-sitemap.xml`
- rows 185 -> distinct 130 (dup collapse 1.42x); sitemap 106
- crossover 94; non-crossover base 36; query bloat 81; sitemap-only missed 12
- non-crossover by type: {'query-string (pagination/facet)': 5, 'file': 27, 'distinct-path': 4}
- real docs (pdf/doc/xls/ppt) not in sitemap: 27 total, 26 recoverable via good found_on, 0 null found_on, 1 at-risk, 0 derivative junk
- images not in sitemap: 0 total, 0 derivative junk, 0 null found_on

