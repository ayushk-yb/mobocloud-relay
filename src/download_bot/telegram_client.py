"""Minimal Telegram Bot API client using long polling (getUpdates), stdlib only.

Deliberately does not use a webhook: the bot only ever makes outbound HTTPS
requests to api.telegram.org, so no inbound port is needed at home.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request

logger = logging.getLogger("download_bot.telegram")

API_ROOT = "https://api.telegram.org"

# A dropped connection right after a successful backend action (e.g. a
# torrent was added but the confirmation reply's TCP connection got reset)
# should not silently swallow the user's confirmation. Retry transient
# network errors a few times before giving up.
SEND_RETRY_ATTEMPTS = 3
SEND_RETRY_BACKOFF_SECONDS = 2


class TelegramError(Exception):
    pass


class TelegramNetworkError(TelegramError):
    """A transient network failure, as opposed to a rejected request."""


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
            raise TelegramNetworkError(f"Telegram API network error calling {method}: {exc}") from exc

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
        last_exc: Exception | None = None
        for attempt in range(1, SEND_RETRY_ATTEMPTS + 1):
            try:
                self._call(
                    "sendMessage",
                    {
                        "chat_id": chat_id,
                        "text": text,
                        "disable_web_page_preview": True,
                    },
                )
                return
            except TelegramNetworkError as exc:
                last_exc = exc
                if attempt < SEND_RETRY_ATTEMPTS:
                    logger.warning(
                        "sendMessage network error (attempt %s/%s), retrying: %s",
                        attempt,
                        SEND_RETRY_ATTEMPTS,
                        exc,
                    )
                    time.sleep(SEND_RETRY_BACKOFF_SECONDS)
        raise last_exc

    def get_me(self) -> dict:
        return self._call("getMe")
