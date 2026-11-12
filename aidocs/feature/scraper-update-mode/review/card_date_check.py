"""Compare the Date on file cards (/resource/<slug>.md) with the XML sitemap lastmod of the same landing page.
Live: 1 GET per card, 2 s apart (20 cards, 5 hosts). SITES_TOML=<file> python -I card_date_check.py <out.json>"""
import json, random, re, sys, time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / "rules")]
from curl_cffi import requests as cr  # noqa: E402
from loaders import SNAP_OCT, load_sites, load_snapshot  # noqa: E402
from rules import evaluate, parse_lastmod, url_kind  # noqa: E402

HOSTS = ["history.fas.harvard.edu", "sociology.fas.harvard.edu", "www.physics.harvard.edu", "nelc.fas.harvard.edu", "www.chemistry.harvard.edu"]
snap, sites = load_snapshot(SNAP_OCT), load_sites()
random.seed(7)
rows = []
for h in HOSTS:
    cand = [(l, m) for l, m in snap[h]["entries"] if m and url_kind(l) == "resource_page" and evaluate(l, h, sites[h]).in_scope]
    for loc, lm in random.sample(cand, 4):
        r = cr.get(loc.rstrip("/") + ".md", impersonate="chrome", timeout=90)
        time.sleep(2)
        body = r.text if r.status_code == 200 else ""
        m = re.search(r"\*\*Date:\*\*\s*([0-9/]+)", body)
        size = re.search(r"\*\*Size:\*\*\s*([^\n*]+)", body)
        fmt = re.search(r"\*\*Format:\*\*\s*([^\n*]+)", body)
        card = datetime.strptime(m.group(1), "%m/%d/%Y").date() if m else None
        x = parse_lastmod(lm)
        rows.append({"host": h, "url": loc, "status": r.status_code, "xml_lastmod": lm, "card_date": str(card) if card else None,
                     "size": size.group(1).strip() if size else None, "format": fmt.group(1).strip() if fmt else None,
                     "match_utc_date": bool(card and x and x.date() == card),
                     "match_et_date": bool(card and x and x.astimezone(ZoneInfo("America/New_York")).date() == card)})
        print(rows[-1]["host"][:12], rows[-1]["card_date"], lm, rows[-1]["match_utc_date"], rows[-1]["match_et_date"], rows[-1]["size"], rows[-1]["format"], flush=True)
json.dump(rows, open(sys.argv[1], "w"), indent=1)
n = len(rows)
print("cards", n, "with date", sum(1 for r in rows if r["card_date"]), "match UTC date", sum(r["match_utc_date"] for r in rows), "match ET date", sum(r["match_et_date"] for r in rows),
      "match either", sum(r["match_utc_date"] or r["match_et_date"] for r in rows))
