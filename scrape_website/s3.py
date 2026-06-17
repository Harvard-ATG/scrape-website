"""Optional S3 upload for scraped content.

Uploads the local output directory to S3, preserving directory structure.
Manifest is uploaded LAST as a commit-point signal.
"""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def upload_to_s3(base_dir: Path, bucket: str, prefix: str = "data"):
    """Upload all files in base_dir to s3://{bucket}/{prefix}/{hostname}/...

    Manifest.json is uploaded last so its presence signals a complete upload.

    Args:
        base_dir: local directory (e.g., data/advising.harvard.edu/)
        bucket: S3 bucket name
        prefix: S3 key prefix (default: "data")
    """
    import boto3

    s3 = boto3.client('s3')
    hostname = base_dir.name
    manifest_key = None
    uploaded = 0

    for root, _dirs, files in os.walk(base_dir):
        for filename in files:
            local_path = Path(root) / filename
            relative = local_path.relative_to(base_dir)
            s3_key = f"{prefix}/{hostname}/{relative}"

            if filename == "manifest.json":
                manifest_key = (str(local_path), s3_key)
                continue

            s3.upload_file(str(local_path), bucket, s3_key)
            uploaded += 1

    if manifest_key:
        local_path, s3_key = manifest_key
        s3.upload_file(local_path, bucket, s3_key)
        uploaded += 1

    logger.info(f"Uploaded {uploaded} files to s3://{bucket}/{prefix}/{hostname}/")
    return uploaded
