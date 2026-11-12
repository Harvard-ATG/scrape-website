"""
AWS /sitemap-llm probe — runs INSIDE the ECS task so egress uses the
Akamai-gated NAT IP. For each host in sites.toml, fetch the fixed path
``/sitemap-llm`` two ways — Tier 1 (plain urllib) and Tier 2 (curl_cffi chrome
impersonation) — recording status, content-type, bytes, and the count of URLs
in the body. Answers two questions the local check cannot: (1) which hosts
expose an LLM sitemap, and (2) whether it survives Akamai from the production
NAT (the same gate that 403s the regular sitemap.xml on 51/83 hosts).
Results go to S3 (container logs are Splunk-only).
"""
import concurrent.futures as cf
import json
import re
import sys
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
PATH = "/sitemap-llm"
BUCKET = "atg-apo-mcp-qa-scrape"
KEY = "_sitemap_reachability/result_llm.json"
TIMEOUT = 30


def parse_hosts(path="sites.toml"):
    hosts = []
    seen = set()
    with open(path) as f:
        for line in f:
            s = line.strip()
            if s.startswith("#"):
                continue
            m = re.match(r'hostname\s*=\s*"([^"]+)"', s)
            if m and m.group(1) not in seen:
                seen.add(m.group(1))
                hosts.append(m.group(1))
    return hosts


def tier1_get(url):
    """Plain urllib — proxy for the scraper's Tier 1 (naive client)."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.getcode(), r.headers.get("Content-Type", ""), r.read()


def tier2_get(url):
    """curl_cffi chrome impersonation — the scraper's Tier 2 (beats Akamai)."""
    from curl_cffi import requests as creq
    r = creq.get(url, impersonate="chrome", timeout=TIMEOUT, allow_redirects=True)
    return r.status_code, r.headers.get("Content-Type", ""), r.content


def status_of(fn, url):
    try:
        code, ctype, body = fn(url)
        return {"status": code, "ctype": ctype, "bytes": len(body),
                "body": body if code == 200 else b""}
    except urllib.error.HTTPError as e:
        return {"status": e.code, "ctype": "", "bytes": 0, "body": b""}
    except Exception as e:
        return {"status": None, "ctype": "", "error": f"{type(e).__name__}: {e}"[:200], "body": b""}


def probe(host):
    url = f"https://{host}{PATH}"
    t1 = status_of(tier1_get, url)
    t2 = status_of(tier2_get, url)
    body = t2["body"] or t1["body"]
    ctype = (t2.get("ctype") or t1.get("ctype") or "")
    # A real LLM sitemap is markdown; count distinct http(s) URLs in it.
    url_count = None
    is_markdown = None
    if body:
        is_markdown = "markdown" in ctype.lower()
        url_count = len(set(re.findall(rb"https?://[^\s)>\"']+", body)))
    return {
        "host": host,
        "url": url,
        "tier1": t1["status"],
        "tier2": t2["status"],
        "content_type": ctype,
        "bytes": max(t1["bytes"], t2["bytes"]),
        "url_count": url_count,
        "is_markdown": is_markdown,
        "has_llm_sitemap": bool(body) and bool(is_markdown),
    }


def main():
    hosts = parse_hosts()
    print(f"probing {len(hosts)} hosts for {PATH}", flush=True)
    results = []
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        for r in ex.map(probe, hosts):
            results.append(r)
            print(f"  {r['host']:45s} t1={r['tier1']} t2={r['tier2']} "
                  f"llm={r['has_llm_sitemap']} urls={r['url_count']}", flush=True)

    have = [r for r in results if r["has_llm_sitemap"]]
    t1_ok = sum(1 for r in have if r["tier1"] == 200)
    summary = {
        "total": len(results),
        "path": PATH,
        "have_llm_sitemap": len(have),
        "llm_tier1_200": t1_ok,
        "llm_needed_tier2": len(have) - t1_ok,
        "llm_hosts": [r["host"] for r in have],
        "results": results,
    }

    import boto3
    boto3.client("s3").put_object(
        Bucket=BUCKET, Key=KEY,
        Body=json.dumps(summary, indent=2).encode(),
        ContentType="application/json",
    )
    print(f"WROTE s3://{BUCKET}/{KEY}", flush=True)
    print(f"SUMMARY have_llm={len(have)}/{len(results)} "
          f"tier1_200={t1_ok} needed_tier2={len(have) - t1_ok}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
