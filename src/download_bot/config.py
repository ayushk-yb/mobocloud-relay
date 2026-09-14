"""Loads download-bot configuration from an env file outside the repo.

Machine-specific values (bot token, authorized chat IDs, RPC credentials)
must never live in source control. They are read from a plain KEY=VALUE
file whose path is given by the DOWNLOAD_BOT_ENV_FILE environment variable,
or one of a few conventional Termux locations.
"""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass, field

DEFAULT_ENV_LOCATIONS = (
    os.path.expanduser("~/.config/download-bot/download-bot.env"),
    os.environ.get("PREFIX", "") + "/etc/download-bot.env",
)

REQUIRED_KEYS = (
    "TELEGRAM_BOT_TOKEN",
    "AUTHORIZED_CHAT_IDS",
    "TRANSMISSION_RPC_URL",
    "ARIA2_RPC_URL",
)


class ConfigError(Exception):
    pass


def _find_env_file() -> str:
    explicit = os.environ.get("DOWNLOAD_BOT_ENV_FILE")
    if explicit:
        return explicit
    for candidate in DEFAULT_ENV_LOCATIONS:
        if candidate and os.path.isfile(candidate):
            return candidate
    raise ConfigError(
        "No config file found. Set DOWNLOAD_BOT_ENV_FILE or create "
        "~/.config/download-bot/download-bot.env (see .env.example)."
    )


def _parse_env_file(path: str) -> dict:
    values = {}
    with open(path, "r", encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _check_permissions(path: str) -> None:
    if os.name != "posix":
        return
    mode = stat.S_IMODE(os.stat(path).st_mode)
    if mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise ConfigError(
            f"{path} is readable/writable by group or others (mode {oct(mode)}). "
            f"Run: chmod 600 {path}"
        )


@dataclass(frozen=True)
class Config:
    telegram_bot_token: str
    authorized_chat_ids: frozenset
    transmission_rpc_url: str
    transmission_rpc_username: str
    transmission_rpc_password: str
    aria2_rpc_url: str
    aria2_rpc_secret: str
    state_dir: str
    disk_usage_path: str
    poll_timeout_seconds: int = 30
    request_timeout_seconds: int = 40
    log_dir: str = field(default_factory=lambda: os.path.expanduser("~/.local/state/download-bot/logs"))


def load_config() -> Config:
    path = _find_env_file()
    _check_permissions(path)
    values = _parse_env_file(path)

    missing = [k for k in REQUIRED_KEYS if not values.get(k)]
    if missing:
        raise ConfigError(f"Missing required config keys in {path}: {', '.join(missing)}")

    try:
        chat_ids = frozenset(
            int(x.strip()) for x in values["AUTHORIZED_CHAT_IDS"].split(",") if x.strip()
        )
    except ValueError as exc:
        raise ConfigError("AUTHORIZED_CHAT_IDS must be a comma-separated list of integers") from exc
    if not chat_ids:
        raise ConfigError("AUTHORIZED_CHAT_IDS must contain at least one chat ID")

    state_dir = values.get("DOWNLOAD_BOT_STATE_DIR") or os.path.expanduser(
        "~/.local/state/download-bot"
    )
    disk_usage_path = values.get("DOWNLOAD_BOT_DISK_PATH") or os.path.expanduser("~/storage/shared")

    return Config(
        telegram_bot_token=values["TELEGRAM_BOT_TOKEN"],
        authorized_chat_ids=chat_ids,
        transmission_rpc_url=values["TRANSMISSION_RPC_URL"],
        transmission_rpc_username=values.get("TRANSMISSION_RPC_USERNAME", ""),
        transmission_rpc_password=values.get("TRANSMISSION_RPC_PASSWORD", ""),
        aria2_rpc_url=values["ARIA2_RPC_URL"],
        aria2_rpc_secret=values.get("ARIA2_RPC_SECRET", ""),
        state_dir=state_dir,
        disk_usage_path=disk_usage_path,
    )
