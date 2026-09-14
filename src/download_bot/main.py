"""Entry point: long-poll Telegram, authorize, route, and reply.

Run under runit (see service/download-bot/run). Crash-only design: on an
unhandled error the process exits and sv restarts it; the persisted offset
in state.py means restart does not reprocess old messages.
"""

from __future__ import annotations

import logging
import sys
import time

from . import commands, formatting, router
from .auth import is_authorized
from .backends.aria2 import Aria2Client
from .backends.transmission import TransmissionClient
from .config import ConfigError, load_config
from .router import UnrecognizedLink
from .state import State
from .telegram_client import TelegramClient, TelegramError

logger = logging.getLogger("download_bot")

MIN_BACKOFF_SECONDS = 1
MAX_BACKOFF_SECONDS = 60
POLL_TIMEOUT_SECONDS = 30
JELLYFIN_PING_URL = "http://127.0.0.1:8096/System/Ping"


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )


def _reply(tg: TelegramClient, chat_id: int, text: str) -> None:
    try:
        tg.send_message(chat_id, text)
    except TelegramError as exc:
        logger.warning("Failed to send reply: %s", exc)


def _handle_link(tg, transmission, aria2, chat_id: int, link: str, forced: str | None) -> None:
    try:
        backend = forced or router.classify(link)
    except UnrecognizedLink as exc:
        _reply(tg, chat_id, f"⚠️ {exc}")
        return

    if backend == router.TRANSMISSION:
        logger.info("Sending magnet/torrent link to Transmission")
        try:
            info = transmission.add(link)
        except Exception as exc:  # noqa: BLE001 - report any backend failure to the user
            logger.warning("Transmission rejected the add: %s", exc)
            _reply(tg, chat_id, f"⚠️ Transmission could not add this: {exc}")
            return
        logger.info("Transmission accepted torrent id %s", info.get("id"))
        _reply(tg, chat_id, formatting.transmission_added(info))
    else:
        logger.info("Sending URL to aria2")
        try:
            gid = aria2.add_uri(link)
        except Exception as exc:  # noqa: BLE001
            logger.warning("aria2 rejected the add: %s", exc)
            _reply(tg, chat_id, f"⚠️ aria2 could not add this: {exc}")
            return
        logger.info("aria2 accepted download gid %s", gid)
        _reply(tg, chat_id, formatting.aria2_added(gid))


def _dispatch(tg, transmission, aria2, disk_path: str, chat_id: int, text: str) -> None:
    text = text.strip()
    if not text:
        return

    if text.startswith("/"):
        parts = text.split(maxsplit=1)
        cmd = parts[0].lower().split("@")[0]
        arg = parts[1].strip() if len(parts) > 1 else ""

        if cmd in ("/start",):
            _reply(tg, chat_id, formatting.START_TEXT)
        elif cmd == "/help":
            _reply(tg, chat_id, formatting.HELP_TEXT)
        elif cmd == "/status":
            _reply(tg, chat_id, commands.cmd_status(transmission, aria2, JELLYFIN_PING_URL, disk_path))
        elif cmd == "/downloads":
            _reply(tg, chat_id, commands.cmd_downloads(transmission, aria2))
        elif cmd == "/disk":
            _reply(tg, chat_id, commands.cmd_disk(disk_path))
        elif cmd == "/transmission":
            _reply(tg, chat_id, commands.cmd_transmission_list(transmission))
        elif cmd == "/aria2":
            _reply(tg, chat_id, commands.cmd_aria2_list(aria2))
        elif cmd == "/pause":
            if not arg:
                _reply(tg, chat_id, "Usage: /pause <transmission-id-or-aria2-gid>")
            else:
                _reply(tg, chat_id, commands.cmd_pause(transmission, aria2, arg))
        elif cmd == "/resume":
            if not arg:
                _reply(tg, chat_id, "Usage: /resume <transmission-id-or-aria2-gid>")
            else:
                _reply(tg, chat_id, commands.cmd_resume(transmission, aria2, arg))
        elif cmd == "/remove":
            if not arg:
                _reply(tg, chat_id, "Usage: /remove <transmission-id-or-aria2-gid>")
            else:
                _reply(tg, chat_id, commands.cmd_remove(transmission, aria2, arg))
        elif cmd == "/t":
            if not arg:
                _reply(tg, chat_id, "Usage: /t <magnet-or-url>")
            else:
                _handle_link(tg, transmission, aria2, chat_id, arg, forced=router.TRANSMISSION)
        elif cmd == "/a":
            if not arg:
                _reply(tg, chat_id, "Usage: /a <url>")
            else:
                _handle_link(tg, transmission, aria2, chat_id, arg, forced=router.ARIA2)
        else:
            _reply(tg, chat_id, "Unknown command. Send /help for the list of commands.")
        return

    if router.is_link_like(text):
        logger.info("Magnet or URL detected in message")
        _handle_link(tg, transmission, aria2, chat_id, text, forced=None)
    else:
        _reply(tg, chat_id, "Not a recognized command, magnet link, or URL. Send /help.")


def run() -> None:
    _setup_logging()
    try:
        config = load_config()
    except ConfigError as exc:
        logger.error("Configuration error: %s", exc)
        sys.exit(1)

    tg = TelegramClient(config.telegram_bot_token, request_timeout_seconds=POLL_TIMEOUT_SECONDS + 10)
    transmission = TransmissionClient(
        config.transmission_rpc_url,
        config.transmission_rpc_username,
        config.transmission_rpc_password,
    )
    aria2 = Aria2Client(config.aria2_rpc_url, config.aria2_rpc_secret)
    state = State(config.state_dir)

    try:
        me = tg.get_me()
        logger.info("Telegram connection established as @%s", me.get("username"))
    except TelegramError as exc:
        logger.warning("Could not verify bot identity yet, will keep retrying: %s", exc)

    backoff = MIN_BACKOFF_SECONDS
    while True:
        try:
            updates = tg.get_updates(state.last_update_id, POLL_TIMEOUT_SECONDS)
            backoff = MIN_BACKOFF_SECONDS
        except TelegramError as exc:
            logger.warning("Telegram poll failed (%s), retrying in %ss", exc, backoff)
            time.sleep(backoff)
            backoff = min(backoff * 2, MAX_BACKOFF_SECONDS)
            continue

        for update in updates:
            update_id = update.get("update_id")
            if update_id is None or state.already_processed(update_id):
                continue

            message = update.get("message") or {}
            chat = message.get("chat") or {}
            chat_id = chat.get("id")
            text = message.get("text", "")

            if chat_id is None:
                state.mark_processed(update_id)
                continue

            if not is_authorized(chat_id, config.authorized_chat_ids):
                # Silently ignore: no reply, no detail logged about the message content.
                logger.info("Ignored message from unauthorized chat")
                state.mark_processed(update_id)
                continue

            logger.info("Authorized message received")
            try:
                _dispatch(tg, transmission, aria2, config.disk_usage_path, chat_id, text)
            except Exception:  # noqa: BLE001 - never let one bad message kill the loop
                logger.exception("Unhandled error while processing update %s", update_id)
                _reply(tg, chat_id, "⚠️ Internal error handling that message.")
            state.mark_processed(update_id)


if __name__ == "__main__":
    run()
