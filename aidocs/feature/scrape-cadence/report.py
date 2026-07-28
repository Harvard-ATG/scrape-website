"""Render the human-facing RECOMMENDATIONS.md from the per-host records: a
per-site table (frequency, mode, cadence, diff signal, baseline recency,
rationale), a corpus rollup (how many sites at each frequency / mode), and an
explicit no-sitemap callout so degraded hosts are visible rather than silently
defaulted. The Baseline column surfaces QA's manifest `generated_at` and flags a
stale baseline so a diff measured against ancient state is never hidden."""
from collections import Counter

from dateparse import parse_iso_date

FREQ_ORDER = ["weekly", "monthly", "quarterly", "semiannual"]
STALE_BASELINE_DAYS = 180   # a baseline older than this is flagged in the report


def _cadence_cell(rec):
    c = rec.get("cadence")
    if not c:
        return "—"
    iv = c.get("est_update_interval_days")
    iv_txt = f"~{iv}d" if iv is not None else "n/a"
    return f"{c.get('cadence_class')} ({iv_txt}, cov {c.get('lastmod_coverage')})"


def _diff_cell(rec):
    d = rec.get("diff")
    if not d:
        return "—"
    return f"+{d['new_since_scrape']} / -{d['gone_from_manifest']} / ~{d['changed_since_scrape']}"


def _baseline_cell(rec, run_dt):
    """QA baseline date + its age, flagged when stale, so a diff measured
    against an old/blocked baseline is visible rather than silently trusted."""
    d = rec.get("diff")
    if not d or not d.get("baseline_known") or not d.get("baseline_date"):
        return "⚠ none"
    bd = d["baseline_date"]
    bdate = parse_iso_date(bd)
    if run_dt is not None and bdate is not None:
        age = (run_dt - bdate).days
        if age > STALE_BASELINE_DAYS:
            return f"{bd} (⚠ {age}d stale)"
        return f"{bd} ({age}d)"
    return bd


def render_report(records: list, run_date: str) -> str:
    run_dt = parse_iso_date(run_date)
    lines = [
        "# Scrape Cadence Recommendations",
        "",
        f"**Generated:** {run_date}  |  **Sites:** {len(records)}",
        "",
        "Per-site scrape frequency + mode grounded in live-sitemap `<lastmod>` "
        "cadence and the delta vs. QA's last-scraped `manifest.json`. "
        "Diff column is `+new / -gone / ~changed` (BASE-normalized page counts); "
        "Baseline column is QA's manifest `generated_at` (with age) and flags a "
        f"baseline older than {STALE_BASELINE_DAYS}d as `⚠ stale`.",
        "",
        "## Recommendations",
        "",
        "| Host | Frequency | Mode | Cadence | Diff (+/-/~) | Baseline | Rationale |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in sorted(records, key=lambda x: x["host"]):
        rec = r["recommendation"]
        lines.append(
            f"| {r['host']} | {rec['frequency']} | {rec['mode']} | "
            f"{_cadence_cell(r)} | {_diff_cell(r)} | {_baseline_cell(r, run_dt)} | "
            f"{rec['rationale']} |"
        )

    freq = Counter(r["recommendation"]["frequency"] for r in records)
    mode = Counter(r["recommendation"]["mode"] for r in records)
    lines += ["", "## Corpus rollup", "", "**By frequency:**"]
    for f in FREQ_ORDER:
        if freq.get(f):
            lines.append(f"- {f}: {freq[f]}")
    lines += ["", "**By mode:**",
              f"- fresh: {mode.get('fresh', 0)}",
              f"- incremental: {mode.get('incremental', 0)}"]

    no_sm = [r for r in records if r["status"] == "no_sitemap"]
    errored = [r for r in records if r["status"] == "error"]
    if no_sm:
        lines += ["", "## No sitemap — fixed conservative schedule", ""]
        for r in sorted(no_sm, key=lambda x: x["host"]):
            lines.append(f"- {r['host']} — {r['recommendation']['frequency']} / {r['recommendation']['mode']}")
    if errored:
        lines += ["", "## Errors (host isolated, not analyzed)", ""]
        for r in sorted(errored, key=lambda x: x["host"]):
            lines.append(f"- {r['host']}")
    return "\n".join(lines) + "\n"
