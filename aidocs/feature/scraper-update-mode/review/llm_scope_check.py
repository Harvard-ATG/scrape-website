"""Fetch /sitemap-llm (one request per host), apply sites.toml scope rules, compare with the cached QA manifest.

Live: one GET per host, 1.5 s apart. Everything after the fetch is offline.
  MANIFEST_CACHE=<dir> SITES_TOML=<file> python llm_scope_check.py <out.json>
"""
import json, re, sys, time
from pathlib import Path
from urllib.parse import urlsplit, unquote

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / "rules")]
from curl_cffi import requests as cr  # noqa: E402
from loaders import load_manifest, load_sites  # noqa: E402
from rules import evaluate, normalize_key  # noqa: E402

PROBE = HERE.parent / "evidence" / "aws-reachability" / "result_llm.json"
hosts = [h for h in json.load(open(PROBE))["llm_hosts"]]
sites = load_sites()
LINK = re.compile(r"\[([^\]]*)\]\((https?://[^)\s]+)\)")
slug = lambda s: re.sub(r"[^a-z0-9]", "", unquote(s).lower())

out = {}
for h in hosts:
    if h not in sites:
        out[h] = {"skipped": "not in sites.toml"}
        continue
    try:
        r = cr.get(f"https://{h}/sitemap-llm", impersonate="chrome", timeout=90)
    except Exception as e:
        out[h] = {"error": str(e)[:80]}
        time.sleep(1.5)
        continue
    time.sleep(1.5)
    if r.status_code != 200 or "markdown" not in r.headers.get("content-type", ""):
        out[h] = {"error": f"status {r.status_code}"}
        continue
    entries = sites[h]
    pages, files = [], []
    for title, link in LINK.findall(r.text):
        page_url = re.sub(r"\.md$", "", link)
        (files if "/resource/" in link else pages).append((title, page_url))
    man = load_manifest(h)
    man_pages, man_docs = set(), []
    if man:
        for e in man[0]:
            if e.get("content_type") == "webpage":
                man_pages.add(normalize_key(e["source_url"]))
            else:
                man_docs.append(e)
    doc_slugs = {slug(Path(urlsplit(e["source_url"]).path).stem) for e in man_docs} | {slug(Path(e.get("filename", "")).stem) for e in man_docs}
    doc_slugs.discard("")
    rec = {"manifest": bool(man), "llm_pages": len(pages), "llm_files": len(files),
           "pages_in_scope": sum(evaluate(u, h, entries).in_scope for _, u in pages), "man_docs": len(man_docs)}
    in_files = [(t, u) for t, u in files if evaluate(u, h, entries).in_scope]
    rec["files_in_scope"] = len(in_files)
    rec["files_out_of_scope"] = len(files) - len(in_files)
    rec["files_in_scope_title_in_manifest"] = sum(slug(t) in doc_slugs or slug(Path(urlsplit(u).path).name) in doc_slugs for t, u in in_files)
    rec["files_in_scope_card_in_manifest"] = sum(normalize_key(u) in man_pages for _, u in in_files)
    rec["pages_in_scope_in_manifest"] = sum(normalize_key(u) in man_pages for _, u in pages if evaluate(u, h, entries).in_scope)
    out[h] = rec
    print(h, {k: v for k, v in rec.items() if k != "manifest"}, flush=True)
json.dump(out, open(sys.argv[1], "w"), indent=1)
