"""Offline: compare the 20 sampled pages (served .md vs our extraction of the HTML) and list every date-like value on each
page next to the XML sitemap lastmod. Reads samples/sample20 written by sample20_fetch.py.  python -I sample20_analyze.py"""
import json, re, sys
from email.utils import parsedate_to_datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[4]))      # repo root, for scrape_website
from scrape_website.scraper import _extract_text_trafilatura  # noqa: E402

ROOT = HERE / "samples" / "sample20"
OUT = []

DATE_PATTERNS = {
    "meta": re.compile(r'<meta[^>]+(?:property|name|itemprop)="(?:article:modified_time|article:published_time|og:updated_time|date|dcterms\.(?:modified|created)|last-modified|DC\.date[^"]*|modified|created)"[^>]*content="([^"]+)"', re.I),
    "jsonld": re.compile(r'"(dateModified|datePublished|dateCreated)"\s*:\s*"([^"]+)"'),
    "time_tag": re.compile(r'<time[^>]*datetime="([^"]+)"', re.I),
    "data_attr": re.compile(r'data-[a-z-]*(?:date|updated|modified|changed)[a-z-]*="([^"]+)"', re.I),
}
VISIBLE = re.compile(r"(?:last\s+(?:updated|modified|edited)|updated|modified)\s*[:\-]?\s*([A-Z][a-z]+ \d{1,2},? \d{4}|\d{1,2}/\d{1,2}/\d{2,4}|\d{4}-\d{2}-\d{2})", re.I)

def words(t):
    t = re.sub(r"\(https?://[^)]*\)|\(/[^)]*\)|<[^>]+>", " ", t)
    return re.findall(r"[A-Za-zÀ-ÿ0-9’'\-]{2,}", t.lower())

rows = []
for d in sorted(ROOT.glob("*/*")):
    m = json.load(open(d / "meta.json"))
    html = (d / "page.html").read_text(errors="replace")
    md = (d / "page.md").read_text(errors="replace")
    ours = _extract_text_trafilatura(html, m["url"], http_status=200) or ""
    body_ours = re.sub(r"\A---.*?---\n", "", ours, flags=re.S)
    wm, wo = set(words(md)), set(words(body_ours))
    found = {}
    for k, rx in DATE_PATTERNS.items():
        v = [x if isinstance(x, str) else x[-1] for x in rx.findall(html)]
        if v: found[k] = sorted(set(v))[:4]
    vis = VISIBLE.findall(re.sub(r"<[^>]+>", " ", html))
    if vis: found["visible_text"] = sorted(set(vis))[:3]
    md_dates = sorted(set(re.findall(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}/\d{1,2}/\d{4}\b", md)))[:4]
    def hdr(which, h): return m[which]["headers"].get(h) or m[which]["headers"].get(h.title())
    rows.append({
        "page": f"{d.parent.name}/{d.name}", "url": m["url"], "xml_lastmod": m["xml_lastmod"],
        "html_last_modified": hdr("page.html", "last-modified"), "html_etag": hdr("page.html", "etag"),
        "md_last_modified": hdr("page.md", "last-modified"), "md_etag": hdr("page.md", "etag"),
        "html_date_values": found, "md_date_values": md_dates,
        "words_md": len(words(md)), "words_ours": len(words(body_ours)),
        "only_in_md": len(wm - wo), "only_in_ours": len(wo - wm),
        "only_in_md_sample": sorted(wm - wo)[:12],
        "md_lines_blank": sum(1 for l in md.split("\n") if not l.strip()),
        "md_bytes": len(md.encode()), "ours_bytes": len(body_ours.encode()),
    })
json.dump(rows, open(HERE / "samples" / "sample20_analysis.json", "w"), indent=1)
print(len(rows), "pages")
