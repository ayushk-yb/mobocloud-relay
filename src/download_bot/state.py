"""Persists the Telegram update offset and a short history of processed update IDs.

This lets the bot survive a crash/restart/reboot without reprocessing (and
re-submitting) the same message twice.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections import deque

RECENT_HISTORY_SIZE = 200


class State:
    def __init__(self, state_dir: str):
        self._path = os.path.join(state_dir, "state.json")
        os.makedirs(state_dir, exist_ok=True)
        self.last_update_id = 0
        self._recent = deque(maxlen=RECENT_HISTORY_SIZE)
        self._load()

    def _load(self) -> None:
        if not os.path.isfile(self._path):
            return
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            self.last_update_id = int(data.get("last_update_id", 0))
            self._recent = deque(data.get("recent_update_ids", []), maxlen=RECENT_HISTORY_SIZE)
        except (ValueError, OSError, json.JSONDecodeError):
            self.last_update_id = 0
            self._recent = deque(maxlen=RECENT_HISTORY_SIZE)

    def _save(self) -> None:
        data = {
            "last_update_id": self.last_update_id,
            "recent_update_ids": list(self._recent),
        }
        fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(self._path))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh)
            os.replace(tmp_path, self._path)
        except OSError:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise

    def already_processed(self, update_id: int) -> bool:
        return update_id in self._recent

    def mark_processed(self, update_id: int) -> None:
        self._recent.append(update_id)
        if update_id >= self.last_update_id:
            self.last_update_id = update_id + 1
        self._save()
