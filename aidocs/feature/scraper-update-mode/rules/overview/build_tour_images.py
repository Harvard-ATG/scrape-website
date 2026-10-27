"""Generate the code-tour images (SVG, then PNG copies) into ./tour/.

Sized for the narrow CodeTour side panel: 640 units wide, 12 to 16 px text, a fixed light palette on a white card so
they read on any editor theme. Run:  python3 build_tour_images.py   (PNG step needs macOS qlmanage; skipped elsewhere)

Numbers come from the July QA manifests, the 2026-10-15 sitemaps and rules/report/summary.json (see PRESENTATION_NOTES.md).
"""
import html, math, os, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "tour")
W = 640
SANS = '-apple-system, "Segoe UI", system-ui, Helvetica, Arial, sans-serif'
MONO = 'ui-monospace, Menlo, Consolas, monospace'
C = dict(line="#C6D0D8", fg="#15212B", muted="#4F5D6A", acc="#0A6B8D", accs="#DCEFF6", warn="#955700",
         warns="#FBEBD1", chip="#E7EDF1", arrow="#4A5864", card="#FFFFFF")
STYLE = f"""
.t{{font:600 14px {SANS};fill:{C['fg']}}} .s{{font:400 12px {SANS};fill:{C['muted']}}} .f{{font:400 12px {SANS};fill:{C['fg']}}}
.m{{font:400 11px {MONO};fill:{C['fg']}}} .ta{{font:600 14px {SANS};fill:{C['acc']}}} .tw{{font:600 12.5px {SANS};fill:{C['warn']}}}
.h{{font:700 16px {SANS};fill:{C['fg']}}} .l{{font:500 10.5px {MONO};fill:{C['muted']}}} .n{{font:700 12px {MONO};fill:#fff}}
.b{{fill:{C['card']};stroke:{C['line']};stroke-width:1.5}} .ba{{fill:{C['accs']};stroke:{C['acc']};stroke-width:1.6}}
.bw{{fill:{C['warns']};stroke:{C['warn']};stroke-width:1.6}} .bg{{fill:{C['chip']};stroke:{C['line']};stroke-width:1.5}}
.d{{stroke-dasharray:6 4}} .ln{{stroke:{C['arrow']};stroke-width:1.7;fill:none}} .lna{{stroke:{C['acc']};stroke-width:1.9;fill:none}}
.lnw{{stroke:{C['warn']};stroke-width:1.5;fill:none;stroke-dasharray:3 3}} .grid{{stroke:{C['line']};stroke-width:1;stroke-dasharray:2 4}}
.mk{{fill:{C['arrow']}}} .mka{{fill:{C['acc']}}} .dot{{fill:{C['acc']}}} .dotw{{fill:{C['warn']}}}
"""
esc = lambda s: html.escape(s, quote=False)


def T(x, y, s, cls="s", anchor=None):
    a = f' text-anchor="{anchor}"' if anchor else ""
    return f'<text class="{cls}" x="{x}" y="{y}"{a}>{esc(s)}</text>'


def box(x, y, w, h, kind="b", title=None, lines=(), dash=False, tcls="t", pad=12):
    o = [f'<rect class="{kind}{" d" if dash else ""}" x="{x}" y="{y}" width="{w}" height="{h}" rx="8"/>']
    ty = y + 22
    if title:
        o.append(T(x + pad, ty, title, tcls)); ty += 18
    for ln in lines:
        o.append(T(x + pad, ty, ln, "s")); ty += 16
    return "".join(o)


def arrow(x1, y1, x2, y2, kind="ln"):
    m = "ara" if kind == "lna" else "ar"
    return f'<line class="{kind}" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" marker-end="url(#{m})"/>'


def svg(h, body, label):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {h}" width="{W}" height="{h}" role="img" '
            f'aria-label="{esc(label)}"><defs>'
            f'<marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path class="mk" d="M0,0 L10,5 L0,10 z"/></marker>'
            f'<marker id="ara" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path class="mka" d="M0,0 L10,5 L0,10 z"/></marker>'
            f'</defs><style>{STYLE}</style><rect x="0.75" y="0.75" width="{W-1.5}" height="{h-1.5}" rx="10" fill="#fff" stroke="{C["line"]}"/>{body}</svg>')


def badge(x, y, ch, cls="dotw"):
    return f'<circle class="{cls}" cx="{x}" cy="{y}" r="11"/>' + f'<text class="n" x="{x}" y="{y+4}" text-anchor="middle">{ch}</text>'


