"""Run trafilatura on the saved HTML pages with the same options our scraper uses and write the results.
  TRAF_PATH=<dir containing another trafilatura install> python trafilatura_versions_compare.py out.json
Without TRAF_PATH the interpreter's own trafilatura is used."""
import json, os, re, sys
from pathlib import Path
if os.environ.get("TRAF_PATH"):
    sys.path.insert(0, os.environ["TRAF_PATH"])
import trafilatura
from trafilatura.deduplication import LRU_TEST

S = Path(__file__).resolve().parent / "samples"
pages = []
for d in sorted((S / "sample20").glob("*/*")) + sorted((S / "typed19").glob("*/*")) + [S / "haa-about"]:
    h = d / ("about.html" if d.name == "haa-about" else "page.html")
    if not h.exists():
        continue
    html = h.read_text(errors="replace")
    if "<title>Not Found</title>" in html[:3000]:
        continue
    m = json.load(open(d / "meta.json")) if (d / "meta.json").exists() else {"url": "https://haa.fas.harvard.edu/about"}
    pages.append((str(d.relative_to(S)), m["url"], html))
out = []
for name, url, html in pages:
    LRU_TEST.clear()
    body = trafilatura.extract(html, url=url, include_comments=False, include_tables=True, include_links=True, include_images=False,
                               favor_recall=True, deduplicate=True, with_metadata=False, output_format="markdown") or ""
    meta = trafilatura.extract_metadata(html, default_url=url)
    out.append({"page": name, "url": url, "words": len(re.findall(r"\w+", body)), "nav": body.startswith("Skip to main content"),
                "headings": len(re.findall(r"^#{1,6} ", body, re.M)), "date": meta.date if meta else None, "body": body})
json.dump({"version": trafilatura.__version__, "pages": out}, open(sys.argv[1], "w"), indent=0)
print(trafilatura.__version__, len(out), "pages")
