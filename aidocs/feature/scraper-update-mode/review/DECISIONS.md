# Decisions

One entry per decision: what was decided, on what evidence, what it changes, and how to undo it. Newest first. Open decisions
that came out of the same review are listed at the end with their ids from `REVIEW_FINDINGS.md`.

## D1. Exclude Drupal bibcite citation exports from the crawl

| | |
| --- | --- |
| Date | 2026-10-21 |
| Decided by | Kevin Gray |
| Status | Decided and committed as `bec9247` on `feature/scraper-update-mode-consolidated` (PR #10 branch; local, not pushed) |
| Verification | **NOT CHECKED:** whether any of these files was ever ingested or returned by the bot (database check and bot test not done) |
| Decision | Add `/bibcite/export` to `_DEFAULT_EXCLUDE_PATTERNS` in `scrape_website/scraper.py`. For now these files are not crawled, saved or listed in the manifest. |

**What they are.** Publication lists on Drupal sites offer "export" links that return a list as a small text file in a citation
manager format: EndNote XML (two layouts), RIS, BibTeX, MARC, EndNote tagged, and PubMed ID. The crawler followed them as documents
because the server answers `text/plain`.

**Evidence.**
- July QA manifests: 2,369 of 8,961 document entries (26.4%) match `/bibcite/export`, on 8 sites (`classics` 1,111, `sociology` 518,
  `linguistics` 283, `astronomy` 199, `heb` 151, `slavic` 103, `socialstudies` 2, `statistics` 2). The pattern matches no web page and
  nothing else among the 152,438 manifest entries.
- 381 of 384 lists were captured in all six formats: the same record is saved six times. Content hashes are distinct (2,361 of 2,369),
  because each address returns a different selection.
- Ingest does not read them: `preprocess.py:28` limits documents to `.pdf`, `.docx`, `.pptx` and `.doc`, so a `.txt` export is never
  uploaded. Splunk (index `soc-isites`, source `atg-apo-mcp`, 90 days) shows 63 crawler fetch lines for them, all on 2026-07-28, and no
  ingest upload, skip or retire.
- Six sampled exports against the page each was found on: the page already shows the full citation ("Publication information: ..."),
  usually with more authors than the export (Sociology: "Patterson, O., & Fosse, E. (2015)" against Orlando Patterson alone). Only two
  facts were unique to an export: a subject heading (Classics) and a page count (Slavic).
- On 2 of those 6 pages our extraction lost the page text (Astronomy, Slavic). The right fix for that is extraction, not these files.

**Why exclude.** They are not the type of content the tool ingests, they add little beyond the publication pages, they repeat six times,
and they cost crawl time and manifest space.

**What it changes.**
- Future crawls skip these addresses. The scraper and the update-mode rules share the default list, so the rules also treat them as out of scope.
- Entries already in old manifests and S3 remain until a fresh scrape replaces them. Ingest never used them, so the vector store is unaffected.
- Test: `tests/test_default_excludes.py` (all seven formats, a filtered address, and the publication pages that must stay).

**NOT CHECKED.** Whether any of these files was ever ingested or returned in an answer. The database check (`web_content_files`) and the
bot test were not completed; the bot test questions and files are in `review/samples/bibcite-qa/` and the review notes. If either shows
that the exports were used, reverse this decision.

**How to undo.** Remove the `/bibcite/export` line from `_DEFAULT_EXCLUDE_PATTERNS` and the three tests. If the data is wanted later,
ingest one format per list (not six) and add `.bib` or `.ris` handling to `preprocess.py`; or recover the same details from the
publication page's "Publication information" block.

**Follow-up.** If bibliographic details matter, fix extraction of publication pages instead (two of six sampled pages came back without
their text); see `REVIEW_FINDINGS.md` O18.

## Open decisions from the same review

| Id | Decision needed | Where |
| --- | --- | --- |
| D2 | Honour `Crawl-delay` on the 17 sites that ask for 30 s (one asks for 10)? | `REVIEW_FINDINGS.md`; Claude Doc section 3 |
| D3 | Accept a one-time re-ingest of most pages for a trafilatura upgrade (31 of 39 sampled pages change text)? When? | Claude Doc section 5 |
| D4 | Menu-only extraction: drop the page, or keep the last good copy if one exists? | `REVIEW_FINDINGS.md` O18 |
| D5 | Sitemap source for update mode: XML only (for dates), or XML plus the markdown sitemap for file discovery? | `SITEMAP_LLM_VS_XML.md` |
