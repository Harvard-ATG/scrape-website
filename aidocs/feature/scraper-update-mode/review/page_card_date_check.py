"""Do page cards (.md copies of pages) carry dates? Sample 5 pages each of news, events, publications and blog types, fetch the .md
copy only, extract every date-like string, compare with the XML lastmod.
Live: 1 GET each, 2 s apart (20). SITES_TOML=<file> python -I page_card_date_check.py <out.json>"""
import json, random, re, sys, time
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / "rules")]
from curl_cffi import requests as cr  # noqa: E402
from loaders import SNAP_OCT, load_snapshot  # noqa: E402

TYPES = {"news": ("/news/",), "events": ("/event/", "/events/"), "publications": ("/publications/",), "blog": ("/blog/",)}
MONTH = "Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?"
PATS = [("iso", r"\b(?:19|20)\d{2}-\d{2}-\d{2}(?:T[\d:]+(?:Z|[+-]\d\d:?\d\d)?)?\b"), ("us_slash", r"\b\d{1,2}/\d{1,2}/(?:19|20)\d{2}\b"),
        ("month_d_yyyy", rf"\b(?:{MONTH})\.? \d{{1,2}}(?:st|nd|rd|th)?,? (?:19|20)\d{{2}}\b"), ("d_month_yyyy", rf"\b\d{{1,2}} (?:{MONTH})\.? (?:19|20)\d{{2}}\b"),
        ("month_yyyy", rf"\b(?:{MONTH})\.? (?:19|20)\d{{2}}\b")]
snap = load_snapshot(SNAP_OCT)
llm_hosts = [h for h in json.load(open(HERE.parent / "evidence/aws-reachability/result_llm.json"))["llm_hosts"] if h in snap and snap[h].get("entries")]
random.seed(11)
out = []
for t, segs in TYPES.items():
    pool = []
    for h in llm_hosts:
        for loc, lm in snap[h]["entries"]:
            p = urlsplit(loc).path
            if p.startswith(segs) and p.count("/") == 2 and lm:
                pool.append((h, loc, lm))
    by_host = {}
    for r in pool: by_host.setdefault(r[0], []).append(r)
    elig = [h for h, v in by_host.items() if len(v) >= 2]
    hosts = random.sample(elig, min(5, len(elig)))
    for h in hosts[:5]:
        loc, lm = random.choice(by_host[h])[1:]
        r = cr.get(loc + ".md", impersonate="chrome", timeout=90)
        time.sleep(2)
        md = r.text if r.status_code == 200 else ""
        hits = []
        for name, p in PATS:
            for m in re.finditer(p, md):
                hits.append({"form": name, "value": m.group(0), "context": re.sub(r"\s+", " ", md[max(0, m.start() - 50):m.end() + 25]).strip()})
        out.append({"type": t, "host": h, "url": loc, "status": r.status_code, "xml_lastmod": lm, "md_bytes": len(md), "dates_in_md": hits})
        print(t, h[:22], r.status_code, lm[:10], [x["value"] for x in hits][:4], flush=True)
json.dump(out, open(sys.argv[1], "w"), indent=1)
