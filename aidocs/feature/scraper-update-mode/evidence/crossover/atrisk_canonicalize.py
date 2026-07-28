"""Resolve whether the corpus 'at-risk' document counts are REAL orphans or
found_on artifacts.

The crossover flagged files whose found_on page's base URL is not in the
sitemap as 'at-risk'. But found_on frequently records a NON-CANONICAL URL of a
page (/node/N, /index.php/..) whose canonical form IS in the sitemap and links
the same file. Those files are fully recoverable; they only look at-risk.

METHOD (the sample-test the pattern needs): for a sample of at-risk docs per
host, fetch the found_on page, follow redirects, and classify by the FINAL URL:
  - final base IN sitemap        -> RECOVERABLE (found_on was a dupe/alias)
  - final base NOT in sitemap, 200 -> TRUE ORPHAN (real page the sitemap omits)
  - final 404 / error            -> DEAD referrer (file likely stale too)

The recoverable rate lets us scale the corpus at-risk counts down to a true
file-loss estimate. Read-only; Tier 2 curl_cffi. LOCAL/non-AWS IP (existence +
redirect facts are IP-independent; production reachability from AWS unproven).
"""
import asyncio
import json
import os
import re
import sqlite3
import xml.etree.ElementTree as ET
from collections import Counter
from urllib.parse import urljoin, urlparse, urlunparse

from curl_cffi.requests import AsyncSession

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_ROOT = "/Users/kevingray/codebase/harvard-atg/apo-mcp-server/data"
OUT_JSON = os.path.join(HERE, "atrisk_sample.json")
OUT_MD = os.path.join(HERE, "ATRISK_SAMPLE.md")

TIMEOUT = 20
CONCURRENCY = 10
SAMPLE_PER_HOST = 40
REAL_FILE = re.compile(r"\.(pdf|docx?|xlsx?|pptx?)$", re.I)

# hosts with material at-risk doc counts (from summary.json), worst first
HOSTS = [
    "www.economics.harvard.edu", "history.fas.harvard.edu",
    "sociology.fas.harvard.edu", "statistics.fas.harvard.edu",
    "linguistics.fas.harvard.edu", "english.fas.harvard.edu",
    "astronomy.fas.harvard.edu", "anthropology.fas.harvard.edu",
    "ofa.fas.harvard.edu", "dso.college.harvard.edu",
]


def _local(tag):
    return tag.rsplit("}", 1)[-1].lower()


def norm_base(u):
    if not u:
        return ""
    p = urlparse(u.strip())
    path = p.path.rstrip("/") or "/"
    return urlunparse(("https", p.netloc.lower(), path, "", "", ""))


async def _get(session, url):
    try:
        r = await session.get(url, impersonate="chrome", timeout=TIMEOUT,
                              allow_redirects=True)
        return r.status_code, r.content, str(r.url)
    except Exception:
        return None, None, None


def _parse_locs(body):
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return [], []
    if _local(root.tag) == "sitemapindex":
        return ([loc.text.strip() for sm in root if _local(sm.tag) == "sitemap"
                 for loc in sm if _local(loc.tag) == "loc" and loc.text], [])
    if _local(root.tag) == "urlset":
        return ([], [loc.text.strip() for u in root if _local(u.tag) == "url"
                     for loc in u if _local(loc.tag) == "loc" and loc.text])
    return [], []


async def discover_sitemap(session, host):
    base = f"https://{host}"
    candidates = []
    st, body, _ = await _get(session, urljoin(base, "/robots.txt"))
    if st == 200 and body:
        for line in body.decode("utf-8", "ignore").splitlines():
            m = re.match(r"\s*sitemap:\s*(\S+)", line, re.IGNORECASE)
            if m:
                candidates.append(m.group(1).strip())
    for path in ("/sitemap.xml", "/sitemap_index.xml", "/wp-sitemap.xml"):
        candidates.append(urljoin(base, path))
    for sm_url in candidates:
        st, body, _ = await _get(session, sm_url)
        if st != 200 or not body:
            continue
        children, pages = _parse_locs(body)
        urls = set(pages)
        for child in children:
            cst, cbody, _ = await _get(session, child)
            if cst == 200 and cbody:
                _, cpages = _parse_locs(cbody)
                urls.update(cpages)
        if urls:
            return {norm_base(u) for u in urls}
    return set()


def at_risk_docs(host, sm_base):
    """Docs (real files) whose found_on base is set but NOT in sitemap."""
    db = os.path.join(DATA_ROOT, host, "logs", "state.db")
    conn = sqlite3.connect(db)
    rows = conn.execute("SELECT url, found_on FROM visited").fetchall()
    conn.close()
    out = []
    for url, found_on in rows:
        if not REAL_FILE.search(urlparse(url).path):
            continue
        if norm_base(url) in sm_base:
            continue  # file itself in sitemap
        if not found_on:
            continue  # null bucket, separate concern
        if norm_base(found_on) in sm_base:
            continue  # already counted recoverable
        out.append((url, found_on))
    return out


