"""Run the update-mode reference rules offline on the 2026-10-15 sitemap fixtures and write traces-run.html.

No network, no scraper, no vector store. Inputs: rules/fixtures snapshots, sites.toml, cached QA manifests.
  MANIFEST_CACHE=<dir> SITES_TOML=<file> python trace_run.py
"""
import html, os, sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
RULES = HERE.parent / "rules"
sys.path[:0] = [str(RULES)]
from loaders import MOVED_HOSTS, SNAP_JUL, SNAP_OCT, load_manifest, load_sites, load_snapshot, sitemap_dict  # noqa: E402
from rules import classify_confirmation, evaluate, normalize_key, parse_lastmod, plan_update  # noqa: E402

SW = "https://github.com/Harvard-ATG/scrape-website/blob/a70def7326f47b25d0325744dff4e7c126870347/"
APO = "https://github.com/Harvard-ATG/apo-mcp-server/blob/37e6bfce3ee320f882b31a9738e8815048811bf9/"
e = html.escape
A_HOST, CAP_HOST, MOVED = "aaas.fas.harvard.edu", "ofa.fas.harvard.edu", "oie.fas.harvard.edu"

oct_, jul, sites = load_snapshot(SNAP_OCT), load_snapshot(SNAP_JUL), load_sites()


def run(host, entries):
    sm, prev = sitemap_dict(oct_.get(host)), sitemap_dict(jul.get(host))
    man = load_manifest(host)
    state, baseline = {}, None
    if man:
        ents, baseline = man
        for en in ents:
            if en.get("content_type") == "webpage" and "?" not in en["source_url"]:
                state[normalize_key(en["source_url"])] = {"lastmod": None}
    return sm, prev, state, baseline, plan_update(sm, state, host, entries, prev_sitemap=prev, baseline=baseline)


def link(path, line, text):
    return f'<a href="{SW if not path.startswith("apo:") else APO}{path.removeprefix("apo:")}#L{line}">{e(text)}</a>'


