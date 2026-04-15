from __future__ import annotations

from dataclasses import dataclass
import os

DEFAULT_USERS = ["ユーザー1", "ユーザー2"]


@dataclass(frozen=True)
class AppConfig:
    discord_webhook_url: str
    users: list[str]
    time_format: str
    host: str
    port: int
    debug: bool

    @staticmethod
    def _parse_bool(value: str | None, default: bool = False) -> bool:
        if value is None:
            return default
        return value.strip().lower() in {"1", "true", "yes", "on"}

    @classmethod
    def from_env(cls) -> "AppConfig":
        users_raw = os.getenv("USERS", "")
        users = [name.strip() for name in users_raw.split(",") if name.strip()]
        if not users:
            users = DEFAULT_USERS

        port_raw = os.getenv("PORT", "5000")
        try:
            port = int(port_raw)
        except ValueError:
            port = 5000

        return cls(
            discord_webhook_url=os.getenv("DISCORD_WEBHOOK_URL", "").strip(),
            users=users,
            time_format=os.getenv("TIME_FORMAT", "%Y/%m/%d %H:%M:%S"),
            host=os.getenv("HOST", "0.0.0.0").strip() or "0.0.0.0",
            port=port,
            debug=cls._parse_bool(os.getenv("DEBUG"), default=False),
        )
