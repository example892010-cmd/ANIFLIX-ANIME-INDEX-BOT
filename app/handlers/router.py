from __future__ import annotations

import io
import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.config import Settings
from app.database.repository import Database
from app.keyboards.admin import admin_panel, back, confirm_remove_poster, post_text_menu, posts_menu
from app.services.catalogue import DEFAULT_POST_TEXT, bulk_add, make_backup, render_post_text, restore, validate_backup
from app.utils.formatting import esc, trim

log = logging.getLogger(__name__)


def build_router(db: Database, settings: Settings) -> Router:
    router = Router()
    pending: dict[int, str] = {}
    pending_restore: dict[int, list[dict]] = {}

    def authorized(user_id: int | None) -> bool:
        return settings.is_admin(user_id)

    def user_id(message: Message) -> int | None:
        return message.from_user.id if message.from_user else None

    @router.message(CommandStart())
    async def start(message: Message):
        welcome = await db.setting('welcome_message', 'Welcome to ANIFLIX ANIME INDEX BOT. Send an anime name to search.')
        start_image = await db.setting('start_image_file_id')
        if start_image:
            try:
                await message.answer_photo(start_image, caption=welcome)
                return
            except Exception:
                log.exception('Configured start image unavailable; using text fallback')
        await message.answer(welcome)

    @router.message(Command('admin'))
    async def admin(message: Message):
        if not authorized(user_id(message)):
            await message.answer('You are not authorized to use the admin panel.')
            return
        await message.answer('ANIFLIX Admin Panel', reply_markup=admin_panel())

    @router.callback_query(F.data.startswith('admin:'))
    async def admin_callback(call: CallbackQuery):
        if not authorized(call.from_user.id):
            await call.answer('Not authorized', show_alert=True)
            return
        action = call.data.split(':', 1)[1]
        if action == 'close':
            await call.message.delete(); await call.answer(); return
        if action == 'back':
            await call.message.edit_text('ANIFLIX Admin Panel', reply_markup=admin_panel()); await call.answer(); return
        if action == 'stats':
            stats = await db.stats()
            text = f"📊 <b>Statistics</b>\nAnime: {stats['anime']}\nAliases: {stats['aliases']}\nSearches: {stats['searches']}"
        elif action == 'recent':
            rows = await db.recent_searches()
            text = '🔎 <b>Recent Searches</b>\n' + ('\n'.join(f"• {esc(row['query'])} ({row['created_at'][:19]})" for row in rows) if rows else 'No searches recorded.')
        elif action == 'backup':
            rows = await db.all_anime(); payload = make_backup(rows)
            await call.message.answer_document(BufferedInputFile(payload, filename='ANIFLIX_Anime_Backup.json'), caption=f'Exported {len(rows)} records.')
            await call.answer(); return
        elif action == 'bulk':
            pending[call.from_user.id] = 'bulk'
            text = '📦 Send the next message as one anime per line:\n`🍥 Title - https://example.com - green (post text)`\n\nSend /cancel to cancel.'
        elif action == 'add':
            pending[call.from_user.id] = 'add'
            text = '➕ Send one anime line in the bulk format. Color and post text are optional. Send /cancel to cancel.'
        elif action == 'post_text':
            text = '📝 <b>Post Text</b>\nThis global template is used when an anime has no individual custom post text. The {anime_title} placeholder is replaced at render time.'
            await call.message.edit_text(text, reply_markup=post_text_menu(), parse_mode='HTML'); await call.answer(); return
        elif action == 'posts':
            await call.message.edit_text('📝 <b>Manage Posts</b>\nThis menu controls the one shared landscape image. It is separate from global 📝 Post Text.', reply_markup=posts_menu(), parse_mode='HTML'); await call.answer(); return
        elif action == 'edit': text = '✏️ Use /edit &lt;id&gt; &lt;new title&gt; to update an anime title safely.'
        elif action == 'delete': text = '🗑 Use /delete &lt;id&gt; and confirm the inline prompt.'
        elif action == 'links': text = '🔗 Use /setlink &lt;id&gt; &lt;https URL&gt; to update a saved download link.'
        elif action == 'aliases': text = '🔤 Use /addalias &lt;id&gt; &lt;alias&gt; or /removealias &lt;id&gt; &lt;alias&gt;. Aliases are searchable immediately.'
        elif action == 'welcome': text = '💬 Use /setwelcome &lt;message&gt; to save a welcome message. It persists in SQLite.'
        elif action == 'start_image': text = '🏞 Reply to a photo with /setstartimage, or use /removestartimage.'
        elif action == 'restore': text = '📤 Upload ANIFLIX_Anime_Backup.json. The bot validates it and asks for confirmation before importing.'
        elif action == 'posters': text = '🖼 Individual anime posters are optional and separate from the shared landscape poster.'
        elif action == 'force_sub': text = '🔒 Force subscription is disabled by default. Configure required channels in persistent settings before enabling it.'
        elif action == 'admins': text = '👥 Authorized IDs come from OWNER_ID and ADMIN_IDS. Group administrator status never grants panel access.'
        elif action == 'settings': text = '⚙️ Active settings: SQLite path, media path, welcome message, global post text, shared poster, and start image.'
        else: text = 'This setting is configured from the documented commands and persistent SQLite settings.'
        await call.message.edit_text(text, reply_markup=back(), parse_mode='HTML'); await call.answer()

    @router.callback_query(F.data.startswith('posttext:'))
    async def post_text_callback(call: CallbackQuery):
        if not authorized(call.from_user.id): return await call.answer('Not authorized', show_alert=True)
        action = call.data.split(':', 1)[1]
        if action == 'edit':
            pending[call.from_user.id] = 'post_text'
            await call.message.edit_text('✏️ Send the complete new global post-text template now. Use {anime_title} where the title should appear. /cancel cancels.', reply_markup=back()); return await call.answer()
        template = await db.setting('global_post_text', DEFAULT_POST_TEXT)
        preview = trim(render_post_text(template, 'Sample Anime'))
        await call.message.edit_text(f'👁 <b>Preview</b>\n\n{esc(preview)}', reply_markup=post_text_menu(), parse_mode='HTML'); await call.answer()

    @router.callback_query(F.data.startswith('poster:'))
    async def poster_callback(call: CallbackQuery):
        if not authorized(call.from_user.id): return await call.answer('Not authorized', show_alert=True)
        action = call.data.split(':', 1)[1]
        if action == 'set':
            pending[call.from_user.id] = 'shared_poster'; await call.message.edit_text('🖼 Send a landscape photo now. The current poster is kept until the new image is received successfully.', reply_markup=back()); await call.answer(); return
        if action == 'preview':
            file_id = await db.setting('shared_poster_file_id')
            if not file_id: await call.message.edit_text('No shared landscape poster is configured.', reply_markup=posts_menu()); await call.answer(); return
            try: await call.message.answer_photo(file_id, caption='Current shared landscape poster.')
            except Exception: await call.message.answer('The configured poster could not be retrieved; text-only fallback remains active.')
            await call.answer(); return
        if action == 'remove':
            await call.message.edit_text('Remove the shared landscape poster? Anime records and URLs will not be changed.', reply_markup=confirm_remove_poster()); await call.answer(); return
        await db.set_setting('shared_poster_file_id', '')
        await call.message.edit_text('Shared landscape poster removed. Results will use text-only fallback.', reply_markup=posts_menu()); await call.answer()

    @router.callback_query(F.data == 'restore:confirm')
    async def confirm_restore(call: CallbackQuery):
        if not authorized(call.from_user.id): return await call.answer('Not authorized', show_alert=True)
        records = pending_restore.pop(call.from_user.id, [])
        result = await restore(db, records)
        await call.message.edit_text(f"Restore complete. Added: {result['added']}, skipped duplicates: {result['skipped']}, failed: {result['failed']}.", reply_markup=back()); await call.answer()

    @router.message(Command('cancel'))
    async def cancel(message: Message):
        pending.pop(user_id(message), None); pending_restore.pop(user_id(message), None); await message.answer('Cancelled.')

    @router.message(Command('setwelcome'))
    async def setwelcome(message: Message):
        if not authorized(user_id(message)): return
        value = message.text.partition(' ')[2].strip()
        if not value: return await message.answer('Usage: /setwelcome your welcome message')
        await db.set_setting('welcome_message', trim(value, 1000)); await message.answer('Welcome message saved.')

    @router.message(Command('setlink'))
    async def setlink(message: Message):
        if not authorized(user_id(message)): return
        parts = message.text.split(maxsplit=2)
        if len(parts) != 3 or not parts[1].isdigit() or not parts[2].startswith(('http://', 'https://')): return await message.answer('Usage: /setlink <id> <http(s) URL>')
        ok = await db.update_anime(int(parts[1]), url=parts[2]); await message.answer('Download link updated.' if ok else 'Could not update link; check the ID or duplicate URL.')

    @router.message(Command('edit'))
    async def edit(message: Message):
        if not authorized(user_id(message)): return
        parts = message.text.split(maxsplit=2)
        if len(parts) != 3 or not parts[1].isdigit(): return await message.answer('Usage: /edit <id> <new title>')
        ok = await db.update_anime(int(parts[1]), title=parts[2]); await message.answer('Anime updated.' if ok else 'Could not update anime; check the ID or duplicate title.')

    @router.message(Command('delete'))
    async def delete(message: Message):
        if not authorized(user_id(message)): return
        parts = message.text.split()
        if len(parts) != 2 or not parts[1].isdigit(): return await message.answer('Usage: /delete <id>')
        anime_id = int(parts[1]); row = await db.get_anime(anime_id)
        if not row: return await message.answer('Anime not found.')
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='✅ Confirm delete', callback_data=f'delete:confirm:{anime_id}'), InlineKeyboardButton(text='❌ Cancel', callback_data='admin:back')]])
        await message.answer(f"Delete <b>{esc(row['title'])}</b>?", reply_markup=keyboard, parse_mode='HTML')

    @router.callback_query(F.data.startswith('delete:confirm:'))
    async def confirm_delete(call: CallbackQuery):
        if not authorized(call.from_user.id): return await call.answer('Not authorized', show_alert=True)
        ok = await db.delete_anime(int(call.data.rsplit(':', 1)[1])); await call.message.edit_text('Anime deleted.' if ok else 'Anime was not found.'); await call.answer()

    @router.message(Command('addalias'))
    async def addalias(message: Message):
        if not authorized(user_id(message)): return
        parts = message.text.split(maxsplit=2)
        if len(parts) != 3 or not parts[1].isdigit(): return await message.answer('Usage: /addalias <id> <alias>')
        await message.answer('Alias added.' if await db.add_alias(int(parts[1]), parts[2]) else 'Alias could not be added; it may already exist.')

    @router.message(Command('removealias'))
    async def removealias(message: Message):
        if not authorized(user_id(message)): return
        parts = message.text.split(maxsplit=2)
        if len(parts) != 3 or not parts[1].isdigit(): return await message.answer('Usage: /removealias <id> <alias>')
        await message.answer('Alias removed.' if await db.remove_alias(int(parts[1]), parts[2]) else 'Alias was not found.')

    @router.message(Command('setposter', 'setstartimage'))
    async def set_image(message: Message):
        if not authorized(user_id(message)): return
        pending[user_id(message)] = 'start_image' if message.text.startswith('/setstartimage') else 'shared_poster'
        await message.answer('Reply to this command with a landscape photo, or send the photo next.')

    @router.message(Command('removestartimage'))
    async def remove_start_image(message: Message):
        if authorized(user_id(message)): await db.set_setting('start_image_file_id', ''); await message.answer('Start image removed.')

    @router.message(F.photo)
    async def photo_upload(message: Message):
        uid = user_id(message)
        if not authorized(uid) or not message.photo: return
        mode = pending.get(uid)
        if mode not in {'shared_poster', 'start_image'}: return
        photo = message.photo[-1]
        if mode == 'shared_poster':
            await db.set_setting('shared_poster_file_id', photo.file_id); message_text = 'Shared landscape poster saved.'
            if photo.width < photo.height: message_text += ' Warning: portrait images are not ideal for the requested landscape layout.'
        else:
            await db.set_setting('start_image_file_id', photo.file_id); message_text = 'Start image saved.'
        pending.pop(uid, None); await message.answer(message_text)

    @router.message(F.document)
    async def restore_document(message: Message):
        uid = user_id(message)
        if not authorized(uid) or not message.document or message.document.file_name != 'ANIFLIX_Anime_Backup.json': return
        if message.document.file_size and message.document.file_size > 5_000_000: return await message.answer('Backup is too large.')
        file = await message.bot.get_file(message.document.file_id); data = io.BytesIO(); await message.bot.download_file(file.file_path, data)
        try: records = validate_backup(data.getvalue())
        except ValueError as exc: return await message.answer(f'Invalid backup: {esc(str(exc))}')
        pending_restore[uid] = records
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='✅ Confirm restore', callback_data='restore:confirm'), InlineKeyboardButton(text='❌ Cancel', callback_data='admin:back')]])
        await message.answer(f'Validated {len(records)} records. Existing records will be preserved; duplicates will be skipped. Apply restore?', reply_markup=keyboard)

    @router.message(F.text & ~F.text.startswith('/'))
    async def text_message(message: Message):
        uid = user_id(message)
        if not message.text or (message.from_user and message.from_user.is_bot): return
        mode = pending.get(uid)
        if authorized(uid) and mode == 'post_text':
            await db.set_setting('global_post_text', message.text); pending.pop(uid, None); await message.answer('Global post text saved and active immediately.')
            return
        if authorized(uid) and mode in {'bulk', 'add'}:
            result = await bulk_add(db, message.text); pending.pop(uid, None)
            errors = result['errors'][:5]
            detail = '\n'.join(f"Line {item['line']}: {item['reason']}" for item in errors)
            report = f"📦 Received: {result['received']}\n✅ Added: {result['added']}\n⏭ Duplicates: {result['duplicates']}\n⚠️ Invalid: {result['invalid']}\n❌ Failed: {result['failed']}"
            await message.answer(report + (f'\n\nDetails:\n{detail}' if detail else ''))
            return
        rows = await db.search_anime(message.text); await db.record_search(uid, message.chat.id, message.text)
        if not rows: return await message.answer('No anime found. Try another title or alias.')
        global_template = await db.setting('global_post_text', DEFAULT_POST_TEXT)
        for row in rows:
            template = row['post_text'] or global_template
            text = trim(render_post_text(template, row['title']))
            if row['emoji'] and '{anime_title}' not in template: text = f"{row['emoji']} {text}"
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='⬇️ Download', url=row['url'])]])
            poster = await db.setting('shared_poster_file_id')
            if poster:
                try:
                    if len(text) <= 1024: await message.answer_photo(poster, caption=esc(text), reply_markup=keyboard, parse_mode='HTML'); continue
                    await message.answer_photo(poster); await message.answer(text, reply_markup=keyboard)
                    continue
                except Exception: log.exception('Shared poster unavailable; using text fallback')
            await message.answer(esc(text), reply_markup=keyboard, parse_mode='HTML')

    return router
