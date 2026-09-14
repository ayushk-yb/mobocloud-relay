"""aria2 JSON-RPC client (stdlib only).

Talks to aria2's existing local JSON-RPC endpoint. Never touches ariaNG.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request


class Aria2Error(Exception):
    pass


class Aria2Unavailable(Aria2Error):
    pass


_STATUS_MAP = {
    "active": "downloading",
    "waiting": "queued",
    "paused": "paused",
    "error": "error",
    "complete": "complete",
    "removed": "removed",
}


class Aria2Client:
    def __init__(self, rpc_url: str, secret: str = "", timeout_seconds: int = 15):
        self._url = rpc_url
        self._secret = secret
        self._timeout = timeout_seconds
        self._request_id = 0

    def _token_param(self) -> list:
        return [f"token:{self._secret}"] if self._secret else []

    def _call(self, method: str, params: list | None = None) -> object:
        self._request_id += 1
        body = {
            "jsonrpc": "2.0",
            "id": str(self._request_id),
            "method": f"aria2.{method}",
            "params": self._token_param() + (params or []),
        }
        req = urllib.request.Request(
            self._url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise Aria2Unavailable(f"aria2 RPC unreachable: {exc}") from exc

        if "error" in result:
            message = result["error"].get("message", "unknown error")
            if "Unauthorized" in message:
                raise Aria2Error("aria2 RPC authentication failed (check rpc-secret)")
            raise Aria2Error(f"aria2 RPC error: {message}")
        return result.get("result")

    def add_uri(self, uri: str) -> str:
        gid = self._call("addUri", [[uri]])
        return gid

    def add_torrent_uri(self, uri: str) -> str:
        # aria2 can fetch a .torrent URL itself via addUri; it detects the
        # torrent by content, so this is the same call as add_uri.
        return self.add_uri(uri)

    def tell_status(self, gid: str) -> dict:
        keys = ["gid", "status", "totalLength", "completedLength", "downloadSpeed", "files", "errorMessage"]
        return self._call("tellStatus", [gid, keys])

    def list_active(self, limit: int = 15) -> list:
        keys = ["gid", "status", "totalLength", "completedLength", "downloadSpeed", "files"]
        active = self._call("tellActive", [keys]) or []
        remaining = max(0, limit - len(active))
        waiting = self._call("tellWaiting", [0, remaining, keys]) if remaining else []
        return (active + waiting)[:limit]

    def pause(self, gid: str) -> None:
        self._call("pause", [gid])

    def resume(self, gid: str) -> None:
        self._call("unpause", [gid])

    def remove(self, gid: str) -> None:
        self._call("remove", [gid])

    def get_version(self) -> dict:
        return self._call("getVersion")

    @staticmethod
    def status_name(status: str) -> str:
        return _STATUS_MAP.get(status, status)

    @staticmethod
    def display_name(status: dict) -> str:
        files = status.get("files") or []
        if files and files[0].get("path"):
            return files[0]["path"].rsplit("/", 1)[-1]
        return status.get("gid", "unknown")
