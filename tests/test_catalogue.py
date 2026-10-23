import pytest

from app.database.repository import Database
from app.services.catalogue import DEFAULT_POST_TEXT, bulk_add, make_backup, parse_line, render_post_text, validate_backup


def test_parse_unicode_title_optional_emoji_and_nested_parentheses():
    row = parse_line('🔥 Demon Slayer (TV) - https://example.com/ds - red (Watch (subbed) now)')
    assert row and row.title == 'Demon Slayer (TV)' and row.color == 'red'
    assert row.post_text == 'Watch (subbed) now'
    assert parse_line('My Hero: Academia - https://example.com/mha')


def test_invalid_lines_and_urls():
    assert parse_line('not a valid record') is None
    assert parse_line('Title - not-a-url - green') is None
    assert parse_line('Title - https:// - green') is None
    assert parse_line('Title - https://example.com - purple') is None


@pytest.mark.asyncio
async def test_55_valid_entries_are_saved_and_retrievable(tmp_path):
    db = Database(tmp_path / 'test.db'); await db.connect()
    content = '\n'.join(f'🍥 Anime {index} - https://example.com/anime-{index} - blue (Entry {index})' for index in range(55))
    result = await bulk_add(db, content)
    assert {key: result[key] for key in ('received', 'added', 'duplicates', 'invalid', 'failed')} == {'received': 55, 'added': 55, 'duplicates': 0, 'invalid': 0, 'failed': 0}
    assert len(await db.all_anime()) == 55
    assert (await db.search_anime('Anime 37'))[0]['url'] == 'https://example.com/anime-37'
    await db.close()


@pytest.mark.asyncio
async def test_mixed_batch_keeps_valid_entries_and_repeated_batches(tmp_path):
    db = Database(tmp_path / 'test.db'); await db.connect()
    first = await bulk_add(db, 'Naruto - https://example.com/naruto - green (Ninja)\nBad line\nNaruto 2 - https://example.com/naruto - blue')
    assert {key: first[key] for key in ('received', 'added', 'duplicates', 'invalid', 'failed')} == {'received': 3, 'added': 1, 'duplicates': 1, 'invalid': 1, 'failed': 0}
    second = await bulk_add(db, 'Solo Leveling - https://example.com/solo - blue\nDemon Slayer - https://example.com/ds - red')
    assert second['added'] == 2
    rows = await db.search_anime('nar'); assert len(rows) == 1 and rows[0]['url'].endswith('naruto')
    await db.close()


@pytest.mark.asyncio
async def test_alias_crud_post_text_and_restart_persistence(tmp_path):
    path = tmp_path / 'test.db'
    db = Database(path); await db.connect()
    ok, _, anime_id = await db.add_anime('Solo Leveling', 'https://example.com/solo', aliases=['SL'])
    assert ok and (await db.search_anime('sl'))[0]['title'] == 'Solo Leveling'
    assert await db.update_anime(anime_id, title='Solo Leveling: Season 1', url='https://example.com/solo-s1')
    assert await db.add_alias(anime_id, 'SLS1')
    assert await db.set_setting('global_post_text', '🍥 {anime_title}\nQuality: 480p | 720p | 1080p') is None
    await db.close()
    db2 = Database(path); await db2.connect()
    assert (await db2.search_anime('SLS1'))[0]['url'].endswith('solo-s1')
    assert render_post_text(await db2.setting('global_post_text'), 'Sample') == '🍥 Sample\nQuality: 480p | 720p | 1080p'
    assert DEFAULT_POST_TEXT.count('480p | 720p | 1080p') == 1
    assert await db2.delete_anime(anime_id)
    await db2.close()


@pytest.mark.asyncio
async def test_backup_roundtrip_and_validation(tmp_path):
    db = Database(tmp_path / 'test.db'); await db.connect()
    await db.add_anime('Backup Anime', 'https://example.com/backup', aliases=['BA'])
    payload = make_backup(await db.all_anime()); records = validate_backup(payload)
    assert records[0]['title'] == 'Backup Anime' and records[0]['aliases'] == ['BA']
    with pytest.raises(ValueError): validate_backup(b'{"format":"wrong"}')
    await db.close()