async def process(host, sem):
    async with sem, AsyncSession() as s:
        sm_base = await discover_sitemap(s, host)
        if not sm_base:
            return {"host": host, "status": "no_sitemap"}
        items = at_risk_docs(host, sm_base)
        total = len(items)
        # deterministic sample: sort by url, take head + evenly spaced tail
        items.sort(key=lambda x: x[0])
        if total > SAMPLE_PER_HOST:
            step = total / SAMPLE_PER_HOST
            sample = [items[int(i * step)] for i in range(SAMPLE_PER_HOST)]
        else:
            sample = items
        buckets = Counter()
        examples = {"recoverable": [], "true_orphan": [], "dead": []}
        for file_url, found_on in sample:
            st, _, final = await _get(s, found_on)
            if st is None:
                buckets["dead/error"] += 1
                if len(examples["dead"]) < 6:
                    examples["dead"].append({"file": file_url, "found_on": found_on})
            elif st >= 400:
                buckets["dead/error"] += 1
                if len(examples["dead"]) < 6:
                    examples["dead"].append({"file": file_url, "found_on": found_on,
                                             "status": st})
            elif norm_base(final) in sm_base:
                buckets["recoverable (found_on -> sitemap page)"] += 1
                if len(examples["recoverable"]) < 6:
                    examples["recoverable"].append(
                        {"file": file_url, "found_on": found_on, "final": final})
            else:
                buckets["true_orphan (real page, sitemap omits)"] += 1
                if len(examples["true_orphan"]) < 6:
                    examples["true_orphan"].append(
                        {"file": file_url, "found_on": found_on, "final": final})
        n = sum(buckets.values()) or 1
        rec = buckets["recoverable (found_on -> sitemap page)"]
        orphan = buckets["true_orphan (real page, sitemap omits)"]
        return {
            "host": host, "status": "ok",
            "at_risk_total": total, "sampled": len(sample),
            "buckets": dict(buckets),
            "recoverable_rate": round(rec / n, 3),
            "true_orphan_rate": round(orphan / n, 3),
            "est_true_orphans": round(total * orphan / n),
            "examples": examples,
        }


def write_md(results):
    lines = ["# At-risk document canonicalization sample\n",
             "Resolves whether corpus 'at-risk' docs are real orphans or found_on "
             "artifacts (non-canonical /node//index.php referrers whose canonical "
             "IS in the sitemap). Sample fetches found_on, follows redirects.\n",
             "| Host | At-risk total | Sampled | Recoverable | True-orphan | Dead | "
             "Est. true orphans |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for r in sorted([x for x in results if x.get("status") == "ok"],
                    key=lambda x: -x["at_risk_total"]):
        b = r["buckets"]
        lines.append(
            f"| {r['host']} | {r['at_risk_total']} | {r['sampled']} | "
            f"{r.get('recoverable_rate', 0):.0%} | {r.get('true_orphan_rate', 0):.0%} | "
            f"{b.get('dead/error', 0)} | {r['est_true_orphans']} |")
    lines.append("\n## Examples\n")
    for r in results:
        if r.get("status") != "ok":
            continue
        lines.append(f"### {r['host']}")
        for kind in ("true_orphan", "recoverable", "dead"):
            ex = r["examples"].get(kind, [])
            if ex:
                lines.append(f"**{kind}:**")
                for e in ex:
                    lines.append(f"- `{e.get('file','')}` <- `{e.get('found_on','')}`"
                                 + (f" -> `{e.get('final','')}`" if e.get('final') else ""))
        lines.append("")
    with open(OUT_MD, "w") as f:
        f.write("\n".join(lines) + "\n")


async def main():
    sem = asyncio.Semaphore(CONCURRENCY)
    results = await asyncio.gather(*(process(h, sem) for h in HOSTS))
    with open(OUT_JSON, "w") as f:
        json.dump(results, f, indent=2)
    write_md(results)
    print("DONE")
    for r in sorted([x for x in results if x.get("status") == "ok"],
                    key=lambda x: -x["at_risk_total"]):
        print(f"  {r['host']:<40} at-risk={r['at_risk_total']:>4} "
              f"recoverable={r.get('recoverable_rate',0):.0%} "
              f"true-orphan={r.get('true_orphan_rate',0):.0%} "
              f"est-orphans={r['est_true_orphans']}")
    print(f"Evidence: {OUT_MD}")


if __name__ == "__main__":
    asyncio.run(main())
