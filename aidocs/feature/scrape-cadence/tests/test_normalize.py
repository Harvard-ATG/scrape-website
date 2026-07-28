from normalize import norm_base


def test_scheme_and_host_lowered():
    assert norm_base("HTTP://Example.COM/Path") == "https://example.com/Path"


def test_trailing_slash_stripped():
    assert norm_base("https://x.edu/a/b/") == "https://x.edu/a/b"


def test_query_and_fragment_dropped():
    assert norm_base("https://x.edu/a?page=2#frag") == "https://x.edu/a"


def test_root_path_preserved():
    assert norm_base("https://x.edu") == "https://x.edu/"
    assert norm_base("https://x.edu/") == "https://x.edu/"


def test_empty_and_relative():
    assert norm_base("") == ""
    assert norm_base(None) == ""
    assert norm_base("/just/a/path") == ""   # no netloc
