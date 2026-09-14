import json
from unittest import mock

import pytest

from download_bot.backends.transmission import (
    TransmissionClient,
    TransmissionError,
    TransmissionUnavailable,
)


def _fake_response(body: dict):
    cm = mock.MagicMock()
    cm.__enter__.return_value.read.return_value = json.dumps(body).encode("utf-8")
    return cm


def test_add_new_torrent():
    client = TransmissionClient("http://127.0.0.1:9091/transmission/rpc")
    body = {"result": "success", "arguments": {"torrent-added": {"id": 17, "name": "ubuntu.iso"}}}
    with mock.patch("urllib.request.urlopen", return_value=_fake_response(body)):
        info = client.add("magnet:?xt=urn:btih:abc")
    assert info["id"] == 17
    assert info["_duplicate"] is False


def test_add_duplicate_torrent():
    client = TransmissionClient("http://127.0.0.1:9091/transmission/rpc")
    body = {"result": "success", "arguments": {"torrent-duplicate": {"id": 3, "name": "existing"}}}
    with mock.patch("urllib.request.urlopen", return_value=_fake_response(body)):
        info = client.add("magnet:?xt=urn:btih:abc")
    assert info["_duplicate"] is True


def test_unreachable_raises_unavailable():
    import urllib.error

    client = TransmissionClient("http://127.0.0.1:9091/transmission/rpc")
    with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("refused")):
        with pytest.raises(TransmissionUnavailable):
            client.add("magnet:?xt=urn:btih:abc")


def test_rpc_error_result_raises():
    client = TransmissionClient("http://127.0.0.1:9091/transmission/rpc")
    body = {"result": "invalid argument"}
    with mock.patch("urllib.request.urlopen", return_value=_fake_response(body)):
        with pytest.raises(TransmissionError):
            client.add("magnet:?xt=urn:btih:abc")


def test_status_name_lookup():
    assert TransmissionClient.status_name(4) == "downloading"
    assert TransmissionClient.status_name(99) == "unknown(99)"
