import pytest

from download_bot import router


def test_magnet_goes_to_transmission():
    assert router.classify("magnet:?xt=urn:btih:abcdef1234567890") == router.TRANSMISSION


def test_torrent_url_goes_to_transmission():
    assert router.classify("https://example.com/file.torrent") == router.TRANSMISSION


def test_torrent_url_with_query_goes_to_transmission():
    assert router.classify("https://example.com/file.torrent?x=1") == router.TRANSMISSION


def test_http_url_goes_to_aria2():
    assert router.classify("https://example.com/file.zip") == router.ARIA2


def test_plain_http_goes_to_aria2():
    assert router.classify("http://example.com/file.zip") == router.ARIA2


def test_malformed_input_rejected():
    with pytest.raises(router.UnrecognizedLink):
        router.classify("not a link at all")


def test_shell_injection_attempt_rejected():
    with pytest.raises(router.UnrecognizedLink):
        router.classify("; rm -rf / #")


def test_is_link_like():
    assert router.is_link_like("magnet:?xt=urn:btih:abc")
    assert router.is_link_like("https://example.com/a.zip")
    assert not router.is_link_like("hello there")
