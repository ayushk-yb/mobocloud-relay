"""Plain-text message templates for Telegram replies."""

from __future__ import annotations


def bytes_to_human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def speed_to_human(bytes_per_sec: float) -> str:
    return f"{bytes_to_human(bytes_per_sec)}/s"


def eta_to_human(seconds: int) -> str:
    if seconds is None or seconds < 0:
        return "unknown"
    if seconds == 0:
        return "done"
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h{minutes}m"
    if minutes:
        return f"{minutes}m{secs}s"
    return f"{secs}s"


HELP_TEXT = """\
This bot adds downloads to your home server.

Send a magnet link or an http(s) URL directly, or use:
/t <magnet-or-url> - force Transmission
/a <url> - force aria2

Other commands:
/status - server + service health
/downloads - active downloads
/disk - storage usage
/transmission - list Transmission torrents
/aria2 - list aria2 downloads
/pause <id> - pause a download
/resume <id> - resume a download
/remove <id> - remove a download
/help - this message
"""

START_TEXT = "Home server download-bot is online. Send /help for commands."


def transmission_added(info: dict) -> str:
    name = info.get("name", "unknown")
    torrent_id = info.get("id", "?")
    size = bytes_to_human(info.get("totalSize", 0) or 0)
    duplicate_note = " (already added)" if info.get("_duplicate") else ""
    return (
        f"✅ Download added{duplicate_note}\n"
        f"Name: {name}\n"
        f"Engine: Transmission\n"
        f"ID: {torrent_id}\n"
        f"Size: {size}\n"
        f"Status: Downloading"
    )


def aria2_added(gid: str, filename: str = "") -> str:
    label = f"File: {filename}\n" if filename else ""
    return (
        f"✅ Download added\n"
        f"{label}"
        f"Engine: aria2\n"
        f"GID: {gid}\n"
        f"Status: Downloading"
    )


def status_report(transmission_ok: bool, aria2_ok: bool, jellyfin_ok: bool, used: str, free: str) -> str:
    def mark(ok: bool) -> str:
        return "RUNNING" if ok else "DOWN"

    return (
        "\U0001f7e2 Home Server\n"
        f"Transmission: {mark(transmission_ok)}\n"
        f"aria2: {mark(aria2_ok)}\n"
        f"Jellyfin: {mark(jellyfin_ok)}\n"
        "download-bot: RUNNING\n\n"
        "Storage:\n"
        f"Used: {used}\n"
        f"Free: {free}"
    )


def disk_report(used: str, free: str, total: str) -> str:
    return f"Storage\nUsed: {used}\nFree: {free}\nTotal: {total}"


def transmission_list(torrents: list, status_name_fn) -> str:
    if not torrents:
        return "No torrents."
    lines = ["Transmission torrents:"]
    for t in torrents:
        pct = round((t.get("percentDone", 0) or 0) * 100)
        lines.append(
            f"#{t['id']} {t.get('name', '?')[:40]} - {pct}% "
            f"↓{speed_to_human(t.get('rateDownload', 0))} "
            f"↑{speed_to_human(t.get('rateUpload', 0))} "
            f"ETA {eta_to_human(t.get('eta'))} [{status_name_fn(t.get('status'))}]"
        )
    return "\n".join(lines)


def aria2_list(downloads: list, status_name_fn, display_name_fn) -> str:
    if not downloads:
        return "No aria2 downloads."
    lines = ["aria2 downloads:"]
    for d in downloads:
        total = int(d.get("totalLength", 0) or 0)
        done = int(d.get("completedLength", 0) or 0)
        pct = round((done / total) * 100) if total else 0
        lines.append(
            f"{d['gid']} {display_name_fn(d)[:40]} - {pct}% "
            f"↓{speed_to_human(int(d.get('downloadSpeed', 0) or 0))} "
            f"[{status_name_fn(d.get('status'))}]"
        )
    return "\n".join(lines)