IMAGES = {}
SIZES = {}
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def image(name, label):
    def deco(fn):
        h, body = fn()
        IMAGES[name] = svg(h, body, label)
        SIZES[name] = h
        return fn
    return deco


# 01 -------------------------------------------------------------------------------------------------------
@image("01-today-flow", "How a scrape works today: entry, crawl, fetch, save, manifest and S3, ingest, with three problems marked A, B and C.")
def _():
    b = [T(20, 28, "How a scrape works today", "h")]
    rows = [("sites.toml entry", "seed URL and scope rules"), ("Crawl", "follow links on one host, random order"),
            ("Fetch", "3 tiers: plain, browser-like, Playwright"), ("Save", "pages, text, files, state.db rows"),
            ("Manifest and S3", "written only if the crawl is complete"), ("Ingest", "unchanged: skip   ·   missing: retire")]
    ys = [48 + i * 78 for i in range(6)]
    for (t, s), y in zip(rows, ys):
        b.append(box(20, y, 300, 56, "b", t, [s]))
    for y in ys[:-1]:
        b.append(arrow(170, y + 56, 170, y + 77))
    notes = {1: ("A", ["Crawl order is random:", "45 to 136 pages on one site"]),
             3: ("B", ["A normal run never refreshes", "a changed page"]),
             5: ("C", ["Missing from the crawl", "means retired, unchecked"])}
    for i, (ch, ls) in notes.items():
        y = ys[i]
        b.append(f'<line class="lnw" x1="320" y1="{y+28}" x2="346" y2="{y+28}"/>')
        b.append(box(346, y, 274, 56, "bw", None, [], False))
        b.append(badge(366, y + 28, ch))
        b.append(T(386, y + 24, ls[0], "tw")); b.append(T(386, y + 42, ls[1], "tw"))
    b.append(T(20, 540, "Normal run: adds new pages only.   Fresh run (--fresh): re-crawls everything.", "s"))
    return 556, "".join(b)


# 02 -------------------------------------------------------------------------------------------------------
@image("02-cleaner-full-scrape", "Of 143,477 saved pages, PR 10 removes or merges 73,101 (50.9%): 39,193 twin URLs, 23,896 search pages, 10,012 calendar feeds; 19,823 query strings are pending a rule and 50,553 are kept.")
def _():
    segs = [(39193, "27.3%", "Twin URLs merged into one (http vs https, trailing slash)", "acc", 1.0),
            (23896, "16.7%", "Search result pages dropped", "acc", .78),
            (10012, "7.0%", "Calendar feeds (.ics) dropped", "acc", .58),
            (19823, "13.8%", "Query strings: decided, rule not written yet", "warn", 1),
            (50553, "35.2%", "Kept: real pages and files", "grey", 1)]
    total = 143477; scale = 600 / total
    b = [T(20, 26, "A cleaner full scrape: 143,477 saved pages", "h")]
    x = 20; edge = []
    for n, p, lab, kind, op in segs:
        w = n * scale
        fill = {"acc": f'style="fill:{C["acc"]};opacity:{op}"', "warn": f'style="fill:{C["warns"]};stroke:{C["warn"]};stroke-width:1.5"',
                "grey": f'style="fill:{C["chip"]};stroke:{C["line"]};stroke-width:1.5"'}[kind]
        b.append(f'<rect x="{x:.1f}" y="66" width="{w:.1f}" height="44" {fill}/>')
        edge.append((x, w)); x += w
    b.append(f'<line class="ln" x1="20" y1="58" x2="{20+(39193+23896+10012)*scale:.1f}" y2="58"/>')
    b.append(T(20, 50, "PR #10 removes or merges 73,101 pages (50.9%)", "tw"))
    y = 140
    for (n, p, lab, kind, op), (x0, w) in zip(segs, edge):
        sw = {"acc": f'style="fill:{C["acc"]};opacity:{op}"', "warn": f'style="fill:{C["warns"]};stroke:{C["warn"]};stroke-width:1.5"',
              "grey": f'style="fill:{C["chip"]};stroke:{C["line"]};stroke-width:1.5"'}[kind]
        b.append(f'<rect x="20" y="{y-11}" width="16" height="16" rx="3" {sw}/>')
        b.append(T(46, y + 2, f"{n:,}  ·  {p}", "t")); b.append(T(190, y + 2, lab, "f"))
        y += 30
    b.append(T(20, 310, "e.g.  linguistics.fas…/search?page=0   ·   socialstudies.fas…/node/1127886/event-feed.ics", "m"))
    b.append(T(20, 330, "Counts are pages saved in the July manifests, not pages uploaded to the vector store.", "s"))
    return 348, "".join(b)


