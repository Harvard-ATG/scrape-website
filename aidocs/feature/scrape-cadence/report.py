"""Render the human-facing RECOMMENDATIONS.md from the per-host records: a
per-site table (frequency, mode, cadence, diff signal, rationale), a corpus
rollup (how many sites at each frequency / mode), and an explicit no-sitemap
callout so degraded hosts are visible rather than silently defaulted."""
from collections import Counter

FREQ_ORDER = ["weekly", "monthly", "quarterly", "semiannual"]


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


def render_report(records: list, run_date: str) -> str:
    lines = [
        "# Scrape Cadence Recommendations",
        "",
        f"**Generated:** {run_date}  |  **Sites:** {len(records)}",
        "",
        "Per-site scrape frequency + mode grounded in live-sitemap `<lastmod>` "
        "cadence and the delta vs. QA's last-scraped `manifest.json`. "
        "Diff column is `+new / -gone / ~changed` (BASE-normalized page counts).",
        "",
        "## Recommendations",
        "",
        "| Host | Frequency | Mode | Cadence | Diff (+/-/~) | Rationale |",
        "|---|---|---|---|---|---|",
    ]
    for r in sorted(records, key=lambda x: x["host"]):
        rec = r["recommendation"]
        lines.append(
            f"| {r['host']} | {rec['frequency']} | {rec['mode']} | "
            f"{_cadence_cell(r)} | {_diff_cell(r)} | {rec['rationale']} |"
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