def table(head, rows):
    return ('<div class="tw"><table><thead><tr>' + "".join(f"<th>{h}</th>" for h in head) + "</tr></thead><tbody>"
            + "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows) + "</tbody></table></div>")


# ---------- Trace A: a changed page ----------
entries = sites[A_HOST]
sm, prev, state, baseline, plan = run(A_HOST, entries)
funnel = Counter()
for u in sm:
    d = evaluate(u, A_HOST, entries)
    funnel["in scope" if d.in_scope else "out of scope: " + d.reason] += 1
c = plan.counts()
changed = sorted(((k, sm.get(k) or sm.get(k + "/") or "") for k, r in plan.fetch.items() if r == "changed"))
new = sorted(k for k, r in plan.fetch.items() if r == "new")
sample_back = sorted(plan.backfill)[:5]

# ---------- Trace B: departures ----------
_, prevB, _, _, planB = run(A_HOST, entries)
_, _, _, _, planCap = run(CAP_HOST, sites[CAP_HOST])
_, _, _, _, planMoved = run(MOVED, [{"url": f"https://{MOVED}/"}])
conf = [(200, None), (404, None), (410, None), (403, None), (301, "https://example.edu/new"), (503, None), (None, None)]


# ---------- Sitemap versus no sitemap, every host ----------
cats = {}
for host, ents in sorted({**sites, **{o_: [{"url": f"https://{o_}/"}] for o_ in MOVED_HOSTS}}.items()):
    smh = sitemap_dict(oct_.get(host))
    p = plan_update(smh, {}, host, ents)
    if host in MOVED_HOSTS:
        cat = "5 moved: sitemap lists another host (R12)"
    elif host not in oct_:
        cat = "6 new hostname, no snapshot yet"
    elif p.blocked:
        cat = "4 no sitemap, blocked (R11)"
    elif not smh:
        cat = "3 no sitemap, seeds refetched (R10)"
    else:
        cov = sum(1 for v in smh.values() if v) / len(smh)
        cat = ("0 sitemap with dates" if cov >= 0.9 else "1 sitemap, partial dates" if cov > 0 else "2 sitemap, no dates")
    cats.setdefault(cat, []).append((host, len(smh or {}), p))
cat_note = {
 "0 sitemap with dates": "Normal planning: fetch new and changed pages, skip the rest.",
 "1 sitemap, partial dates": "Pages without a date are fetched every run; the rest are planned normally.",
 "2 sitemap, no dates": "Every page is fetched every run, so no saving over a full crawl of that host.",
 "3 no sitemap, seeds refetched (R10)": "Path-scoped host with a tiny section: only the seed pages are refetched each run. New pages inside are found only by the monthly full run.",
 "4 no sitemap, blocked (R11)": "Nothing is fetched and nothing is retired. The host is covered only by the monthly full run (R19).",
 "6 new hostname, no snapshot yet": "These replaced the four moved names; the 2026-10-15 snapshot has no record for them, so this is a gap in the input, not proof they lack a sitemap. Re-run the cadence fetch to include them.",
 "5 moved: sitemap lists another host (R12)": "Blocked, no removals; the entry in sites.toml must point at the new hostname.",
}
cat_rows = []
for k in sorted(cats):
    hs = cats[k]
    fetches = sum(len(p.fetch) for _, _, p in hs)
    names = ", ".join(h.removesuffix(".harvard.edu") for h, _, _ in hs) if len(hs) <= 12 else ", ".join(h.removesuffix(".harvard.edu") for h, _, _ in hs[:6]) + f", and {len(hs)-6} more"
    cat_rows.append([e(k[2:]), len(hs), e(cat_note[k]), f"<small>{e(names)}</small>"])

CSS = (HERE / "trace_run.css").read_text()
out = f"""<title>Trace Run</title>
<meta name="claude:viewport-fit-sides" content="cover">
<style>{CSS}</style>
<header class="top"><div class="wrap">
<p class="eyebrow">Harvard-ATG/scrape-website · PR #10 · offline run of the reference rules</p>
<h1>Trace run</h1>
<p class="lede">The two traces from the code tour, run for real on the 2026-10-15 sitemap snapshot, the 2026-07-28 snapshot and the cached QA manifests. Every number below is output of <code>rules.py</code>; nothing was crawled.</p>
<p class="warn"><b>Read this first:</b> this is the proposed planner running on saved data. The scraper does not call it yet, and no page was fetched, saved, ingested or retired. The confirmation statuses in Trace B are example inputs, not results of fetching.</p>
<nav><a href="#start">Commands</a><a href="#a">Trace A: changed page</a><a href="#b">Trace B: missing page</a><a href="#moved">Moved host</a><a href="#cap">Cap trips</a><a href="#sitemaps">Sitemap or not</a><a href="#reproduce">Reproduce</a></nav>
</div></header>
<main class="wrap">
<section id="start"><h2>Where each trace starts</h2>
{table(["Layer","Command","Source"],[
 ["Schedule","<code>scrape_and_ingest.py --all --mode full --workers 8</code> (disabled)",'<a href="https://github.com/Harvard-ATG/atg-ops-appserver/blob/24c065d7f356b6fe5facd79369871ebfc391a984/terraform/modules/apps/apo-mcp/main.tf#L203">main.tf:203</a>'],
 ["Manual","<code>run_scrape.py prod --hostname {A_HOST} --mode scrape</code>",'<a href="https://github.com/Harvard-ATG/atg-ops-appserver/blob/24c065d7f356b6fe5facd79369871ebfc391a984/apps/apo-mcp/run_scrape.py">run_scrape.py</a>'],
 ["Orchestrator","<code>scrape_and_ingest.py --hostname {A_HOST}</code>",link("apo:scrape_and_ingest.py",268,"scrape_and_ingest.py:268")],
 ["Per-site","<code>scrape.py --hostname {A_HOST}</code>",link("apo:scrape.py",60,"scrape.py:60")],
 ["Scraper","<code>scrape-website https://{A_HOST}/ --scope-to-path ...</code>",link("scrape_website/scraper.py",1575,"scraper.py:1575")]])}
<p>This page traces <code>{A_HOST}</code> through the <em>proposed</em> update path: an update flag would be forwarded down this ladder; it does not exist yet.</p></section>

<section id="a"><h2>Trace A: a changed page, host {A_HOST}</h2>
<h3>1. Entry in sites.toml</h3>
<pre class="code">{e(chr(10).join(f"url = {x['url']}" + ("".join(f", {k} = {v}" for k, v in x.items() if k != 'url')) for x in entries))}</pre>
<h3>2. Sitemap read: {len(sm):,} URLs, scope applied ({link("scrape_website/scraper.py",192,"_url_excluded")}, {link("aidocs/feature/scraper-update-mode/rules/rules.py",119,"evaluate")})</h3>
{table(["Result","URLs"],[[e(k),f"{v:,}"] for k,v in funnel.most_common()])}
<h3>3. Plan: {link("aidocs/feature/scraper-update-mode/rules/rules.py",167,"plan_update")} with the July manifest date as baseline ({baseline.date() if baseline else "none"}, R13b)</h3>
{table(["Outcome","Pages","Meaning"],[
 ["new",c.get("new",0),"in scope, not stored, dated after the baseline: fetch"],
 ["changed",c.get("changed",0),"stored, date later than the baseline: fetch"],
 ["no_lastmod",c.get("no_lastmod",0),"no date in the sitemap: always fetch"],
 ["skip",c.get("skip",0),"unchanged"],
 ["backfill",c.get("backfill",0),"never captured, kept out of normal runs (R20)"]])}
<h3>4. The pages it would fetch</h3>
{table(["Reason","Page","Sitemap lastmod"],[["changed",e(k),e(v)] for k,v in changed]+[["new",e(k),e(sm.get(k) or sm.get(k+"/") or "")] for k in new])}
<p>Sample of the {c.get("backfill",0):,} never-captured pages that stay out of the run: {", ".join("<code>"+e(k.split(".edu")[-1])+"</code>" for k in sample_back)}.</p>
<h3>5. Hand-off: what is missing between the plan and the scraper</h3>
<ul><li>{link("scrape_website/scraper.py",360,"_should_fetch")}: the gate exists, the plan is not connected.</li>
<li>{link("scrape_website/scraper.py",621,"upsert_metadata")}: no per-URL <code>lastmod</code> column, so the plan above used the manifest date as a stand-in.</li>
<li>{link("apo:ingest.py",324,"ingest.py:324")}: ingest would hash-compare each fetched page and upload only the ones that differ.</li></ul></section>

<section id="b"><h2>Trace B: a missing page, host {A_HOST}</h2>
<h3>1. Departures: in the 2026-07-28 snapshot, not in 2026-10-15 ({link("aidocs/feature/scraper-update-mode/rules/rules.py",248,"R15")})</h3>
<p>{len(planB.departures)} departure(s); removals held: <code>{e(str(planB.removal_blocked))}</code>.</p>
{table(["Departure candidate"],[[e(u)] for u in planB.departures] or [["none"]])}
<h3>2. A fetch decides ({link("aidocs/feature/scraper-update-mode/rules/rules.py",260,"classify_confirmation")})</h3>
<p>Example inputs, no fetch performed.</p>
{table(["HTTP status","Redirect","Decision"],[[str(s),e(l or ""),"<b>"+classify_confirmation(s,l)+"</b>"] for s,l in conf])}
<h3>3. Today in apo-mcp-server (outside the PR)</h3>
<p>{link("apo:ingest.py",71,"deprecate_removed_urls")} retires every record whose URL is not among the <code>.md</code> files on disk, with no cap and no confirmation. The proposed hand-off is the manifest, but ingest reads files on disk, so either the scraper deletes the file or ingest iterates the manifest.</p></section>

<section id="moved"><h2>A moved host: {MOVED}</h2>
<p>Plan result: <b>blocked: <code>{e(str(planMoved.blocked))}</code></b>, fetches {len(planMoved.fetch)}, departures {len(planMoved.departures)}. The sitemap now lists <code>{e(MOVED_HOSTS[MOVED])}</code>, so the planner skips the host and proposes no removals (R12).</p></section>

<section id="cap"><h2>The departure cap trips: {CAP_HOST}</h2>
<p>Plan result: removals held with <code>{e(str(planCap.removal_blocked))}</code>; fetches still planned: {len(planCap.fetch):,}. Proposed: raise a Sentry alert with the host, counts, sample URLs and links, and carry the entries forward.</p>
{table(["Sample of held departures"],[[e(u)] for u in planCap.departures[:5]] or [["(list is empty when held: the cap stops them being proposed)"]])}</section>

<section id="sitemaps"><h2>Hosts with a sitemap and hosts without</h2>
<p>Update mode lives on the sitemap: it is where the dates come from. Run on all {sum(len(v) for v in cats.values())} entries (83 hosts plus the 4 old moved names), with empty stored state:</p>
{table(["Kind of host","Hosts","What the planner does","Hosts"],cat_rows)}
<p>Two kinds of sitemap exist. The XML sitemap (<code>/sitemap.xml</code>, 79 of 83 hosts) has dates. The markdown <code>/sitemap-llm</code> (52 Drupal 10 hosts) lists pages and files with no dates, so it cannot say what changed. The snapshot records only "no sitemap", so it cannot tell a host with no sitemap from one that was unreadable (503) on the day; both are handled the same way.</p>
<p>Today, with no update mode, no host depends on a sitemap: the crawl follows links, and sitemap seeding is off in production unless <code>use_sitemap</code> is set (<code>scrape.py</code> passes False by default).</p></section>

<section id="reproduce"><h2>Reproduce</h2>
<pre class="code">cd aidocs/feature/scraper-update-mode/review
MANIFEST_CACHE=&lt;manifest-cache dir&gt; SITES_TOML=&lt;apo-mcp-server/sites.toml&gt; python trace_run.py</pre>
<p>Inputs: <code>rules/fixtures/sitemaps_2026-07-28.json.gz</code>, <code>sitemaps_2026-10-15.json.gz</code>, <code>sites.toml</code>, cached QA manifests. Output: <code>traces-run.html</code>.</p></section>
</main>"""
(HERE / "traces-run.html").write_text(out)
print("written", len(out), "| A:", c, "| dep:", len(planB.departures), planB.removal_blocked, "| cap:", planCap.removal_blocked, "| moved:", planMoved.blocked)
