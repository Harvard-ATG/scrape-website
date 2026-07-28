"""Manifest generation for scraped content.

Produces an enriched manifest.json with per-file metadata suitable for
downstream consumers (MCP server ingest, HA S3 FileSync, etc.).
"""

import json
from datetime import datetime, timezone
from pathlib import Path


def build_manifest(files: dict, hostname: str) -> dict:
    """Build the enriched manifest structure from raw file entries.

    Args:
        files: dict of {filename: {source_url, hostname, title, content_type,
               file_type?, found_on?, content_hash?}}
        hostname: the base domain that was scraped
    """
    return {
        "schema_version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "hostname": hostname,
        "file_count": len(files),
        "files": files,
    }


def write_manifest(manifest: dict, output_path: Path):
    """Write manifest.json to disk."""
    with open(output_path, 'w') as f:
        json.dump(manifest, f, indent=2)


def load_manifest(path: Path) -> dict:
    """Load manifest.json from a local path."""
    with open(path) as f:
        return json.load(f)
