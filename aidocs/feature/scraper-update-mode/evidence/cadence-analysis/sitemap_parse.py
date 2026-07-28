"""Pure sitemap XML parser. Unlike corpus_crossover._parse_locs it also
captures <lastmod> per <url> (the cadence signal). Namespace-agnostic: matches
tags by local name so it works regardless of xmlns prefix."""
import xml.etree.ElementTree as ET


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def parse_sitemap(body: bytes) -> tuple[list[str], list[dict]]:
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return [], []
    kind = _local(root.tag)
    if kind == "sitemapindex":
        children = [
            loc.text.strip()
            for sm in root if _local(sm.tag) == "sitemap"
            for loc in sm if _local(loc.tag) == "loc" and loc.text
        ]
        return children, []
    if kind == "urlset":
        entries = []
        for u in root:
            if _local(u.tag) != "url":
                continue
            loc = lastmod = None
            for child in u:
                lc = _local(child.tag)
                if lc == "loc" and child.text:
                    loc = child.text.strip()
                elif lc == "lastmod" and child.text:
                    lastmod = child.text.strip()
            if loc:
                entries.append({"loc": loc, "lastmod": lastmod})
        return [], entries
    return [], []
