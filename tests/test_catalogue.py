import pytest

from app.database.repository import Database
from app.services.catalogue import bulk_add, make_backup, parse_line, validate_backup


def test_parse_unicode_title_and_parentheses():
    row = parse_line('🔥 Demon Slayer (TV) - https://example.com/ds - red (Watch (subbed) now)')
    assert row and row.title == 'Demon Slayer (TV)' and row.color == 'red'
    assert row.post_text == 'Watch (subbed) now'


def test_invalid_line():
    assert parse_line('not a valid record') is None

@pytest.mark.asyncio
async def test_bulk_counts_and_immediate_search(tmp_path):
    db=Database(tmp_path/'test.db'); await db.connect()
    result=await bulk_add(db, 'Naruto - https://example.com/naruto - green (Ninja)\nBad\nNaruto 2 - https://example.com/naruto - blue')
    assert result == {'received': 3, 'added': 1, 'duplicates': 1, 'invalid': 1, 'failed': 0}
    rows=await db.search_anime('nar'); assert len(rows)==1 and rows[0]['url'].endswith('naruto')
    await db.close()

@pytest.mark.asyncio
async def test_alias_persistence_and_backup(tmp_path):
    db=Database(tmp_path/'test.db'); await db.connect()
    ok,_,aid=await db.add_anime('Solo Leveling','https://example.com/solo', aliases=['SL'])
    assert ok and (await db.search_anime('sl'))[0]['title']=='Solo Leveling'
    payload=make_backup(await db.all_anime()); records=validate_backup(payload)
    assert records[0]['title']=='Solo Leveling' and records[0]['aliases']==['SL']
    await db.close()
