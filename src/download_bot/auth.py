"""Application-level authorization: only allowlisted Telegram chat IDs get any response."""

from __future__ import annotations


def is_authorized(chat_id: int, authorized_chat_ids: frozenset) -> bool:
    return chat_id in authorized_chat_ids
