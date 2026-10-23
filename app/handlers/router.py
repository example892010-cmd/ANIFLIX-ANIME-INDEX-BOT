from __future__ import annotations

import io
import logging
from pathlib import Path

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.config import Settings
from app.database.repository import Database
from app.keyboards.admin import admin_panel, back
from app.services.catalogue import bulk_add, make_backup, restore, validate_backup
from app.utils.formatting import esc, trim

log = logging.getLogger(__name__)

def build_router(db: Database, settings: Settings) -> Router:
    router=Router()
    def authorized(user_id: int|None) -> bool: return settings.is_admin(user_id)

    @router.message(CommandStart())
    async def start(message: Message):
        welcome = await db.setting('welcome_message', 'Welcome to ANIFLIX ANIME INDEX BOT. Send an anime name to search.')
        await message.answer(welcome)

    @router.message(Command('admin'))
    async def admin(message: Message):
        if not authorized(message.from_user.id if message.from_user else None): return await message.answer('You are not authorized to use the admin panel.')
        await message.answer('ANIFLIX Admin Panel', reply_markup=admin_panel())

    @router.callback_query(F.data.startswith('admin:'))
    async def admin_callback(call: CallbackQuery):
        if not authorized(call.from_user.id): return await call.answer('Not authorized', show_alert=True)
        action=call.data.split(':',1)[1]
        if action=='close': await call.message.delete(); return await call.answer()
        if action in {'back'}: await call.message.edit_text('ANIFLIX Admin Panel', reply_markup=admin_panel()); return await call.answer()
        if action=='stats':
            s=await db.stats(); text=f"📊 <b>Statistics</b>\nAnime: {s['anime']}\nAliases: {s['aliases']}\nSearches: {s['searches']}"
        elif action=='backup':
            payload=make_backup(await db.all_anime()); await call.message.answer_document(__import__('aiogram').types.BufferedInputFile(payload, filename='ANIFLIX_Anime_Backup.json'), caption=f"Exported {len(await db.all_anime())} records."); return await call.answer()
        elif action=='bulk': text='Send the bulk list as your next message. Format: 🍥 Title - https://example.com - green (post text)'
        elif action=='add': text='Send one line in the bulk format to add an anime.'
        elif action=='posts': text='📝 Manage Posts\nUse /setposter after sending a landscape photo. The shared poster is used for all results.'
        elif action=='posters': text='🖼 Individual poster management is not enabled; the shared landscape poster is managed from 📝 Manage Posts.'
        elif action=='force_sub': text='🔒 Force subscription is disabled by default. Configure channels in the database settings before enabling it.'
        elif action=='welcome': text='💬 Use /setwelcome <message> to configure the start message.'
        elif action=='start_image': text='🏞 Use /setstartimage after sending a photo, or /removestartimage.'
        elif action=='settings': text='⚙️ Settings\nSQLite database and shared media paths are configured with DATABASE_PATH and MEDIA_DIR.'
        elif action=='admins': text='👥 Additional admins are configured with ADMIN_IDS. Only OWNER_ID can change this deployment setting.'
        elif action=='recent': text='🔎 Recent searches are retained as query/chat counters for admin statistics; avoid storing sensitive queries.'
        elif action=='links': text='🔗 Links are edited through the anime add/edit workflow and validated as HTTP(S) URLs.'
        elif action=='aliases': text='🔤 Add aliases through the database service or future admin edit flow; aliases participate in search.'
        elif action=='edit': text='✏️ Send /edit <anime id> <new title> for a safe title edit.'
        elif action=='delete': text='🗑 Send /delete <anime id> to delete after confirmation.'
        elif action=='restore': text='📤 Upload ANIFLIX_Anime_Backup.json; restore is validated and never deletes existing records.'
        else: text='This admin feature is available with safe configuration guidance.'
        await call.message.edit_text(text, reply_markup=back(), parse_mode='HTML'); await call.answer()

    @router.message(Command('setwelcome'))
    async def setwelcome(message: Message):
        if not authorized(message.from_user.id if message.from_user else None): return
        value=message.text.partition(' ')[2].strip()
        if not value: return await message.answer('Usage: /setwelcome your welcome message')
        await db.set_setting('welcome_message', trim(value, 1000)); await message.answer('Welcome message saved.')

    @router.message(Command('setposter'))
    async def setposter(message: Message):
        if not authorized(message.from_user.id if message.from_user else None): return
        if not message.photo: return await message.answer('Reply to a photo with /setposter.')
        photo=message.photo[-1]
        if photo.width < photo.height: await message.answer('Warning: this is portrait; a landscape 16:9 image is recommended.')
        await db.set_setting('shared_poster_file_id', photo.file_id); await message.answer('Shared landscape poster saved.')

    @router.message(F.document)
    async def restore_document(message: Message):
        if not authorized(message.from_user.id if message.from_user else None) or not message.document: return
        if message.document.file_name != 'ANIFLIX_Anime_Backup.json': return
        if message.document.file_size and message.document.file_size > 5_000_000: return await message.answer('Backup is too large.')
        f=await message.bot.get_file(message.document.file_id); data=io.BytesIO(); await message.bot.download_file(f.file_path, data)
        try: records=validate_backup(data.getvalue())
        except Exception as exc: return await message.answer(f'Invalid backup: {esc(str(exc))}')
        result=await restore(db, records); await message.answer(f"Restore complete. Added: {result['added']}, skipped duplicates: {result['skipped']}, failed: {result['failed']}.")

    @router.message(F.text & ~F.text.startswith('/'))
    async def search_or_bulk(message: Message):
        if not message.text or message.text.startswith('/') or (message.from_user and message.from_user.is_bot): return
        if authorized(message.from_user.id if message.from_user else None) and '\n' in message.text:
            result=await bulk_add(db, message.text); return await message.answer(f"📦 Received: {result['received']}\n✅ Added: {result['added']}\n⏭ Duplicates: {result['duplicates']}\n⚠️ Invalid: {result['invalid']}\n❌ Failed: {result['failed']}")
        rows=await db.search_anime(message.text); await db.record_search(message.from_user.id if message.from_user else None, message.chat.id, message.text)
        if not rows: return await message.answer('No anime found. Try another title or alias.')
        for row in rows:
            text=f"{esc(row['emoji'])} <b>{esc(row['title'])}</b>\n{esc(row['post_text'])}".strip()
            kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='⬇️ Download', url=row['url'])]])
            poster=await db.setting('shared_poster_file_id')
            if poster:
                try: await message.answer_photo(poster, caption=trim(text), reply_markup=kb, parse_mode='HTML'); continue
                except Exception: log.exception('Shared poster unavailable; using text fallback')
            await message.answer(trim(text), reply_markup=kb, parse_mode='HTML')

    return router
