import json
from unittest import mock

import pytest

from download_bot.backends.aria2 import Aria2Client, Aria2Error, Aria2Unavailable


def _fake_response(body: dict):
    cm = mock.MagicMock()
    cm.__enter__.return_value.read.return_value = json.dumps(body).encode("utf-8")
    return cm


def test_add_uri_returns_gid():
    client = Aria2Client("http://127.0.0.1:6800/jsonrpc", secret="s3cr3t")
    body = {"jsonrpc": "2.0", "id": "1", "result": "2089b05ecca3d829"}
    with mock.patch("urllib.request.urlopen", return_value=_fake_response(body)) as urlopen:
        gid = client.add_uri("https://example.com/file.zip")
    assert gid == "2089b05ecca3d829"
    sent = json.loads(urlopen.call_args[0][0].data)
    assert sent["params"][0] == "token:s3cr3t"


def test_unauthorized_secret_raises_aria2_error():
    client = Aria2Client("http://127.0.0.1:6800/jsonrpc", secret="wrong")
    body = {"jsonrpc": "2.0", "id": "1", "error": {"code": 1, "message": "Unauthorized"}}
    with mock.patch("urllib.request.urlopen", return_value=_fake_response(body)):
        with pytest.raises(Aria2Error):
            client.add_uri("https://example.com/file.zip")


def test_unreachable_raises_unavailable():
    import urllib.error

    client = Aria2Client("http://127.0.0.1:6800/jsonrpc", secret="s3cr3t")
    with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("refused")):
        with pytest.raises(Aria2Unavailable):
            client.add_uri("https://example.com/file.zip")


def test_status_name_map():
    assert Aria2Client.status_name("active") == "downloading"
    assert Aria2Client.status_name("weird") == "weird"


def test_display_name_from_files():
    status = {"gid": "abc123", "files": [{"path": "/downloads/example.zip"}]}
    assert Aria2Client.display_name(status) == "example.zip"


def test_display_name_falls_back_to_gid():
    assert Aria2Client.display_name({"gid": "abc123", "files": []}) == "abc123"