# 03 -------------------------------------------------------------------------------------------------------
@image("03-sitemap-kinds", "Three kinds of sitemap file: the XML sitemap has last-modified dates; the markdown sitemap and per-page .md copies do not.")
def _():
    b = [T(20, 28, "Three kinds of sitemap file", "h")]
    rows = [("XML sitemap", "/sitemap.xml  ·  79 of 83 hosts", "<lastmod>2025-06-06T21:49:27+00:00</lastmod>", "has dates", "ba"),
            ("Markdown sitemap", "/sitemap-llm  ·  52 hosts (Drupal 10)", "- [Contact](https://haa.fas…/contact.md)", "no dates", "bg"),
            ("Per-page .md copy", "page URL + .md  ·  the same 52 hosts", "response dates are the render time", "no dates", "bg")]
    y = 48
    for t, s, ex, chip, kind in rows:
        b.append(box(20, y, 600, 74, kind, t, [s], False, "ta" if kind == "ba" else "t"))
        b.append(T(32, y + 66, ex, "m"))
        cw = 82
        b.append(f'<rect x="{620-cw-12}" y="{y+12}" width="{cw}" height="24" rx="12" style="fill:{C["acc"] if chip=="has dates" else "#fff"};stroke:{C["acc"] if chip=="has dates" else C["line"]};stroke-width:1.5"/>')
        b.append(T(620 - cw / 2 - 12, y + 28, chip, "n" if chip == "has dates" else "s", "middle"))
        y += 88
    b.append(T(20, 322, "Only the XML sitemap can say what changed.", "t"))
    return 340, "".join(b)


# 04 -------------------------------------------------------------------------------------------------------
@image("04-update-flow", "Proposed update run: entry, scope rules, read the sitemap, plan, fetch only the plan, save, record state, ingest.")
def _():
    b = [T(20, 28, "Proposed: an update run", "h")]
    rows = [("sites.toml entry", "same as today", False), ("Scope rules", "host, seed path, include, exclude", False),
            ("Read the sitemap", "every URL with its last-modified date", True), ("Plan", "compare each date with what is stored", True),
            ("Fetch only the plan", "same tiered fetcher as today", False), ("Save", "changed pages replaced, unchanged kept", False),
            ("Record state", "date and fetch time per URL", True), ("Ingest", "unchanged: hash skip", False)]
    ys = [46 + i * 74 for i in range(8)]
    for (t, s, new), y in zip(rows, ys):
        b.append(box(20, y, 300, 54, "ba" if new else "b", t, [s], new, "ta" if new else "t"))
    for y in ys[:-1]:
        b.append(arrow(170, y + 54, 170, y + 73, "lna" if y in (ys[1], ys[2]) else "ln"))
    b.append(f'<line class="lnw" x1="320" y1="{ys[1]+27}" x2="346" y2="{ys[1]+27}"/>')
    b.append(box(346, ys[1], 274, 54, "bw", None)); b.append(T(358, ys[1] + 24, "tiny path-scoped section:", "tw")); b.append(T(358, ys[1] + 42, "refetch the seeds only (R10)", "tw"))
    b.append(f'<line class="lnw" x1="320" y1="{ys[2]+27}" x2="346" y2="{ys[2]+27}"/>')
    b.append(box(346, ys[2], 274, 54, "bw", None)); b.append(T(358, ys[2] + 24, "unreadable, or lists another host:", "tw")); b.append(T(358, ys[2] + 42, "skip the host (R11, R12)", "tw"))
    chips = [("unchanged → skip", "bg", "s"), ("never captured → backfill", "bw", "tw"), ("new → fetch", "ba", "f"), ("changed → fetch", "ba", "f"), ("no date → fetch every run", "ba", "f")]
    cy = ys[3] - 6
    b.append(T(346, cy - 6, "THE PLAN SORTS EVERY URL", "l"))
    for lab, kind, cls in chips:
        b.append(f'<rect class="{kind} d" x="346" y="{cy}" width="274" height="26" rx="6"/>' + T(358, cy + 17, lab, cls)); cy += 30
    b.append(f'<line class="lna" x1="346" y1="{ys[3]+27}" x2="321" y2="{ys[3]+27}" marker-end="url(#ara)"/>')
    b.append(f'<rect class="b" x="20" y="{ys[7]+72}" width="16" height="12" rx="3"/>' + T(44, ys[7] + 82, "already in the scraper", "s"))
    b.append(f'<rect class="ba d" x="210" y="{ys[7]+72}" width="16" height="12" rx="3"/>' + T(234, ys[7] + 82, "new in this design: reference code and tests, not wired in", "s"))
    return ys[7] + 100, "".join(b)


