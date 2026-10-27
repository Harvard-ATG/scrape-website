"""Convert the AWS sitemap-reachability probe output (result.json) to CSV.

Pure transform of the raw probe artifact — no network. Emits one row per host
with both tier statuses so the exact probe result is inspectable as a table.
Run from this directory: `python3 result_to_csv.py`.
"""
import csv
import json
from collections import Counter

with open("result.json") as f:
    data = json.load(f)

rows = data["results"]


def outcome(r: dict) -> str:
    """Classify a host by how its sitemap fetch resolved."""
    if not r["reachable"]:
        return "no_sitemap"
    if r["tier1"] == 200:
        return "tier1_ok"
    return "needed_tier2"


with open("result.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow([
        "host", "sitemap_url", "tier1_status", "tier2_status",
        "loc_count", "is_index", "reachable", "outcome",
    ])
    for r in rows:
        w.writerow([
            r["host"], r["sitemap_url"], r["tier1"], r["tier2"],
            r["loc_count"], r["is_index"], r["reachable"], outcome(r),
        ])

# Sanity check: derived counts must match the JSON header, and surface every
# distinct status code the probe actually recorded (answers the 429 question).
counts = Counter(outcome(r) for r in rows)
statuses = sorted(set(r["tier1"] for r in rows) | set(r["tier2"] for r in rows))
print(f"rows written: {len(rows)}")
print(
    "JSON header:   "
    f"total={data['total']} reachable={data['reachable']} "
    f"tier1_direct_200={data['tier1_direct_200']} needed_tier2={data['needed_tier2']}"
)
print(f"derived rows:  {dict(counts)}")
print(f"status codes seen (tier1 or tier2): {statuses}")
