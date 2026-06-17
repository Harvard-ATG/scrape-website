"""Deterministic filename generation for scraped content.

Convention: {hostname_dots_to_underscores}__{url_path_slugified}_{hash8}.{ext}
- Max length: 120 chars (configurable)
- Hash derived from URL (not content) so filename is stable across content changes
"""

import hashlib
import os
import re
from urllib.parse import urlparse


def generate_filename_web(url: str, max_len: int = 120) -> str:
    """Deterministic filename for web pages: {domain}__{path-slug}_{hash8}.md"""
    parsed = urlparse(url)
    domain_slug = parsed.hostname.replace('.', '_')
    path = parsed.path.strip('/')
    path_slug = path.replace('/', '_') if path else 'index'
    path_slug = re.sub(r'[^\w\-.]', '_', path_slug)
    h = hashlib.md5(url.encode()).hexdigest()[:8]
    suffix = f'_{h}.md'

    candidate = f'{domain_slug}__{path_slug}{suffix}'
    if len(candidate) <= max_len:
        return candidate

    budget = max_len - len(domain_slug) - 2 - len(suffix)
    truncated = path_slug[:budget]
    if '-' in truncated and len(truncated) < len(path_slug):
        last_sep = max(truncated.rfind('-'), truncated.rfind('_'))
        if last_sep > budget * 0.7:
            truncated = truncated[:last_sep]
    return f'{domain_slug}__{truncated}{suffix}'


def generate_filename_binary(url: str, content_type: str | None = None,
                             max_len: int = 120) -> str:
    """Deterministic filename for binary files: {domain}__{name}_{hash8}.{ext}"""
    parsed = urlparse(url)
    domain_slug = parsed.hostname.replace('.', '_')
    h = hashlib.md5(url.encode()).hexdigest()[:8]

    path_parts = parsed.path.rstrip('/').split('/')
    original = path_parts[-1] if path_parts[-1] else f"file_{h}"
    name, ext = os.path.splitext(original)
    if not ext:
        ext = _guess_extension(url, content_type)
    name = re.sub(r'[^\w\-.]', '_', name).lower()
    suffix = f'_{h}{ext}'

    candidate = f'{domain_slug}__{name}{suffix}'
    if len(candidate) <= max_len:
        return candidate

    budget = max_len - len(domain_slug) - 2 - len(suffix)
    segments = name.replace('-', '_').split('_')
    if len(segments) >= 4:
        head = '_'.join(segments[:2])
        tail = '_'.join(segments[-2:])
        if len(head) + 4 + len(tail) <= budget:
            truncated = f'{head}_.._{ tail}'
        else:
            truncated = name[:budget]
    else:
        truncated = name[:budget]
    return f'{domain_slug}__{truncated}{suffix}'


def _guess_extension(url: str, content_type: str | None) -> str:
    import mimetypes
    path = urlparse(url).path
    if '.' in path:
        ext = '.' + path.split('.')[-1].lower()
        if len(ext) <= 5:
            return ext
    if content_type:
        ct = content_type.lower().split(';')[0].strip()
        ext = mimetypes.guess_extension(ct)
        if ext:
            return ext
    return '.bin'