# 05 -------------------------------------------------------------------------------------------------------
@image("05-url-gates", "A sitemap URL passes five gates (normalize, host, seed path, include, exclude) and ends as new, changed, no date, unchanged or never captured.")
def _():
    b = [T(20, 28, "What happens to one URL", "h")]
    b.append(f'<rect class="bg" x="20" y="42" width="300" height="28" rx="14"/>' + T(170, 61, "A URL from the sitemap", "t", "middle"))
    gates = [("Normalize (R1)", "https, no trailing slash", None), ("Same host? (R2)", "exact host name", "no: another host"),
             ("Inside the seed path? (R3)", "path-scoped entries only", "no: outside the path"),
             ("Include pattern? (R4)", "entries with patterns only", "no: nothing matched"),
             ("Hits an exclude? (R5 R6 R7)", "tags, /page/N, feeds, search, events", "yes: excluded")]
    ys = [88 + i * 64 for i in range(5)]
    b.append(arrow(170, 70, 170, 87))
    for (t, s, ex), y in zip(gates, ys):
        b.append(box(20, y, 300, 46, "b", t, [s]))
        if ex:
            b.append(f'<line class="lnw" x1="320" y1="{y+23}" x2="346" y2="{y+23}"/>' + box(346, y + 5, 274, 36, "bw", None))
            b.append(T(358, y + 28, ex, "tw"))
    for y in ys[:-1]:
        b.append(arrow(170, y + 46, 170, y + 63))
    yb = ys[-1] + 46
    b.append(arrow(170, yb, 170, yb + 22, "lna")); b.append(T(186, yb + 17, "compare with what is stored (R13)", "l"))
    outs = [("New", "not stored, date after baseline", "→ fetch", "ba"), ("Changed", "stored date differs", "→ fetch", "ba"), ("No date", "sitemap gives none", "→ fetch each run", "ba"),
            ("Unchanged", "same date as stored", "→ keep", "bg"), ("Never captured", "not stored, old date", "→ backfill list (R20)", "bw")]
    y0 = yb + 30
    pos = [(20, y0), (226, y0), (432, y0), (20, y0 + 80), (226, y0 + 80)]
    for (t, s, r, kind), (x, y) in zip(outs, pos):
        b.append(box(x, y, 194, 68, kind, t, [s], False, "ta" if kind == "ba" else ("tw" if kind == "bw" else "t")))
        b.append(T(x + 12, y + 62, r, "t" if kind != "bw" else "tw"))
    return y0 + 80 + 68 + 16, "".join(b)


# 06 -------------------------------------------------------------------------------------------------------
@image("06-moved-host", "When a host moves, its old sitemap lists only the new host's pages; without a check that looks like 1,377 deleted pages; rule R12 blocks the host instead.")
def _():
    b = [T(20, 28, "A site moved: gone, or moved?", "h")]
    b.append(box(20, 44, 290, 176, "bw", "Without a check", [], False, "tw"))
    for i, l in enumerate(["July: oie.fas sitemap lists", "oie.fas pages.", "October: it lists only", "studyabroad.college pages.", "", "Looks like every page vanished:", "1,377 \"departures\" on 4 hosts."]):
        b.append(T(32, 86 + i * 17, l, "f" if i != 5 and i != 6 else "tw"))
    b.append(box(330, 44, 290, 176, "ba", "With rule R12", [], False, "ta"))
    for i, l in enumerate(["host_moved(): the whole URL set", "changed host.", "plan.blocked =", "\"sitemap_foreign_host\"", "", "No fetches and no removals", "for the old host."]):
        b.append(T(342, 86 + i * 17, l, "f" if i not in (5, 6) else "t"))
    b.append(T(20, 246, "The four moves (sites.toml now lists the new hosts):", "t"))
    moves = [("oie.fas.harvard.edu", "studyabroad.college.harvard.edu"), ("summerfunding.college.harvard.edu", "sfsao.college.harvard.edu"),
             ("incomingstudents.college.harvard.edu", "firstyear.college.harvard.edu"), ("oaisc.fas.harvard.edu", "secretary.college.harvard.edu")]
    for i, (o, n) in enumerate(moves):
        y = 270 + i * 22
        b.append(T(24, y, o, "m")); b.append(T(300, y, "→", "t", "middle")); b.append(T(320, y, n, "m"))
    b.append(T(20, 376, "Still open: the files already ingested under the old host names.", "s"))
    return 394, "".join(b)


