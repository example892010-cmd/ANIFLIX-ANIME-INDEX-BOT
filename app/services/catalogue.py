from __future__ import annotations

import json
import re
from dataclasses import dataclass
from urllib.parse import urlparse

from app.database.repository import Database

LINE_RE = re.compile(r'^\s*(?P<emoji>[^\w\s-])?\s*(?P<title>.+?)\s*-\s*(?P<url>https?://\S+)\s*-\s*(?P<color>green|blue|red)\s*(?:\((?P<text>.*)\))?\s*$', re.I)

@dataclass
class ParsedLine:
    title: str; url: str; color: str; emoji: str = ''; post_text: str = ''

def parse_line(line: str) -> ParsedLine | None:
    m = LINE_RE.match(line)
    if not m: return None
    title = m.group('title').strip(); url = m.group('url').strip().rstrip('.,')
    parsed = urlparse(url)
    if not title or parsed.scheme not in {'http','https'} or not parsed.netloc: return None
    emoji = (m.group('emoji') or '').strip()
    return ParsedLine(title, url, m.group('color').lower(), emoji, (m.group('text') or '').strip())

async def bulk_add(db: Database, content: str) -> dict[str, int]:
    result = {'received': 0, 'added': 0, 'duplicates': 0, 'invalid': 0, 'failed': 0}
    for line in content.splitlines():
        if not line.strip(): continue
        result['received'] += 1; parsed = parse_line(line)
        if not parsed: result['invalid'] += 1; continue
        ok, reason, _ = await db.add_anime(parsed.title, parsed.url, parsed.emoji, parsed.color, parsed.post_text)
        if ok: result['added'] += 1
        elif reason.startswith('duplicate'): result['duplicates'] += 1
        else: result['failed'] += 1
    return result

def make_backup(rows: list[dict]) -> bytes:
    records = []
    for row in rows:
        records.append({'id': row['id'], 'title': row['title'], 'emoji': row['emoji'], 'url': row['url'], 'color': row['color'], 'post_text': row['post_text'], 'aliases': [a for a in (row.get('aliases') or '').split(',') if a], 'metadata': json.loads(row.get('metadata_json') or '{}')})
    return json.dumps({'format': 'aniflix-backup', 'version': 1, 'records': records}, ensure_ascii=False, indent=2).encode()

def validate_backup(payload: bytes, max_bytes: int = 5_000_000) -> list[dict]:
    if len(payload) > max_bytes: raise ValueError('Backup file is too large')
    data = json.loads(payload); records = data.get('records')
    if data.get('format') != 'aniflix-backup' or data.get('version') != 1 or not isinstance(records, list): raise ValueError('Unsupported backup structure')
    for r in records:
        if not all(isinstance(r.get(k), str) and r[k].strip() for k in ('title','url')): raise ValueError('Each record needs title and URL')
        if r.get('color','blue') not in {'green','blue','red'}: raise ValueError('Invalid button color')
    return records

async def restore(db: Database, records: list[dict]) -> dict[str, int]:
    out = {'added': 0, 'skipped': 0, 'failed': 0}
    for r in records:
        ok, reason, _ = await db.add_anime(r['title'], r['url'], r.get('emoji',''), r.get('color','blue'), r.get('post_text',''), r.get('aliases',[]), r.get('metadata',{}))
        if ok: out['added'] += 1
        elif reason.startswith('duplicate'): out['skipped'] += 1
        else: out['failed'] += 1
    return out
