# s3_manifest.py
"""Pull a host's QA manifest.json from the scrape bucket via the AWS CLI (same
tool modify_file.py uses — no boto3 dependency). manifest.json carries
generated_at (the baseline date for the diff) and files{}.source_url (the URL
set QA holds). Any failure returns None so one missing host never aborts the run."""
import json
import os
import subprocess


def pull_manifest(host, cache_dir, profile="tlt-prod", bucket="atg-apo-mcp-qa-scrape"):
    os.makedirs(cache_dir, exist_ok=True)
    local = os.path.join(cache_dir, f"{host}.manifest.json")
    if not os.path.exists(local):
        src = f"s3://{bucket}/data/{host}/manifest.json"
        env = {**os.environ, "AWS_PROFILE": profile}
        proc = subprocess.run(["aws", "s3", "cp", src, local],
                              env=env, capture_output=True, text=True)
        if proc.returncode != 0 or not os.path.exists(local):
            return None
    try:
        with open(local) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def manifest_source_urls(manifest):
    files = manifest.get("files", {}) if manifest else {}
    return [f["source_url"] for f in files.values()
            if isinstance(f, dict) and f.get("source_url")]


def manifest_generated_at(manifest):
    return manifest.get("generated_at") if manifest else None
