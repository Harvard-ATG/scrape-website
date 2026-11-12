"""For simple /bibcite/export?...&format=ris files from the QA manifests: fetch the RIS and the page it was found on, and test which
facts in the RIS also appear in the page text (as our trafilatura extraction sees it). Live: 2 GETs per file, 2 s apart.
  python -I bibcite_value_check.py qa_pick.json samples/bibcite-qa"""
import json, re, sys, time, html as H
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from curl_cffi import requests as cr
from scrape_website.scraper import _extract_text_trafilatura
pick, out = json.load(open(sys.argv[1])), Path(sys.argv[2])
rows = []
def norm(t): return re.sub(r"[^a-z0-9]+", " ", H.unescape(re.sub(r"<[^>]+>", " ", t)).lower()).strip()
for host, ris_url, found_on, gen in pick:
    d = out / host.split(".")[0]; d.mkdir(exist_ok=True)
    r1 = cr.get(ris_url, impersonate="chrome", timeout=90); time.sleep(2)
    r2 = cr.get(found_on, impersonate="chrome", timeout=90); time.sleep(2)
    (d / "export.ris").write_bytes(r1.content); (d / "found_on.html").write_bytes(r2.content)
    ris = r1.text
    recs = [x for x in ris.split("ER  -") if x.strip()]
    page_text = norm(_extract_text_trafilatura(r2.text, found_on, 200) or "")
    fields = {}
    for line in ris.splitlines():
        m = re.match(r"^([A-Z][A-Z0-9])  - (.*)$", line)
        if m: fields.setdefault(m.group(1), []).append(m.group(2))
    def inpage(v):
        n = norm(v)
        if len(n) < 4: return None
        return (n[:70] in page_text) if len(n) > 70 else (n in page_text)
    check = {k: [(v[:60], inpage(v)) for v in vs[:2]] for k, vs in fields.items()}
    rows.append({"host": host, "ris_url": ris_url, "found_on": found_on, "ris_status": r1.status_code, "page_status": r2.status_code,
                 "ris_bytes": len(r1.content), "records_in_export": len(recs), "fields": {k: v for k, v in check.items()}})
    print(host.split(".")[0], "ris", r1.status_code, len(r1.content), "B | records", len(recs), "| page", r2.status_code, "| fields:", {k: [c[1] for c in v] for k, v in check.items()}, flush=True)
json.dump(rows, open(out / "check.json", "w"), indent=1)
