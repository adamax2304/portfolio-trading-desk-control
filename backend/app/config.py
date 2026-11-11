"""Control-plane settings. Secrets live ONLY here (env), never reach the frontend."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


def _bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    return default if v is None else v.strip().lower() in {"1", "true", "yes", "on"}


def _ids(name: str) -> set[int]:
    raw = os.getenv(name, "") or ""
    out: set[int] = set()
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if part.lstrip("-").isdigit():
            out.add(int(part))
    return out


class Settings:
    """Read from environment. Safe defaults = read-only + demo + live disabled."""

    def __init__(self) -> None:
        here = Path(__file__).resolve()
        self.app_root = here.parents[2]                       # trading-desk-control/
        self.control_db_path = Path(
            os.getenv("CONTROL_DB_PATH", str(self.app_root / "backend" / "control.sqlite"))
        )
        # Path to the EXISTING crypto-ai-desk SQLite (read-only). If missing → demo mode.
        self.desk_db_path = Path(
            os.getenv("DESK_DB_PATH", str(self.app_root.parent / "crypto-ai-desk" / "db" / "crypto_ai_desk.sqlite"))
        )
        self.desk_reports_dir = Path(
            os.getenv("DESK_REPORTS_DIR", str(self.app_root.parent / "crypto-ai-desk" / "reports"))
        )
        # Deployment environment: "dev" (default) | "production". Controls the AUTH_DISABLED guard.
        self.app_env = (os.getenv("APP_ENV", "dev") or "dev").strip().lower()
        # Telegram
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.allowed_user_ids = _ids("ALLOWED_TELEGRAM_USER_IDS")
        self.mini_app_url = os.getenv("MINI_APP_URL", "")
        self.api_base_url = os.getenv("API_BASE_URL", "")
        # Server-to-server token the bot uses for the (safe) emergency-pause path. Optional.
        self.control_bot_token = os.getenv("CONTROL_BOT_TOKEN", "")
        # initData freshness window (seconds) — reject stale auth payloads
        self.initdata_max_age = int(os.getenv("INITDATA_MAX_AGE", "86400"))

        # ---- safety switches (default = safest) ----
        # demo_mode: serve synthetic data if the desk DB is absent. Auto-on when no DB.
        self.demo_mode = _bool("DEMO_MODE", not self.desk_db_path.exists())
        # When True, auth is bypassed with a demo user (LOCAL DEV ONLY).
        self.auth_disabled = _bool("AUTH_DISABLED", False)
        # Master gate for any state-changing command. v1 default: paper-only allowed,
        # live HARD-disabled regardless of per-command flags.
        self.enable_paper_commands = _bool("ENABLE_PAPER_COMMANDS", True)
        self.enable_live_commands = False  # HARD-LOCKED in v1 — see commands.py
        # Auto-live is never selectable in v1.
        self.auto_live_locked = True

    @property
    def is_production(self) -> bool:
        return self.app_env in {"production", "prod"}

    def assert_safe_for_env(self) -> None:
        """Fail fast on an unsafe production configuration. Called at app startup."""
        if self.is_production:
            if self.auth_disabled:
                raise RuntimeError(
                    "AUTH_DISABLED=1 is forbidden when APP_ENV=production. "
                    "Telegram initData auth must be active in production.")
            if not self.bot_token:
                raise RuntimeError("TELEGRAM_BOT_TOKEN required when APP_ENV=production.")
            if not self.allowed_user_ids:
                raise RuntimeError("ALLOWED_TELEGRAM_USER_IDS required when APP_ENV=production.")

    # convenience
    @property
    def has_desk_db(self) -> bool:
        return self.desk_db_path.exists()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
