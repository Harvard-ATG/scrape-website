"""Invariants for sites.toml. These guard against the configuration problems found during the analysis."""
import re
from urllib.parse import urlsplit

import pytest

from loaders import MOVED_HOSTS, SITES_TOML, load_sites

pytestmark = pytest.mark.skipif(not SITES_TOML.exists(), reason="sites.toml not found")
SITES = load_sites() if SITES_TOML.exists() else {}
ENTRIES = [(h, e) for h, es in SITES.items() for e in es]


def test_expected_size():
    assert len(ENTRIES) == 84 and len(SITES) == 83                      # registrar has two entries


def test_only_registrar_has_more_than_one_entry():
    assert {h for h, es in SITES.items() if len(es) > 1} == {"registrar.fas.harvard.edu"}


@pytest.mark.parametrize("host,entry", ENTRIES, ids=[f"{h}:{urlsplit(e['url']).path or '/'}" for h, e in ENTRIES])
def test_entry_shape(host, entry):
    u = urlsplit(entry["url"])
    assert u.scheme == "https", "seed must be https (the ^http:// exclude would otherwise drop the entry point)"
    assert u.netloc == host, "seed host must equal hostname"
    assert host == host.lower()
    assert entry.get("resource", {}).get("name") and entry["resource"].get("type")
    for key in ("include_patterns", "exclude_patterns"):
        for pat in entry.get(key, []):
            re.compile(pat)                                              # must be a valid regex


def test_scoped_entries_have_a_non_root_seed():
    for h, e in ENTRIES:
        if e.get("scope_to_path"):
            assert urlsplit(e["url"]).path.strip("/"), f"{h}: scope_to_path with a root seed scopes nothing"


def test_no_live_entry_uses_a_moved_hostname():
    for old, new in MOVED_HOSTS.items():
        assert old not in SITES, f"{old} now redirects to {new}"
        assert new in SITES, f"{new} should be in sites.toml"


def test_use_sitemap_is_not_set_anywhere_yet():
    """Documents today's state (decision 2). Update this test when sitemap seeding is adopted."""
    assert not [h for h, e in ENTRIES if "use_sitemap" in e]
