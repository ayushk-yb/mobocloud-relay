"""Handlers for each Telegram command. Pure functions of (backends, args) -> reply text."""

from __future__ import annotations

import shutil
import urllib.error
import urllib.request

from . import formatting
from .backends.aria2 import Aria2Client, Aria2Error
from .backends.transmission import TransmissionClient, TransmissionError


def _check_jellyfin(ping_url: str) -> bool:
    try:
        with urllib.request.urlopen(ping_url, timeout=5) as resp:
            return resp.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def cmd_status(transmission: TransmissionClient, aria2: Aria2Client, jellyfin_ping_url: str, disk_path: str) -> str:
    transmission_ok = True
    try:
        transmission.get_session()
    except TransmissionError:
        transmission_ok = False

    aria2_ok = True
    try:
        aria2.get_version()
    except Aria2Error:
        aria2_ok = False

    jellyfin_ok = _check_jellyfin(jellyfin_ping_url)

    used_h, free_h = _disk_usage(disk_path)
    return formatting.status_report(transmission_ok, aria2_ok, jellyfin_ok, used_h, free_h)


def _disk_usage(path: str) -> tuple:
    usage = shutil.disk_usage(path)
    return formatting.bytes_to_human(usage.used), formatting.bytes_to_human(usage.free)


def cmd_disk(disk_path: str) -> str:
    usage = shutil.disk_usage(disk_path)
    return formatting.disk_report(
        formatting.bytes_to_human(usage.used),
        formatting.bytes_to_human(usage.free),
        formatting.bytes_to_human(usage.total),
    )


def cmd_transmission_list(transmission: TransmissionClient) -> str:
    try:
        torrents = transmission.list_torrents()
    except TransmissionError as exc:
        return f"⚠️ Transmission unavailable: {exc}"
    return formatting.transmission_list(torrents, TransmissionClient.status_name)


def cmd_aria2_list(aria2: Aria2Client) -> str:
    try:
        downloads = aria2.list_active()
    except Aria2Error as exc:
        return f"⚠️ aria2 unavailable: {exc}"
    return formatting.aria2_list(downloads, Aria2Client.status_name, Aria2Client.display_name)


def cmd_downloads(transmission: TransmissionClient, aria2: Aria2Client) -> str:
    parts = [cmd_transmission_list(transmission), "", cmd_aria2_list(aria2)]
    return "\n".join(parts)


def cmd_pause(transmission: TransmissionClient, aria2: Aria2Client, target_id: str) -> str:
    if target_id.isdigit():
        try:
            transmission.pause(int(target_id))
            return f"⏸ Paused Transmission torrent #{target_id}"
        except TransmissionError as exc:
            return f"⚠️ Could not pause: {exc}"
    try:
        aria2.pause(target_id)
        return f"⏸ Paused aria2 download {target_id}"
    except Aria2Error as exc:
        return f"⚠️ Could not pause: {exc}"


def cmd_resume(transmission: TransmissionClient, aria2: Aria2Client, target_id: str) -> str:
    if target_id.isdigit():
        try:
            transmission.resume(int(target_id))
            return f"▶️ Resumed Transmission torrent #{target_id}"
        except TransmissionError as exc:
            return f"⚠️ Could not resume: {exc}"
    try:
        aria2.resume(target_id)
        return f"▶️ Resumed aria2 download {target_id}"
    except Aria2Error as exc:
        return f"⚠️ Could not resume: {exc}"


def cmd_remove(transmission: TransmissionClient, aria2: Aria2Client, target_id: str) -> str:
    if target_id.isdigit():
        try:
            transmission.remove(int(target_id))
            return f"🗑 Removed Transmission torrent #{target_id}"
        except TransmissionError as exc:
            return f"⚠️ Could not remove: {exc}"
    try:
        aria2.remove(target_id)
        return f"🗑 Removed aria2 download {target_id}"
    except Aria2Error as exc:
        return f"⚠️ Could not remove: {exc}"
