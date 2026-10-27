# One page, two forms: haa.fas.harvard.edu/about

Fetched 2026-10-21, one request each, from a local IP (not AWS):
- `haa-about/about.md`: the per-page markdown copy that `/sitemap-llm` links to (`https://haa.fas.harvard.edu/about.md`)
- `haa-about/about.html`: the page itself (`https://haa.fas.harvard.edu/about`)
- `haa-about-extracted/ours-from-html.md`: what the scraper's own `_extract_text_trafilatura` produces from that HTML (run offline on the saved file)

| | Served `.md` | Our extraction |
| --- | --- | --- |
| Words (link targets removed) | 766 | 532 |
| Headings | 12 | 15 |
| Links | 42 | 9 |
| Images | 20 (markdown image links) | 0 (`include_images=False`) |
| Blank or space-only lines | 442 | 42 |
| Front matter | none | title, url, hostname, sitename, date, http_status |

## What differs

- **Content dropped by our extraction.** Under the heading "Department Administration" the served copy has 16 person cards
  (name, role such as "Department Chair", titles, email). Our output keeps the heading and the closing contact block but none of the
  cards. 102 distinct words appear only in the served copy, mostly names, roles and emails.
- **The served copy is noisy.** Hundreds of blank or whitespace-only lines, image links, and layout leftovers (`arrow`, `circle`).
  It would need cleanup before ingest, and the images have no alt text beyond a name.
- **Front matter date is not a page date.** The HTML has no date meta tag; our output says `date: "2026-01-01"`, which is a
  heuristic guess by the metadata extractor (not checked which text triggered it). Do not use it as `lastmod`.
- **HTTP headers.** The `.md` response `Last-Modified` is 2026-10-21 11:54:53 GMT, the minute it was fetched (render time), while
  the HTML says 2026-10-20 17:36:07 GMT. Neither is a reliable change date; the XML `lastmod` is.

## What it means (one page; not a conclusion)

On this page the served markdown holds content our extractor lost, which matches the earlier worry that trafilatura's heuristics
can drop real content. One page cannot say how often that happens. A sample of about 20 pages across a few hosts, scored on
words present in one copy and missing from the other, would put a number on it. People and listing sections look like the likely
loss; that is a guess from this one page.
