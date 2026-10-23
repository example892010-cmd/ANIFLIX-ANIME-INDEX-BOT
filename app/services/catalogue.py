from __future__ import annotations

import json
import re
from dataclasses import dataclass
from urllib.parse import urlparse

from app.database.repository import Database

DEFAULT_POST_TEXT = """🍥 {anime_title}

🎭 Genre: Action | Adventure | Comedy
🎙️ Audio: Tamil
📺 Quality: 480p | 720p | 1080p

👇 Click the below button to download episodes!

⚠️ If Any Issues, Message here:
https://t.me/+4YfcdPoSdK9jYmVl

🔗 Click the below button to join!"""

@dataclass
class ParsedLine:
    title: str
    url: str
    color: str = 'blue'
    emoji: str = ''
    post_text: str = ''


def _outer_parenthesized(value: str) -> tuple[str, str]:
    """Remove only a final outer (...) block, preserving nested parentheses."""
    value = value.rstrip()
    if not value.endswith(')'):
        return value, ''
    depth = 0
    opening = -1
    for index in range(len(value) - 1, -1, -1):
        if value[index] == ')': depth += 1
        elif value[index] == '(':
            depth -= 1
            if depth == 0:
                opening = index
                break
    if opening < 0: return value, ''
    return value[:opening].rstrip(), value[opening + 1:-1].strip()


def parse_line(line: str) -> ParsedLine | None:
    raw = line.strip()
    if not raw: return None
    before_text, post_text = _outer_parenthesized(raw)
    # Work from the URL marker, so title hyphens and punctuation remain valid.
    match = re.match(r'^(?P<prefix>.+?)\s*-\s*(?P<url>https?://\S+)(?P<tail>.*)$', before_text, re.I)
    if not match: return None
    url = match.group('url').rstrip('.,')
    parsed = urlparse(url)
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc: return None
    tail = match.group('tail').strip()
    color = 'blue'
    color_match = re.fullmatch(r'-\s*(green|blue|red)', tail, re.I)
    if tail and not color_match: return None
    if color_match: color = color_match.group(1).lower()
    prefix = match.group('prefix').strip()
    emoji_match = re.match(r'^(?P<emoji>[^\w\s])\s*(?P<title>.+)$', prefix, re.UNICODE)
    emoji = emoji_match.group('emoji') if emoji_match else ''
    title = (emoji_match.group('title') if emoji_match else prefix).strip()
    if not title: return None
    return ParsedLine(' '.join(title.split()), url, color, emoji, post_text)


async def bulk_add(db: Database, content: str) -> dict[str, int | list[dict[str, str]]]:
    result: dict[str, int | list[dict[str, str]]] = {'received': 0, 'added': 0, 'duplicates': 0, 'invalid': 0, 'failed': 0, 'errors': []}
    for line_number, line in enumerate(content.splitlines(), 1):
        if not line.strip(): continue
        result['received'] = int(result['received']) + 1
        parsed = parse_line(line)
        if not parsed:
            result['invalid'] = int(result['invalid']) + 1
            result['errors'].append({'line': str(line_number), 'reason': 'Expected title - http(s) URL - color (optional text)'})
            continue
        try:
            ok, reason, _ = await db.add_anime(parsed.title, parsed.url, parsed.emoji, parsed.color, parsed.post_text)
        except Exception as exc:
            result['failed'] = int(result['failed']) + 1
            result['errors'].append({'line': str(line_number), 'reason': f'database error: {type(exc).__name__}'})
            continue
        if ok: result['added'] = int(result['added']) + 1
        elif reason.startswith('duplicate'):
            result['duplicates'] = int(result['duplicates']) + 1
            result['errors'].append({'line': str(line_number), 'reason': reason})
        else:
            result['failed'] = int(result['failed']) + 1
            result['errors'].append({'line': str(line_number), 'reason': reason})
    return result


def make_backup(rows: list[dict]) -> bytes:
    records = []
    for row in rows:
        records.append({'id': row['id'], 'title': row['title'], 'emoji': row['emoji'], 'url': row['url'], 'color': row['color'], 'post_text': row['post_text'], 'aliases': [a for a in (row.get('aliases') or '').split(',') if a], 'metadata': json.loads(row.get('metadata_json') or '{}')})
    return json.dumps({'format': 'aniflix-backup', 'version': 1, 'records': records}, ensure_ascii=False, indent=2).encode('utf-8')


def validate_backup(payload: bytes, max_bytes: int = 5_000_000) -> list[dict]:
    if len(payload) > max_bytes: raise ValueError('Backup file is too large')
    try: data = json.loads(payload)
    except json.JSONDecodeError as exc: raise ValueError('Backup is not valid JSON') from exc
    records = data.get('records')
    if data.get('format') != 'aniflix-backup' or data.get('version') != 1 or not isinstance(records, list): raise ValueError('Unsupported backup structure')
    for record in records:
        if not isinstance(record, dict) or not all(isinstance(record.get(key), str) and record[key].strip() for key in ('title', 'url')): raise ValueError('Each record needs title and URL')
        if urlparse(record['url']).scheme not in {'http', 'https'} or not urlparse(record['url']).netloc: raise ValueError('Backup contains an invalid URL')
        if record.get('color', 'blue') not in {'green', 'blue', 'red'}: raise ValueError('Invalid button color')
    return records


async def restore(db: Database, records: list[dict]) -> dict[str, int]:
    out = {'added': 0, 'skipped': 0, 'failed': 0}
    for record in records:
        try:
            ok, reason, _ = await db.add_anime(record['title'], record['url'], record.get('emoji', ''), record.get('color', 'blue'), record.get('post_text', ''), record.get('aliases', []), record.get('metadata', {}))
        except Exception:
            ok, reason = False, 'failed'
        if ok: out['added'] += 1
        elif reason.startswith('duplicate'): out['skipped'] += 1
        else: out['failed'] += 1
    return out


def render_post_text(template: str, title: str) -> str:
    if not template.strip(): template = DEFAULT_POST_TEXT
    return template.replace('{anime_title}', title)
