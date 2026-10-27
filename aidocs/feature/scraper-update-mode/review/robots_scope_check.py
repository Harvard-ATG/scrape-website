"""How much of our in-scope URL set would robots.txt disallow? Live: 1 GET of /robots.txt per host (1.5 s apart); rest offline.
  SITES_TOML=<file> python -I robots_scope_check.py out.json"""
import json, sys, time, re
from pathlib import Path
from urllib.robotparser import RobotFileParser
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / "rules")]
from curl_cffi import requests as cr
from loaders import SNAP_OCT, load_sites, load_snapshot, sitemap_dict
from rules import evaluate
sites, snap = load_sites(), load_snapshot(SNAP_OCT)
out = {}
for host, ents in sorted(sites.items()):
    sm = sitemap_dict(snap.get(host))
    inscope = [u for u in (sm or {}) if evaluate(u if "://" in u else f"https://{host}{u}", host, ents).in_scope]
    rec = {"in_scope_urls": len(inscope)}
    try:
        r = cr.get(f"https://{host}/robots.txt", impersonate="chrome", timeout=60)
    except Exception as e:
        rec["error"] = str(e)[:60]; out[host] = rec; time.sleep(1.5); continue
    time.sleep(1.5)
    rec["status"] = r.status_code
    if r.status_code == 200 and "<html" not in r.text[:200].lower():
        rp = RobotFileParser(); rp.parse(r.text.splitlines())
        txt = r.text
        rec["disallow_lines"] = len(re.findall(r"(?im)^\s*disallow:\s*\S", txt))
        rec["crawl_delay"] = (re.search(r"(?im)^\s*crawl-delay:\s*([\d.]+)", txt) or [None, None])[1]
        rec["blocks_everything"] = bool(re.search(r"(?im)^\s*disallow:\s*/\s*$", txt))
        blocked = [u for u in inscope if not rp.can_fetch("*", u if "://" in u else f"https://{host}{u}")]
        rec["disallowed_in_scope"] = len(blocked); rec["examples"] = blocked[:3]
    out[host] = rec
json.dump(out, open(sys.argv[1], "w"), indent=1)
print("done", len(out))
