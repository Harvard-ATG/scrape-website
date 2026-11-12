"""
AWS sitemap-reachability probe — runs INSIDE the ECS task so egress uses the
Akamai-gated NAT IP. For each host in sites.toml: discover the sitemap
(robots.txt Sitemap: -> /sitemap.xml -> /sitemap_index.xml -> /wp-sitemap.xml),
then fetch it two ways — Tier 1 (plain urllib) and Tier 2 (curl_cffi chrome
impersonation) — recording status, first-passing tier, bytes, and <loc> count.
Results go to S3 (container logs are Splunk-only, unreadable from the operator).
"""
import concurrent.futures as cf
import json
import re
import sys
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
CANDIDATES = ["/sitemap.xml", "/sitemap_index.xml", "/wp-sitemap.xml"]
BUCKET = "atg-apo-mcp-qa-scrape"
KEY = "_sitemap_reachability/result.json"
TIMEOUT = 25


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
        return r.getcode(), r.read()


def tier2_get(url):
    """curl_cffi chrome impersonation — the scraper's Tier 2 (beats Akamai)."""
    from curl_cffi import requests as creq
    r = creq.get(url, impersonate="chrome", timeout=TIMEOUT, allow_redirects=True)
    return r.status_code, r.content


def status_of(fn, url):
    try:
        code, body = fn(url)
        return {"status": code, "bytes": len(body), "body": body if code == 200 else b""}
    except urllib.error.HTTPError as e:
        return {"status": e.code, "bytes": 0, "body": b""}
    except Exception as e:
        return {"status": None, "error": f"{type(e).__name__}: {e}"[:200], "body": b""}


def discover_and_probe(host):
    base = f"https://{host}"
    urls = []
    # robots.txt Sitemap: directive first
    rob = status_of(tier2_get, f"{base}/robots.txt")
    if rob.get("body"):
        for m in re.finditer(rb"(?im)^\s*sitemap:\s*(\S+)", rob["body"]):
            urls.append(m.group(1).decode("utf-8", "replace").strip())
    urls += [base + c for c in CANDIDATES]

    result = {"host": host, "sitemap_url": None, "tier1": None, "tier2": None,
              "loc_count": None, "is_index": None, "reachable": False}
    for su in urls:
        t1 = status_of(tier1_get, su)
        t2 = status_of(tier2_get, su)
        body = t2["body"] or t1["body"]
        result["sitemap_url"] = su
        result["tier1"] = t1["status"]
        result["tier2"] = t2["status"]
        if body:
            result["is_index"] = b"<sitemapindex" in body[:2000].lower()
            result["loc_count"] = len(re.findall(rb"<loc>", body))
            result["reachable"] = True
            break
        # if both non-200 and not a "found but empty", try next candidate
        if t1["status"] == 200 or t2["status"] == 200:
            result["reachable"] = True
            break
    return result


def main():
    hosts = parse_hosts()
    print(f"probing {len(hosts)} hosts", flush=True)
    results = []
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        for r in ex.map(discover_and_probe, hosts):
            results.append(r)
            print(f"  {r['host']:45s} t1={r['tier1']} t2={r['tier2']} "
                  f"reach={r['reachable']} locs={r['loc_count']}", flush=True)

    reachable = sum(1 for r in results if r["reachable"])
    t1_ok = sum(1 for r in results if r["tier1"] == 200)
    blocked = [r["host"] for r in results if not r["reachable"]]
    summary = {
        "total": len(results),
        "reachable": reachable,
        "tier1_direct_200": t1_ok,
        "needed_tier2": reachable - t1_ok,
        "unreachable_hosts": blocked,
        "results": results,
    }

    import boto3
    boto3.client("s3").put_object(
        Bucket=BUCKET, Key=KEY,
        Body=json.dumps(summary, indent=2).encode(),
        ContentType="application/json",
    )
    print(f"WROTE s3://{BUCKET}/{KEY}", flush=True)
    print(f"SUMMARY reachable={reachable}/{len(results)} "
          f"tier1_direct={t1_ok} needed_tier2={reachable - t1_ok} "
          f"unreachable={len(blocked)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
