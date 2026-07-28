# Scrape Cadence Recommendations

**Generated:** 2026-07-28  |  **Sites:** 83

Per-site scrape frequency + mode grounded in live-sitemap `<lastmod>` cadence and the delta vs. QA's last-scraped `manifest.json`. Diff column is `+new / -gone / ~changed` (BASE-normalized page counts); Baseline column is QA's manifest `generated_at` (with age) and flags a baseline older than 180d as `⚠ stale`.

## Recommendations

| Host | Frequency | Mode | Cadence | Diff (+/-/~) | Baseline | Rationale |
|---|---|---|---|---|---|---|
| aaas.fas.harvard.edu | weekly | fresh | high (~3.0d, cov 1.0) | +487 / -52 / ~0 | 2026-07-22 (6d) | cadence=high (~3.0d interval); 52 pages gone from sitemap — incremental cannot retire removals |
| academicresourcecenter.harvard.edu | weekly | incremental | high (~6.0d, cov 0.917) | +59 / -4 / ~0 | 2026-07-22 (6d) | cadence=high (~6.0d interval); mostly additive (59 new, 4 gone, 0 changed) |
| advising.college.harvard.edu | weekly | fresh | high (~5.0d, cov 0.933) | +26 / -44 / ~1 | 2026-07-22 (6d) | cadence=high (~5.0d interval); 44 pages gone from sitemap — incremental cannot retire removals |
| afvs.fas.harvard.edu | weekly | fresh | high (~6.0d, cov 1.0) | +355 / -71 / ~0 | 2026-07-22 (6d) | cadence=high (~6.0d interval); 71 pages gone from sitemap — incremental cannot retire removals |
| anthropology.fas.harvard.edu | weekly | fresh | high (~3.0d, cov 1.0) | +123 / -290 / ~1 | 2026-07-22 (6d) | cadence=high (~3.0d interval); 290 pages gone from sitemap — incremental cannot retire removals |
| archaeology.harvard.edu | weekly | incremental | high (~5.0d, cov 1.0) | +520 / -0 / ~0 | 2026-07-22 (6d) | cadence=high (~5.0d interval); mostly additive (520 new, 0 gone, 0 changed) |
| astronomy.fas.harvard.edu | weekly | fresh | high (~6.0d, cov 1.0) | +238 / -333 / ~1 | 2026-07-22 (6d) | cadence=high (~6.0d interval); 333 pages gone from sitemap — incremental cannot retire removals |
| careerservices.fas.harvard.edu | monthly | fresh | — | — | ⚠ none | no sitemap / no lastmod signal — conservative monthly full scrape |
| celtic.fas.harvard.edu | weekly | fresh | high (~11.0d, cov 1.0) | — | ⚠ none | cadence=high (~11.0d interval); no reliable baseline — full re-scrape to establish state |
| ces.fas.harvard.edu | monthly | fresh | — | — | ⚠ none | no sitemap / no lastmod signal — conservative monthly full scrape |
| classics.fas.harvard.edu | weekly | fresh | high (~7.0d, cov 1.0) | +227 / -600 / ~3 | 2026-07-22 (6d) | cadence=high (~7.0d interval); 600 pages gone from sitemap — incremental cannot retire removals |
| college.harvard.edu | weekly | incremental | high (~3.0d, cov 1.0) | +2445 / -1 / ~1 | 2026-07-22 (6d) | cadence=high (~3.0d interval); mostly additive (2445 new, 1 gone, 1 changed) |
| collegehousing.fas.harvard.edu | weekly | fresh | high (~13.0d, cov 0.931) | +7 / -37 / ~0 | 2026-07-22 (6d) | cadence=high (~13.0d interval); 37 pages gone from sitemap — incremental cannot retire removals |
| complit.fas.harvard.edu | weekly | fresh | high (~3.0d, cov 0.878) | +449 / -75 / ~23 | 2026-07-22 (6d) | cadence=high (~3.0d interval); 75 pages gone from sitemap — incremental cannot retire removals |
| courses.my.harvard.edu | monthly | fresh | — | — | ⚠ none | no sitemap / no lastmod signal — conservative monthly full scrape |
| csadvising.seas.harvard.edu | monthly | fresh | unknown (n/a, cov 0.0) | +0 / -52 / ~0 | 2026-07-22 (6d) | sitemap present but no <lastmod> dates — cannot derive cadence; conservative monthly full scrape |
| dao.fas.harvard.edu | weekly | fresh | high (~13.5d, cov 0.922) | +8 / -26 / ~0 | 2026-07-22 (6d) | cadence=high (~13.5d interval); 26 pages gone from sitemap — incremental cannot retire removals |
| daviscenter.fas.harvard.edu | monthly | fresh | — | — | ⚠ none | no sitemap / no lastmod signal — conservative monthly full scrape |
| dso.college.harvard.edu | weekly | fresh | high (~4.0d, cov 1.0) | +265 / -322 / ~6 | 2026-07-22 (6d) | cadence=high (~4.0d interval); 322 pages gone from sitemap — incremental cannot retire removals |
| eas.fas.harvard.edu | monthly | fresh | moderate (~16.0d, cov 1.0) | +44 / -7 / ~0 | 2026-07-22 (6d) | cadence=moderate (~16.0d interval); 7 pages gone from sitemap — incremental cannot retire removals |
| edsecondary.fas.harvard.edu | weekly | fresh | high (~13.0d, cov 1.0) | +200 / -32 / ~0 | 2026-07-22 (6d) | cadence=high (~13.0d interval); 32 pages gone from sitemap — incremental cannot retire removals |
| emr.fas.harvard.edu | weekly | incremental | high (~13.0d, cov 0.773) | +171 / -0 / ~0 | 2026-07-22 (6d) | cadence=high (~13.0d interval); mostly additive (171 new, 0 gone, 0 changed) |
| engagedscholarship.fas.harvard.edu | monthly | fresh | moderate (~30.0d, cov 0.816) | +16 / -23 / ~0 | 2026-07-22 (6d) | cadence=moderate (~30.0d interval); 23 pages gone from sitemap — incremental cannot retire removals |
| english.fas.harvard.edu | weekly | fresh | high (~4.0d, cov 1.0) | +425 / -437 / ~0 | 2026-07-22 (6d) | cadence=high (~4.0d interval); 437 pages gone from sitemap — incremental cannot retire removals |
| eps.harvard.edu | weekly | fresh | high (~3.0d, cov 1.0) | +682 / -54 / ~12 | 2026-07-22 (6d) | cadence=high (~3.0d interval); 54 pages gone from sitemap — incremental cannot retire removals |
| espp.fas.harvard.edu | weekly | fresh | high (~13.0d, cov 1.0) | +178 / -54 / ~0 | 2026-07-22 (6d) | cadence=high (~13.0d interval); 54 pages gone from sitemap — incremental cannot retire removals |
| firstyearseminarprogram.college.harvard.edu | weekly | fresh | high (~4.0d, cov 0.972) | +10 / -45 / ~0 | 2026-07-22 (6d) | cadence=high (~4.0d interval); 45 pages gone from sitemap — incremental cannot retire removals |
| folkmyth.fas.harvard.edu | monthly | fresh | moderate (~34.5d, cov 1.0) | +34 / -14 / ~0 | 2026-07-22 (6d) | cadence=moderate (~34.5d interval); 14 pages gone from sitemap — incremental cannot retire removals |
| gened.college.harvard.edu | weekly | fresh | high (~7.0d, cov 0.987) | +47 / -31 / ~0 | 2026-07-22 (6d) | cadence=high (~7.0d interval); 31 pages gone from sitemap — incremental cannot retire removals |
| german.fas.harvard.edu | weekly | fresh | high (~6.0d, cov 1.0) | +73 / -158 / ~0 | 2026-07-22 (6d) | cadence=high (~6.0d interval); 158 pages gone from sitemap — incremental cannot retire removals |
| ghhp.fas.harvard.edu | monthly | incremental | moderate (~21.0d, cov 1.0) | +473 / -0 / ~1 | 2026-07-22 (6d) | cadence=moderate (~21.0d interval); mostly additive (473 new, 0 gone, 1 changed) |
| haa.fas.harvard.edu | weekly | incremental | high (~2.0d, cov 1.0) | +2789 / -0 / ~1 | 2026-07-22 (6d) | cadence=high (~2.0d interval); mostly additive (2789 new, 0 gone, 1 changed) |
| handbook.college.harvard.edu | quarterly | incremental | low (~168.0d, cov 1.0) | +2 / -2 / ~0 | 2026-07-22 (6d) | cadence=low (~168.0d interval); mostly additive (2 new, 2 gone, 0 changed) |
| heb.fas.harvard.edu | weekly | fresh | high (~9.0d, cov 1.0) | +132 / -160 / ~5 | 2026-07-22 (6d) | cadence=high (~9.0d interval); 160 pages gone from sitemap — incremental cannot retire removals |
| histlit.fas.harvard.edu | weekly | fresh | high (~6.0d, cov 1.0) | +317 / -1861 / ~2 | 2026-07-22 (6d) | cadence=high (~6.0d interval); 1861 pages gone from sitemap — incremental cannot retire removals |
| history.fas.harvard.edu | weekly | fresh | high (~2.0d, cov 1.0) | +1206 / -5754 / ~0 | 2026-07-22 (6d) | cadence=high (~2.0d interval); 5754 pages gone from sitemap — incremental cannot retire removals |
| histsci.fas.harvard.edu | weekly | incremental | high (~7.0d, cov 1.0) | +865 / -0 / ~2 | 2026-07-22 (6d) | cadence=high (~7.0d interval); mostly additive (865 new, 0 gone, 2 changed) |
| hscrb.harvard.edu | weekly | incremental | high (~3.0d, cov 1.0) | +2003 / -83 / ~0 | 2026-07-22 (6d) | cadence=high (~3.0d interval); mostly additive (2003 new, 83 gone, 0 changed) |
| incomingstudents.college.harvard.edu | weekly | fresh | high (~3.5d, cov 1.0) | +5 / -2 / ~4 | 2026-07-22 (6d) | cadence=high (~3.5d interval); 4 pages changed since last scrape — incremental misses edits |
| iop.harvard.edu | weekly | incremental | high (~2.0d, cov 1.0) | +6940 / -0 / ~1 | 2026-07-22 (6d) | cadence=high (~2.0d interval); mostly additive (6940 new, 0 gone, 1 changed) |
| language.fas.harvard.edu | weekly | incremental | high (~14.0d, cov 1.0) | +24 / -0 / ~0 | 2026-07-23 (5d) | cadence=high (~14.0d interval); mostly additive (24 new, 0 gone, 0 changed) |
| library.harvard.edu | semiannual | incremental | dormant (~40.5d, cov 1.0) | +229 / -1 / ~0 | 2026-07-22 (6d) | cadence=dormant (~40.5d interval); mostly additive (229 new, 1 gone, 0 changed) |
| linguistics.fas.harvard.edu | weekly | fresh | high (~4.0d, cov 1.0) | +415 / -899 / ~0 | 2026-07-22 (6d) | cadence=high (~4.0d interval); 899 pages gone from sitemap — incremental cannot retire removals |
| lpce.college.harvard.edu | weekly | fresh | high (~13.0d, cov 1.0) | +65 / -8 / ~33 | 2026-07-22 (6d) | cadence=high (~13.0d interval); 8 pages gone from sitemap — incremental cannot retire removals |
| mbb.harvard.edu | weekly | incremental | high (~6.0d, cov 1.0) | +985 / -1 / ~0 | 2026-07-22 (6d) | cadence=high (~6.0d interval); mostly additive (985 new, 1 gone, 0 changed) |
| medieval.fas.harvard.edu | weekly | incremental | high (~3.0d, cov 1.0) | +1521 / -0 / ~0 | 2026-07-22 (6d) | cadence=high (~3.0d interval); mostly additive (1521 new, 0 gone, 0 changed) |
| msi.harvard.edu | weekly | incremental | high (~8.0d, cov 1.0) | +104 / -1 / ~0 | 2026-07-22 (6d) | cadence=high (~8.0d interval); mostly additive (104 new, 1 gone, 0 changed) |
| music.fas.harvard.edu | weekly | incremental | high (~2.5d, cov 1.0) | +453 / -1 / ~0 | 2026-07-23 (5d) | cadence=high (~2.5d interval); mostly additive (453 new, 1 gone, 0 changed) |
| nelc.fas.harvard.edu | weekly | fresh | high (~4.0d, cov 1.0) | +945 / -378 / ~5 | 2026-07-22 (6d) | cadence=high (~4.0d interval); 378 pages gone from sitemap — incremental cannot retire removals |
| oaisc.fas.harvard.edu | monthly | fresh | moderate (~22.0d, cov 0.946) | +3 / -17 / ~0 | 2026-07-22 (6d) | cadence=moderate (~22.0d interval); 17 pages gone from sitemap — incremental cannot retire removals |
| ofa.fas.harvard.edu | weekly | fresh | high (~3.0d, cov 1.0) | +227 / -428 / ~13 | 2026-07-22 (6d) | cadence=high (~3.0d interval); 428 pages gone from sitemap — incremental cannot retire removals |
| oie.fas.harvard.edu | weekly | fresh | high (~4.0d, cov 1.0) | +1085 / -140 / ~1 | 2026-07-22 (6d) | cadence=high (~4.0d interval); 140 pages gone from sitemap — incremental cannot retire removals |
| oue.fas.harvard.edu | weekly | fresh | high (~6.0d, cov 0.96) | +23 / -55 / ~0 | 2026-07-22 (6d) | cadence=high (~6.0d interval); 55 pages gone from sitemap — incremental cannot retire removals |
| philosophy.fas.harvard.edu | weekly | fresh | high (~5.0d, cov 1.0) | +242 / -321 / ~1 | 2026-07-22 (6d) | cadence=high (~5.0d interval); 321 pages gone from sitemap — incremental cannot retire removals |
| placement.college.harvard.edu | weekly | incremental | high (~12.0d, cov 0.968) | +2 / -0 / ~1 | 2026-07-22 (6d) | cadence=high (~12.0d interval); mostly additive (2 new, 0 gone, 1 changed) |
| publicservice.fas.harvard.edu | weekly | fresh | high (~12.0d, cov 1.0) | +791 / -41 / ~0 | 2026-07-22 (6d) | cadence=high (~12.0d interval); 41 pages gone from sitemap — incremental cannot retire removals |
| qrd.college.harvard.edu | quarterly | fresh | low (~61.0d, cov 0.988) | +3 / -10 / ~0 | 2026-07-22 (6d) | cadence=low (~61.0d interval); 10 pages gone from sitemap — incremental cannot retire removals |
| registrar.fas.harvard.edu | weekly | fresh | high (~4.0d, cov 1.0) | +648 / -116 / ~27 | 2026-07-22 (6d) | cadence=high (~4.0d interval); 116 pages gone from sitemap — incremental cannot retire removals |
| rll.fas.harvard.edu | weekly | fresh | high (~3.0d, cov 1.0) | +76 / -191 / ~0 | 2026-07-22 (6d) | cadence=high (~3.0d interval); 191 pages gone from sitemap — incremental cannot retire removals |
| sas.fas.harvard.edu | weekly | fresh | high (~7.0d, cov 0.997) | +170 / -335 / ~102 | 2026-07-22 (6d) | cadence=high (~7.0d interval); 335 pages gone from sitemap — incremental cannot retire removals |
| scienceeducation.fas.harvard.edu | weekly | fresh | high (~4.0d, cov 1.0) | +2089 / -64 / ~0 | 2026-07-22 (6d) | cadence=high (~4.0d interval); 64 pages gone from sitemap — incremental cannot retire removals |
| seas.harvard.edu | weekly | fresh | high (~1.0d, cov 1.0) | +1741 / -837 / ~21 | 2026-07-22 (6d) | cadence=high (~1.0d interval); 837 pages gone from sitemap — incremental cannot retire removals |
| seo.harvard.edu | weekly | fresh | high (~14.0d, cov 1.0) | +113 / -41 / ~0 | 2026-07-22 (6d) | cadence=high (~14.0d interval); 41 pages gone from sitemap — incremental cannot retire removals |
| slavic.fas.harvard.edu | weekly | fresh | high (~6.0d, cov 1.0) | +168 / -367 / ~0 | 2026-07-22 (6d) | cadence=high (~6.0d interval); 367 pages gone from sitemap — incremental cannot retire removals |
| socialstudies.fas.harvard.edu | monthly | fresh | moderate (~15.0d, cov 1.0) | +48 / -284 / ~3 | 2026-07-22 (6d) | cadence=moderate (~15.0d interval); 284 pages gone from sitemap — incremental cannot retire removals |
| sociology.fas.harvard.edu | weekly | fresh | high (~4.0d, cov 1.0) | +813 / -1249 / ~0 | 2026-07-22 (6d) | cadence=high (~4.0d interval); 1249 pages gone from sitemap — incremental cannot retire removals |
| specialconcentrations.fas.harvard.edu | monthly | fresh | moderate (~32.0d, cov 1.0) | +78 / -22 / ~0 | 2026-07-22 (6d) | cadence=moderate (~32.0d interval); 22 pages gone from sitemap — incremental cannot retire removals |
| statistics.fas.harvard.edu | weekly | fresh | high (~4.0d, cov 1.0) | +586 / -937 / ~0 | 2026-07-22 (6d) | cadence=high (~4.0d interval); 937 pages gone from sitemap — incremental cannot retire removals |
| studyofreligion.fas.harvard.edu | weekly | fresh | high (~3.5d, cov 0.923) | +31 / -45 / ~0 | 2026-07-22 (6d) | cadence=high (~3.5d interval); 45 pages gone from sitemap — incremental cannot retire removals |
| summerfunding.college.harvard.edu | weekly | fresh | high (~4.0d, cov 1.0) | +106 / -57 / ~0 | 2026-07-22 (6d) | cadence=high (~4.0d interval); 57 pages gone from sitemap — incremental cannot retire removals |
| tdm.fas.harvard.edu | weekly | fresh | high (~4.0d, cov 1.0) | +131 / -1044 / ~0 | 2026-07-22 (6d) | cadence=high (~4.0d interval); 1044 pages gone from sitemap — incremental cannot retire removals |
| undergrad.psychology.fas.harvard.edu | weekly | fresh | high (~2.0d, cov 1.0) | +1678 / -127 / ~3 | 2026-07-22 (6d) | cadence=high (~2.0d interval); 127 pages gone from sitemap — incremental cannot retire removals |
| uraf.harvard.edu | weekly | fresh | high (~3.5d, cov 1.0) | +264 / -218 / ~4 | 2026-07-22 (6d) | cadence=high (~3.5d interval); 218 pages gone from sitemap — incremental cannot retire removals |
| wgs.fas.harvard.edu | weekly | fresh | high (~5.0d, cov 1.0) | +97 / -436 / ~2 | 2026-07-22 (6d) | cadence=high (~5.0d interval); 436 pages gone from sitemap — incremental cannot retire removals |
| writingcenter.fas.harvard.edu | monthly | fresh | moderate (~26.0d, cov 1.0) | +42 / -12 / ~0 | 2026-07-22 (6d) | cadence=moderate (~26.0d interval); 12 pages gone from sitemap — incremental cannot retire removals |
| writingprogram.college.harvard.edu | weekly | fresh | high (~7.0d, cov 0.972) | +14 / -32 / ~1 | 2026-07-22 (6d) | cadence=high (~7.0d interval); 32 pages gone from sitemap — incremental cannot retire removals |
| www.chemistry.harvard.edu | weekly | fresh | high (~3.0d, cov 1.0) | +561 / -923 / ~2 | 2026-07-22 (6d) | cadence=high (~3.0d interval); 923 pages gone from sitemap — incremental cannot retire removals |
| www.economics.harvard.edu | weekly | fresh | high (~1.0d, cov 1.0) | +724 / -6023 / ~4 | 2026-07-22 (6d) | cadence=high (~1.0d interval); 6023 pages gone from sitemap — incremental cannot retire removals |
| www.gov.harvard.edu | weekly | fresh | high (~4.0d, cov 1.0) | +194 / -102 / ~1 | 2026-07-23 (5d) | cadence=high (~4.0d interval); 102 pages gone from sitemap — incremental cannot retire removals |
| www.hio.harvard.edu | monthly | fresh | — | — | ⚠ none | no sitemap / no lastmod signal — conservative monthly full scrape |
| www.math.harvard.edu | weekly | incremental | high (~2.0d, cov 0.999) | +2937 / -0 / ~7 | 2026-07-22 (6d) | cadence=high (~2.0d interval); mostly additive (2937 new, 0 gone, 7 changed) |
| www.mcb.harvard.edu | weekly | fresh | high (~2.0d, cov 1.0) | +6556 / -42 / ~20 | 2026-07-22 (6d) | cadence=high (~2.0d interval); 42 pages gone from sitemap — incremental cannot retire removals |
| www.physics.harvard.edu | weekly | fresh | high (~4.0d, cov 1.0) | +480 / -312 / ~4 | 2026-07-22 (6d) | cadence=high (~4.0d interval); 312 pages gone from sitemap — incremental cannot retire removals |

## Corpus rollup

**By frequency:**
- weekly: 66
- monthly: 14
- quarterly: 2
- semiannual: 1

**By mode:**
- fresh: 65
- incremental: 18

## No sitemap — fixed conservative schedule

- careerservices.fas.harvard.edu — monthly / fresh
- ces.fas.harvard.edu — monthly / fresh
- courses.my.harvard.edu — monthly / fresh
- daviscenter.fas.harvard.edu — monthly / fresh
- www.hio.harvard.edu — monthly / fresh
