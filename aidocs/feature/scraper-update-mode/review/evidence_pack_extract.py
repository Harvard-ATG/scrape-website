"""For each page in samples/typed19: run our extractor on the HTML, evaluate the scope rules, list dates and facts in each copy.
Offline. SITES_TOML=<file> python -I evidence_pack_extract.py samples/typed19 samples/typed19_extract.json"""
import json, re, sys
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / "rules"), str(HERE.parents[4])]
from loaders import load_sites  # noqa: E402
from rules import evaluate, url_kind  # noqa: E402
from scrape_website.scraper import _extract_text_trafilatura  # noqa: E402

RULE = {"foreign_host": "R2", "outside_path": "R3", "include_miss": "R4", "excluded": "R5", "seed": "R9", "ok": "in scope",
        "proposed:event_policy": "R7 (proposed)"}
M = "Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?"
DATE = re.compile(rf"\b(?:{M})\.? \d{{1,2}}(?:st|nd|rd|th)?,? (?:19|20)\d{{2}}\b|\b(?:19|20)\d{{2}}-\d{{2}}-\d{{2}}\b|\b\d{{1,2}}/\d{{1,2}}/(?:19|20)\d{{2}}\b")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(r"\(?\b\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}\b")
sites = load_sites()
root = Path(sys.argv[1])
rows = []
for d in sorted(root.glob("*/*")):
    m = json.load(open(d / "meta.json"))
    html = (d / "page.html").read_text(errors="replace") if (d / "page.html").exists() else ""
    md = (d / "page.md").read_text(errors="replace") if m["page.md"].get("status") == 200 else ""
    ours_full = _extract_text_trafilatura(html, m["url"], http_status=200) or ""
    ours = re.sub(r"\A---.*?---\n", "", ours_full, flags=re.S).strip()
    (d / "ours.md").write_text(ours_full)
    in_sites = m["host"] in sites
    entries = sites.get(m["host"]) or [{"url": f"https://{m['host']}/"}]   # a moved host is not in sites.toml any more
    dec = evaluate(m["url"], m["host"], entries)
    dec_ev = evaluate(m["url"], m["host"], entries, exclude_events=True)
    def ctx(text):
        out = []
        for i, line in enumerate(text.split("\n"), 1):
            for mm in DATE.finditer(line):
                out.append({"line": i, "date": mm.group(0), "text": re.sub(r"\s+", " ", line).strip()[:140]})
        return out[:6]
    def lines_with(text, n):  # line number of the first non-blank line containing n
        return next((i for i, l in enumerate(text.split("\n"), 1) if n in l), None)
    facts = lambda t: {"emails": sorted(set(EMAIL.findall(t))), "phones": sorted(set(PHONE.findall(t))), "dates": sorted(set(DATE.findall(t)))}
    fm, fo = facts(md), facts(ours)
    time_tags = re.findall(r"<time[^>]*datetime=\"([^\"]+)\"[^>]*>([^<]*)<", html)
    row = {
        "dir": str(d.relative_to(root)), "type": m["type"], "host": m["host"], "url": m["url"], "md_url": m["md_url"],
        "html_status": m["page.html"].get("status"), "md_status": m["page.md"].get("status"),
        "xml_lastmod_snapshot": m["xml_lastmod_snapshot"], "xml_entry": m.get("xml_entry"), "sitemap_llm": m.get("sitemap_llm"),
        "host_in_sites_toml": in_sites,
        "scope": {"in_scope": dec.in_scope, "reason": dec.reason, "rule": RULE.get(dec.reason, dec.reason), "kind": url_kind(m["url"]),
                  "with_proposed_event_rule": {"in_scope": dec_ev.in_scope, "rule": RULE.get(dec_ev.reason, dec_ev.reason)}},
        "md_dates": ctx(md), "html_time_tags": time_tags[:3], "ours_dates": ctx(ours),
        "md_words": len(re.findall(r"\w+", md)), "ours_words": len(re.findall(r"\w+", ours)),
        "ours_is_navigation": ours.startswith("Skip to main content"),
        "facts_only_in_md": {k: sorted(set(fm[k]) - set(fo[k]))[:8] for k in fm},
        "facts_only_in_ours": {k: sorted(set(fo[k]) - set(fm[k]))[:8] for k in fo},
        "md_headings": len(re.findall(r"^\s*#{1,6} ", md, re.M)), "ours_headings": len(re.findall(r"^#{1,6} ", ours, re.M)),
        "md_links": len(re.findall(r"\]\(", md)), "ours_links": len(re.findall(r"\]\(", ours)),
        "md_images": len(re.findall(r"!\[", md)), "ours_images": len(re.findall(r"!\[", ours)),
    }
    rows.append(row)
json.dump(rows, open(sys.argv[2], "w"), indent=1)
print(len(rows), "pages")
