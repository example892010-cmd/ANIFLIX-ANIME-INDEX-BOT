from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, path: str | Path):
        self.path = str(path)
        self.conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = await aiosqlite.connect(self.path)
        self.conn.row_factory = aiosqlite.Row
        await self.conn.execute("PRAGMA foreign_keys=ON")
        await self.conn.execute("PRAGMA journal_mode=WAL")
        await self.conn.executescript('''
        CREATE TABLE IF NOT EXISTS anime (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          title TEXT NOT NULL COLLATE NOCASE,
          emoji TEXT NOT NULL DEFAULT '', url TEXT NOT NULL,
          color TEXT NOT NULL DEFAULT 'blue' CHECK(color IN ('green','blue','red')),
          post_text TEXT NOT NULL DEFAULT '', metadata_json TEXT NOT NULL DEFAULT '{}',
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
          UNIQUE(title), UNIQUE(url)
        );
        CREATE TABLE IF NOT EXISTS aliases (
          id INTEGER PRIMARY KEY AUTOINCREMENT, anime_id INTEGER NOT NULL,
          alias TEXT NOT NULL COLLATE NOCASE, UNIQUE(anime_id, alias), UNIQUE(alias),
          FOREIGN KEY(anime_id) REFERENCES anime(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_anime_title ON anime(title);
        CREATE INDEX IF NOT EXISTS idx_alias_alias ON aliases(alias);
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY, added_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS searches (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, chat_id INTEGER, query TEXT NOT NULL, created_at TEXT NOT NULL);
        ''')
        await self.conn.commit()

    async def close(self) -> None:
        if self.conn:
            await self.conn.close()
            self.conn = None

    def _db(self) -> aiosqlite.Connection:
        if not self.conn:
            raise RuntimeError("Database is not connected")
        return self.conn

    async def add_anime(self, title: str, url: str, emoji: str = '', color: str = 'blue', post_text: str = '', aliases: list[str] | None = None, metadata: dict[str, Any] | None = None) -> tuple[bool, str, int | None]:
        title = ' '.join(title.split())
        url = url.strip()
        if not title: return False, 'invalid_title', None
        if color not in {'green', 'blue', 'red'}: raise ValueError('Invalid color')
        db = self._db(); ts = now()
        try:
            async with db.execute("INSERT INTO anime(title,emoji,url,color,post_text,metadata_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)", (title, emoji.strip(), url, color, post_text.strip(), json.dumps(metadata or {}, ensure_ascii=False), ts, ts)) as cur:
                anime_id = cur.lastrowid
            for alias in aliases or []:
                alias = ' '.join(alias.split())
                if alias:
                    await db.execute("INSERT OR IGNORE INTO aliases(anime_id,alias) VALUES(?,?)", (anime_id, alias))
            await db.commit()
            return True, 'added', anime_id
        except aiosqlite.IntegrityError as exc:
            await db.rollback()
            message = str(exc).lower()
            return False, 'duplicate_url' if 'url' in message else 'duplicate_title', None

    async def get_anime(self, anime_id: int):
        async with self._db().execute("SELECT * FROM anime WHERE id=?", (anime_id,)) as cur:
            return await cur.fetchone()

    async def search_anime(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        q = ' '.join(query.split())
        like = f'%{q}%'
        sql = """SELECT DISTINCT a.*, GROUP_CONCAT(al.alias) AS aliases
                 FROM anime a LEFT JOIN aliases al ON al.anime_id=a.id
                 WHERE a.title LIKE ? OR al.alias LIKE ?
                 ORDER BY CASE WHEN lower(a.title)=lower(?) THEN 0 ELSE 1 END, a.title LIMIT ?"""
        async with self._db().execute(sql, (like, like, q, limit)) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def update_anime(self, anime_id: int, **fields) -> bool:
        allowed = {'title', 'emoji', 'url', 'color', 'post_text', 'metadata_json'}
        fields = {k: v for k, v in fields.items() if k in allowed}
        if 'title' in fields: fields['title'] = ' '.join(str(fields['title']).split())
        if not fields: return False
        fields['updated_at'] = now()
        assignments = ', '.join(f'{key}=?' for key in fields)
        try:
            cur = await self._db().execute(f"UPDATE anime SET {assignments} WHERE id=?", (*fields.values(), anime_id))
            await self._db().commit()
            return cur.rowcount == 1
        except aiosqlite.IntegrityError:
            await self._db().rollback()
            return False

    async def delete_anime(self, anime_id: int) -> bool:
        cur = await self._db().execute("DELETE FROM anime WHERE id=?", (anime_id,))
        await self._db().commit()
        return cur.rowcount == 1

    async def add_alias(self, anime_id: int, alias: str) -> bool:
        try:
            await self._db().execute("INSERT INTO aliases(anime_id,alias) VALUES(?,?)", (anime_id, ' '.join(alias.split())))
            await self._db().commit()
            return True
        except aiosqlite.IntegrityError:
            await self._db().rollback()
            return False

    async def remove_alias(self, anime_id: int, alias: str) -> bool:
        cur = await self._db().execute("DELETE FROM aliases WHERE anime_id=? AND alias=?", (anime_id, alias.strip()))
        await self._db().commit()
        return cur.rowcount == 1

    async def record_search(self, user_id: int | None, chat_id: int, query: str) -> None:
        await self._db().execute("INSERT INTO searches(user_id,chat_id,query,created_at) VALUES(?,?,?,?)", (user_id, chat_id, query[:200], now()))
        await self._db().commit()

    async def recent_searches(self, limit: int = 10) -> list[dict[str, Any]]:
        async with self._db().execute("SELECT query, chat_id, created_at FROM searches ORDER BY id DESC LIMIT ?", (limit,)) as cur:
            return [dict(row) for row in await cur.fetchall()]

    async def stats(self) -> dict[str, int]:
        async def count(table: str) -> int:
            async with self._db().execute(f"SELECT COUNT(*) FROM {table}") as cur:
                return (await cur.fetchone())[0]
        return {'anime': await count('anime'), 'aliases': await count('aliases'), 'searches': await count('searches')}

    async def all_anime(self) -> list[dict[str, Any]]:
        async with self._db().execute("SELECT a.*, GROUP_CONCAT(al.alias) AS aliases FROM anime a LEFT JOIN aliases al ON al.anime_id=a.id GROUP BY a.id ORDER BY a.id") as cur:
            rows = await cur.fetchall()
        return [dict(row) for row in rows]

    async def setting(self, key: str, default: str = '') -> str:
        async with self._db().execute("SELECT value FROM settings WHERE key=?", (key,)) as cur:
            row = await cur.fetchone()
        return row['value'] if row else default

    async def set_setting(self, key: str, value: str) -> None:
        await self._db().execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
        await self._db().commit()