# 07 -------------------------------------------------------------------------------------------------------
@image("07-deletion", "Deleting a page: today a full crawl's missing pages are retired by ingest; proposed, sitemap departures pass guards and a confirmation fetch first.")
def _():
    b = [T(20, 28, "Deleting a page", "h"), T(20, 52, "Today: the crawl decides", "t"), T(330, 52, "Proposed: the sitemap decides", "ta")]
    left = [("Full (fresh) crawl", ["finds some pages,", "misses others"]), ("Files on disk = active set", ["ingest reads the host's folders"]),
            ("Ingest compares", ["records not in the set", "are retired"]), ("Retired", ["soft: hidden from search", "(hard delete only if flagged)"])]
    for i, (t, ls) in enumerate(left):
        y = 62 + i * 98
        b.append(box(20, y, 290, 72, "b", t, ls))
        if i < 3: b.append(arrow(165, y + 72, 165, y + 97))
    right = [("Compare sitemap snapshots", ["today vs last saved, in scope"]), ("Departures (R15)", ["listed before, gone now"]),
             ("Guards (R11 R12 R15)", ["unreadable · moved · over 30% gone"]), ("Confirm by fetching (R16)", ["404/410 retire · 403 hold", "redirect follow · 200 keep · 5xx never"]),
             ("Retire after a clean run (R17)", ["complete and uncapped only"])]
    for i, (t, ls) in enumerate(right):
        y = 62 + i * 78
        kind = "bw" if i == 2 else "ba"
        b.append(box(330, y, 290, 66, kind, t, ls, True, "tw" if i == 2 else "ta"))
        if i < 4: b.append(arrow(475, y + 66, 475, y + 77, "lna"))
    b.append(box(20, 468, 290, 58, "bw", None)); b.append(T(32, 490, "A page the crawl missed is retired", "tw")); b.append(T(32, 508, "though it still exists.", "tw"))
    b.append(box(330, 468, 290, 58, "bg", None, [], True)); b.append(T(342, 490, "Pages never in a sitemap rely on", "s")); b.append(T(342, 508, "a monthly full refresh (R19).", "s"))
    return 544, "".join(b)


# 08 / 09 --------------------------------------------------------------------------------------------------
def bars(title, label, lo_decades, rows, ticks):
    x0 = 210; per = 102.5
    b = [T(20, 26, title, "h")]
    h = 56 + len(rows) * 52 + 40
    for i, tk in enumerate(ticks):
        x = x0 + per * i
        b.append(f'<line class="grid" x1="{x:.1f}" y1="40" x2="{x:.1f}" y2="{h-40}"/>')
        b.append(T(x, h - 24, tk, "l", "middle"))
    for i, (name, sub, v, kind) in enumerate(rows):
        y = 50 + i * 52
        w = per * math.log10(v / 10 ** lo_decades)
        b.append(T(20, y + 15, name, "t")); b.append(T(20, y + 32, sub, "s"))
        b.append(f'<rect x="{x0}" y="{y}" width="{w:.1f}" height="34" rx="3" style="fill:{C["acc"] if kind=="a" else C["line"]}"/>')
    b.append(T(620, h - 6, label, "l", "end"))
    return h, "".join(b)


@image("08-savings-one-host", "One host, english.fas.harvard.edu: a full re-crawl is 1,643 pages, an update's first run 69 and each week 16, on a log scale.")
def _():
    return bars("One host: english.fas.harvard.edu", "pages fetched, log scale", 0,
                [("Full re-crawl", "1,643 pages · 30 to 47 min", 1643, "g"), ("Update, first run", "69 pages · 1 to 2 min", 69, "a"), ("Update, each week", "16 pages · 20 to 30 s", 16, "a")],
                ["1", "10", "100", "1,000", "10,000"])


