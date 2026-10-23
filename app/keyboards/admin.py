from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def admin_panel() -> InlineKeyboardMarkup:
    labels = [
        ('📊 Statistics', 'stats'), ('➕ Add Anime', 'add'), ('📦 Bulk Add Anime', 'bulk'),
        ('✏️ Edit Anime', 'edit'), ('🗑 Delete Anime', 'delete'), ('🔗 Manage Links', 'links'),
        ('📝 Manage Posts', 'posts'), ('🖼 Manage Posters', 'posters'), ('🔤 Manage Aliases', 'aliases'),
        ('🔒 Force Sub Settings', 'force_sub'), ('👥 Manage Admins', 'admins'), ('🔎 Recent Searches', 'recent'),
        ('🏞 Start Image', 'start_image'), ('💬 Welcome Message', 'welcome'), ('📝 Post Text', 'post_text'),
        ('📥 Anime Links Backup', 'backup'), ('📤 Anime Links Restore', 'restore'), ('⚙️ Bot Settings', 'settings'),
    ]
    builder = InlineKeyboardBuilder()
    for label, data in labels: builder.button(text=label, callback_data=f'admin:{data}')
    builder.button(text='❌ Close Panel', callback_data='admin:close')
    builder.adjust(2)
    return builder.as_markup()


def back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='🔙 Back to Admin Panel', callback_data='admin:back')]])


def post_text_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='✏️ Edit Post Text', callback_data='posttext:edit')],
        [InlineKeyboardButton(text='👁 Preview Post Text', callback_data='posttext:preview')],
        [InlineKeyboardButton(text='🔙 Back', callback_data='admin:back')],
    ])


def posts_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='🖼 Set Landscape Poster', callback_data='poster:set')],
        [InlineKeyboardButton(text='👁 Preview Current Poster', callback_data='poster:preview')],
        [InlineKeyboardButton(text='🗑 Remove Landscape Poster', callback_data='poster:remove')],
        [InlineKeyboardButton(text='🔙 Back', callback_data='admin:back')],
    ])


def confirm_remove_poster() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='✅ Confirm removal', callback_data='poster:confirm_remove')],
        [InlineKeyboardButton(text='❌ Cancel', callback_data='admin:posts')],
    ])
