"""Parse ISO 8601 date/datetime strings (sitemap <lastmod>, manifest
generated_at) down to a date. Tolerant: trailing 'Z', microseconds, offsets,
or bare dates all work; anything unparseable returns None."""
from datetime import date, datetime


def parse_iso_date(s: str | None) -> date | None:
    if not s:
        return None
    s = s.strip()
    if not s:
        return None
    candidate = s[:-1] + "+00:00" if s.endswith("Z") else s
    try:
        return datetime.fromisoformat(candidate).date()
    except ValueError:
        try:
            return date.fromisoformat(s[:10])
        except ValueError:
            return None
