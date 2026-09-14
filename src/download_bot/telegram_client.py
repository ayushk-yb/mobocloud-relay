"""Minimal Telegram Bot API client using long polling (getUpdates), stdlib only.

Deliberately does not use a webhook: the bot only ever makes outbound HTTPS
requests to api.telegram.org, so no inbound port is needed at home.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request

logger = logging.getLogger("download_bot.telegram")

API_ROOT = "https://api.telegram.org"


class TelegramError(Exception):
    pass


class TelegramClient:
    def __init__(self, bot_token: str, request_timeout_seconds: int = 40):
        self._token = bot_token
        self._timeout = request_timeout_seconds

    def _call(self, method: str, params: dict | None = None) -> dict:
        url = f"{API_ROOT}/bot{self._token}/{method}"
        data = None
        if params is not None:
            data = json.dumps(params).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"} if data else {},
            method="POST" if data else "GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            try:
                body = json.loads(exc.read().decode("utf-8"))
            except (ValueError, json.JSONDecodeError):
                body = {}
            raise TelegramError(
                f"Telegram API HTTP {exc.code} calling {method}: {body.get('description', 'unknown error')}"
            ) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise TelegramError(f"Telegram API network error calling {method}: {exc}") from exc

        if not body.get("ok"):
            raise TelegramError(f"Telegram API error calling {method}: {body.get('description')}")
        return body["result"]

    def get_updates(self, offset: int, timeout_seconds: int) -> list:
        return self._call(
            "getUpdates",
            {
                "offset": offset,
                "timeout": timeout_seconds,
                "allowed_updates": ["message"],
            },
        )

    def send_message(self, chat_id: int, text: str) -> None:
        self._call(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": text,
                "disable_web_page_preview": True,
            },
        )

    def get_me(self) -> dict:
        return self._call("getMe")
