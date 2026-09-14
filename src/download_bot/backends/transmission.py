"""Transmission RPC client (stdlib only).

Talks to Transmission's existing local RPC endpoint (see README for how to
find TRANSMISSION_RPC_URL on your own install). Never touches the
Transmission web UI, and never shells out to the transmission-remote CLI.
"""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request


class TransmissionError(Exception):
    pass


class TransmissionUnavailable(TransmissionError):
    pass


_STATUS_NAMES = {
    0: "stopped",
    1: "queued-verify",
    2: "verifying",
    3: "queued-download",
    4: "downloading",
    5: "queued-seed",
    6: "seeding",
}


class TransmissionClient:
    def __init__(self, rpc_url: str, username: str = "", password: str = "", timeout_seconds: int = 15):
        self._url = rpc_url
        self._username = username
        self._password = password
        self._timeout = timeout_seconds
        self._session_id = ""

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self._session_id:
            headers["X-Transmission-Session-Id"] = self._session_id
        if self._username:
            token = base64.b64encode(f"{self._username}:{self._password}".encode("utf-8")).decode("ascii")
            headers["Authorization"] = f"Basic {token}"
        return headers

    def _request(self, method: str, arguments: dict | None = None, retry: bool = True) -> dict:
        payload = json.dumps({"method": method, "arguments": arguments or {}}).encode("utf-8")
        req = urllib.request.Request(self._url, data=payload, headers=self._headers(), method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 409 and retry:
                self._session_id = exc.headers.get("X-Transmission-Session-Id", "")
                return self._request(method, arguments, retry=False)
            if exc.code == 401:
                raise TransmissionError("Transmission RPC authentication failed (check username/password)") from exc
            raise TransmissionError(f"Transmission RPC HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise TransmissionUnavailable(f"Transmission RPC unreachable: {exc}") from exc

        if body.get("result") != "success":
            raise TransmissionError(f"Transmission RPC error: {body.get('result')}")
        return body.get("arguments", {})

    def add(self, magnet_or_url: str) -> dict:
        result = self._request("torrent-add", {"filename": magnet_or_url})
        if "torrent-duplicate" in result:
            info = result["torrent-duplicate"]
            info["_duplicate"] = True
            return info
        if "torrent-added" in result:
            info = result["torrent-added"]
            info["_duplicate"] = False
            return info
        raise TransmissionError("Transmission did not report torrent-added or torrent-duplicate")

    def get_torrent(self, torrent_id: int) -> dict:
        fields = ["id", "name", "status", "percentDone", "rateDownload", "rateUpload", "eta", "totalSize"]
        result = self._request("torrent-get", {"ids": [torrent_id], "fields": fields})
        torrents = result.get("torrents", [])
        if not torrents:
            raise TransmissionError(f"No such torrent id {torrent_id}")
        return torrents[0]

    def list_torrents(self, limit: int = 15) -> list:
        fields = ["id", "name", "status", "percentDone", "rateDownload", "rateUpload", "eta"]
        result = self._request("torrent-get", {"fields": fields})
        torrents = result.get("torrents", [])
        return torrents[:limit]

    def pause(self, torrent_id: int) -> None:
        self._request("torrent-stop", {"ids": [torrent_id]})

    def resume(self, torrent_id: int) -> None:
        self._request("torrent-start", {"ids": [torrent_id]})

    def remove(self, torrent_id: int, delete_data: bool = False) -> None:
        self._request("torrent-remove", {"ids": [torrent_id], "delete-local-data": delete_data})

    def get_session(self) -> dict:
        return self._request("session-get")

    @staticmethod
    def status_name(status_code: int) -> str:
        return _STATUS_NAMES.get(status_code, f"unknown({status_code})")
