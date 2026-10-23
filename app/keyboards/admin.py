from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def admin_panel() -> InlineKeyboardMarkup:
    labels = [('📊 Statistics','stats'),('➕ Add Anime','add'),('📦 Bulk Add Anime','bulk'),('✏️ Edit Anime','edit'),('🗑 Delete Anime','delete'),('🔗 Manage Links','links'),('📝 Manage Posts','posts'),('🖼 Manage Posters','posters'),('🔤 Manage Aliases','aliases'),('🔒 Force Sub Settings','force_sub'),('👥 Manage Admins','admins'),('🔎 Recent Searches','recent'),('🏞 Start Image','start_image'),('💬 Welcome Message','welcome'),('📥 Anime Links Backup','backup'),('📤 Anime Links Restore','restore'),('⚙️ Bot Settings','settings')]
    b=InlineKeyboardBuilder()
    for label, data in labels: b.button(text=label, callback_data=f'admin:{data}')
    b.button(text='❌ Close Panel', callback_data='admin:close'); b.adjust(2)
    return b.as_markup()


def back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='🔙 Back to Admin Panel', callback_data='admin:back')]])
