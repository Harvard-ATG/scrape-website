"""Fetch the evidence for the 19 typed pages: HTML, .md copy, the page's line in its host's /sitemap-llm (with line number), and the
raw <url> block from the host's XML sitemap (with the child sitemap it came from).
Live: 2 GETs per page, 1 /sitemap-llm and 1 + N XML requests per host, 1.5 s apart. Saves only excerpts of the two sitemaps.
  python -I evidence_pack_fetch.py samples/page_card_date_check.json samples/typed19   (out dir must not exist)"""
import json, re, sys, time
from pathlib import Path
from urllib.parse import urlsplit
from curl_cffi import requests as cr

src, out = json.load(open(sys.argv[1])), Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=False)
DELAY = 1.5


def get(url, tries=2):
    for _ in range(tries):
        try:
            r = cr.get(url, impersonate="chrome", timeout=120)
            time.sleep(DELAY)
            return r
        except Exception as e:
            err = e
            time.sleep(3)
    print("FAILED", url, str(err)[:80], flush=True)
    return None


pages = []
for x in src:
    host, path = x["host"], urlsplit(x["url"]).path
    slug = re.sub(r"[^a-z0-9]+", "-", path.lower()).strip("-")[:50]
    d = out / x["type"] / f'{host.split(".")[0]}-{slug}'
    d.mkdir(parents=True)
    meta = {"type": x["type"], "host": host, "url": x["url"], "md_url": x["url"] + ".md", "xml_lastmod_snapshot": x["xml_lastmod"]}
    for name, url in (("page.html", x["url"]), ("page.md", x["url"] + ".md")):
        r = get(url)
        if r is None:
            meta[name] = {"error": True}
            continue
        (d / name).write_bytes(r.content)
        meta[name] = {"status": r.status_code, "bytes": len(r.content), "content_type": r.headers.get("content-type")}
    pages.append((d, meta))
    print("page", x["type"], host, meta["page.html"].get("status"), meta["page.md"].get("status"), flush=True)

by_host = {}
for d, m in pages:
    by_host.setdefault(m["host"], []).append((d, m))

for host, items in by_host.items():
    # sitemap-llm: line numbers
    r = get(f"https://{host}/sitemap-llm")
    lines = r.text.split("\n") if r is not None and r.status_code == 200 else []
    for d, m in items:
        m["sitemap_llm"] = {"host_status": r.status_code if r is not None else None, "total_lines": len(lines)}
        for i, l in enumerate(lines, 1):
            if m["md_url"] in l:
                m["sitemap_llm"].update({"line_number": i, "line": l, "before": lines[i - 2] if i > 1 else "", "after": lines[i] if i < len(lines) else ""})
                break
    # XML: index or urlset
    todo = {m["url"]: (d, m) for d, m in items}
    r = get(f"https://{host}/sitemap.xml")
    if r is not None and r.status_code == 200:
        root = r.text
        children = re.findall(r"<sitemap>.*?<loc>([^<]+)</loc>", root, re.S) if "<sitemapindex" in root else []
        targets = children or [f"https://{host}/sitemap.xml"]
        for ci, child in enumerate(targets, 1):
            if not todo:
                break
            body = root if not children else (get(child).text if get(child) is not None else "")
            for url in list(todo):
                m_ = re.search(r"<url>\s*<loc>" + re.escape(url) + r"</loc>.*?</url>", body, re.S)
                if m_:
                    d, m = todo.pop(url)
                    m["xml_entry"] = {"child_sitemap": child, "child_index": ci if children else None, "block": m_.group(0)}
    for url, (d, m) in todo.items():
        m["xml_entry"] = {"not_found": True}
    print("host", host, "llm_lines", len(lines), "xml_missing", len(todo), flush=True)

for d, m in pages:
    json.dump(m, open(d / "meta.json", "w"), indent=1)
print("done", len(pages))