@image("09-savings-all-hosts", "All 71 hosts combined: a full re-crawl is 56,992 pages, an update's first run 4,339, each week 341 and each day about 50, on a log scale.")
def _():
    return bars("All 71 hosts combined", "pages fetched, log scale; hosts run back to back", 1,
                [("Full re-crawl", "56,992 pages · 17 to 27 h", 56992, "g"), ("Update, first run", "4,339 pages · 1.3 to 2 h", 4339, "a"),
                 ("Update, each week", "341 pages · 6 to 10 min", 341, "a"), ("Update, each day", "about 50 pages · 1 min", 50, "a")],
                ["10", "100", "1,000", "10,000", "100,000"])


# 10 -------------------------------------------------------------------------------------------------------
@image("10-test-modes", "The rules tests pass in three input modes: everything present 257 pass and 4 skip, sites.toml only 183 pass and 2 skip, neither 76 pass and 26 skip.")
def _():
    b = [T(20, 28, "The tests run with whatever inputs exist", "h")]
    b.append(T(24, 60, "INPUTS", "l")); b.append(T(330, 60, "RESULT", "l"))
    rows = [("sites.toml + cached manifests", "257 pass · 4 skip", "ba"), ("sites.toml, no manifests", "183 pass · 2 skip", "b"), ("neither (a clean clone)", "76 pass · 26 skip", "b")]
    for i, (a, r, k) in enumerate(rows):
        y = 70 + i * 62
        b.append(box(20, y, 600, 50, k, None)); b.append(T(34, y + 31, a, "t")); b.append(T(330, y + 31, r, "ta" if k == "ba" else "t"))
    b.append(T(20, 276, "Tests that need an absent input skip; they never fail for a missing file.", "s"))
    b.append(T(20, 296, "Repo's own tests (pytest at the root): 47 pass.", "s"))
    return 314, "".join(b)


# 11 -------------------------------------------------------------------------------------------------------
@image("11-plan-order", "The order of checks inside plan_update: tiny path-scoped section, unreadable sitemap, another host, per-URL scope and date comparison, never-captured list, seeds, departures.")
def _():
    b = [T(20, 28, "plan_update: the order of checks", "h")]
    rows = [("Tiny path-scoped section?", "refetch the seeds only (R10)"), ("Sitemap unreadable or empty?", "block the host (R11)"),
            ("Sitemap lists only another host?", "block the host (R12)"), ("For each URL: in scope?", "evaluate(): R2 to R9"),
            ("Compare the date with what is stored", "new · changed · no date · unchanged (R13, R13b)"),
            ("Not stored and not changed since the baseline?", "backfill list, not fetched (R20)"), ("Seeds", "always fetched (R9)"),
            ("Departures vs the last snapshot", "held if over 30% (R15)")]
    for i, (t, s) in enumerate(rows):
        y = 46 + i * 56
        b.append(f'<circle class="dot" cx="38" cy="{y+22}" r="13"/>' + T(38, y + 27, str(i + 1), "n", "middle"))
        if i < len(rows) - 1: b.append(f'<line class="ln" x1="38" y1="{y+35}" x2="38" y2="{y+55}"/>')
        b.append(box(64, y, 556, 44, "b" if i not in (1, 2) else "bw", t, [], False, "t" if i not in (1, 2) else "tw")); b.append(T(76, y + 38, s, "s"))
    return 46 + len(rows) * 56 + 8, "".join(b)


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, s in IMAGES.items():
        with open(os.path.join(OUT, name + ".svg"), "w", encoding="utf-8") as f:
            f.write(s)
    print(f"wrote {len(IMAGES)} SVG files to {OUT}")
    if os.path.exists(CHROME):          # headless Chrome renders like the editor's own browser engine
        prof = tempfile.mkdtemp()
        for name in IMAGES:
            png = os.path.join(OUT, name + ".png")
            cmd = [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=2",
                   f"--user-data-dir={prof}", f"--window-size={W},{SIZES[name]}", f"--screenshot={png}",
                   "file://" + os.path.join(OUT, name + ".svg")]
            for attempt in (1, 2):
                try:
                    subprocess.run(cmd, capture_output=True, timeout=45)
                    break
                except subprocess.TimeoutExpired:
                    print("retrying", name)
        print("PNG copies:", len([f for f in os.listdir(OUT) if f.endswith(".png")]))
    else:
        print("Chrome not found: PNG copies skipped (the SVG files are still written)")

if __name__ == "__main__":
    main()
