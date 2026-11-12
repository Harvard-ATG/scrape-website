"""What date does trafilatura (and htmldate) return for the pages we saved, compared with the XML sitemap lastmod and the date shown on the page?
Offline. python -I trafilatura_dates_check.py   (reads samples/sample20, samples/typed19, samples/haa-about)"""
import json, re, sys
from pathlib import Path
import trafilatura
from trafilatura.settings import set_date_params
from htmldate import find_date

S = Path(__file__).resolve().parent / "samples"
FULL = "%Y-%m-%dT%H:%M:%S"
pages = []
for d in sorted((S / "sample20").glob("*/*")):
    m = json.load(open(d / "meta.json")); pages.append(("sample20", m["url"], (d / "page.html").read_text(errors="replace"), m["xml_lastmod"], None))
ext = {x["dir"]: x for x in json.load(open(S / "typed19_extract.json"))}
for d in sorted((S / "typed19").glob("*/*")):
    m = json.load(open(d / "meta.json")); x = ext.get(str(d.relative_to(S / "typed19")))
    shown = x["md_dates"][0]["date"] if x and x["md_dates"] else None
    pages.append(("typed19:" + m["type"], m["url"], (d / "page.html").read_text(errors="replace"), m["xml_lastmod_snapshot"], shown))
rows = []
for kind, url, html, xml, shown in pages:
    if "<html" not in html[:2000].lower() and "<!doctype" not in html[:200].lower():
        continue
    if "<title>Not Found</title>" in html[:3000]:
        continue
    meta_default = trafilatura.extract_metadata(html, default_url=url)
    dflt = meta_default.date if meta_default else None
    cfg = set_date_params(True); cfg.update({"original_date": False, "outputformat": FULL})
    meta_mod = trafilatura.extract_metadata(html, default_url=url, date_config=cfg)
    modified_mode = meta_mod.date if meta_mod else None
    strict = find_date(html, extensive_search=False, original_date=False, outputformat=FULL, url=url)
    rows.append({"kind": kind, "url": url, "xml_lastmod": xml, "shown_on_page": shown,
                 "trafilatura_default": dflt, "trafilatura_original_false_fullts": modified_mode, "htmldate_strict_modified": strict})
json.dump(rows, open(S / "trafilatura_dates.json", "w"), indent=1)
n = len(rows)
xd = lambda r: (r["xml_lastmod"] or "")[:10]
print("pages", n)
print("trafilatura default returns a date:", sum(1 for r in rows if r["trafilatura_default"]))
print("  equals XML lastmod date:", sum(1 for r in rows if r["trafilatura_default"] and r["trafilatura_default"][:10] == xd(r)))
print("  equals date shown on page (where one is shown):", sum(1 for r in rows if r["shown_on_page"] and r["trafilatura_default"]), "of", sum(1 for r in rows if r["shown_on_page"]), "pages with a shown date;",
      "match:", sum(1 for r in rows if r["shown_on_page"] and r["trafilatura_default"] and __import__("datetime").datetime.strptime(r["shown_on_page"], "%B %d, %Y").date().isoformat() == r["trafilatura_default"][:10]) if any(r["shown_on_page"] for r in rows) else "")
print("trafilatura with original_date=False + time of day returns a date:", sum(1 for r in rows if r["trafilatura_original_false_fullts"]), "| with a time part:", sum(1 for r in rows if r["trafilatura_original_false_fullts"] and "T" in r["trafilatura_original_false_fullts"] and not r["trafilatura_original_false_fullts"].endswith("T00:00:00")))
print("  equals XML lastmod to the day:", sum(1 for r in rows if r["trafilatura_original_false_fullts"] and r["trafilatura_original_false_fullts"][:10] == xd(r)))
print("htmldate strict (structured sources only, modified preferred) returns a date:", sum(1 for r in rows if r["htmldate_strict_modified"]))
guess = [r for r in rows if r["trafilatura_default"] and r["trafilatura_default"].endswith("-01-01")]
print("defaults that look like year-only guesses (YYYY-01-01):", len(guess))
for r in rows[:0]: pass
import collections
print("by kind, default date present:", dict(collections.Counter(r["kind"] for r in rows if r["trafilatura_default"])), "of", dict(collections.Counter(r["kind"] for r in rows)))
