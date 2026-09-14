import json
import urllib.error
from unittest import mock

import pytest

from download_bot.telegram_client import TelegramClient, TelegramError


def _fake_response(body: dict):
    cm = mock.MagicMock()
    cm.__enter__.return_value.read.return_value = json.dumps(body).encode("utf-8")
    return cm


def test_send_message_retries_then_succeeds():
    client = TelegramClient("dummy-token")
    ok_body = {"ok": True, "result": {}}
    side_effects = [
        urllib.error.URLError("connection reset"),
        urllib.error.URLError("connection reset"),
        _fake_response(ok_body),
    ]
    with mock.patch("urllib.request.urlopen", side_effect=side_effects), mock.patch("time.sleep"):
        client.send_message(123, "hello")  # should not raise


def test_send_message_gives_up_after_max_attempts():
    client = TelegramClient("dummy-token")
    with mock.patch(
        "urllib.request.urlopen", side_effect=urllib.error.URLError("connection reset")
    ), mock.patch("time.sleep"):
        with pytest.raises(TelegramError):
            client.send_message(123, "hello")


def test_get_updates_does_not_retry_on_network_error():
    client = TelegramClient("dummy-token")
    with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("refused")):
        with pytest.raises(TelegramError):
            client.get_updates(0, 30)
