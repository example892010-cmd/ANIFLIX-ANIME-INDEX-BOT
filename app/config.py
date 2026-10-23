from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    bot_token: str
    owner_id: int
    admin_ids: frozenset[int]
    database_path: Path
    media_dir: Path
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "Settings":
        token = os.getenv("BOT_TOKEN", "").strip()
        owner_raw = os.getenv("OWNER_ID", "").strip()
        if not token:
            raise ValueError("BOT_TOKEN is required")
        if not owner_raw.isdigit():
            raise ValueError("OWNER_ID must be a numeric Telegram user ID")
        extra = set()
        for value in os.getenv("ADMIN_IDS", "").split(","):
            value = value.strip()
            if value:
                if not value.isdigit():
                    raise ValueError("ADMIN_IDS must be comma-separated numeric IDs")
                extra.add(int(value))
        database_path = Path(os.getenv("DATABASE_PATH", "data/aniflix.db"))
        media_dir = Path(os.getenv("MEDIA_DIR", "data/media"))
        database_path.parent.mkdir(parents=True, exist_ok=True)
        media_dir.mkdir(parents=True, exist_ok=True)
        return cls(token, int(owner_raw), frozenset(extra), database_path, media_dir, os.getenv("LOG_LEVEL", "INFO"))

    def is_admin(self, user_id: int | None) -> bool:
        return user_id is not None and (user_id == self.owner_id or user_id in self.admin_ids)
