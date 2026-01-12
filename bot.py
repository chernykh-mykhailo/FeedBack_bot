import asyncio
import logging
import sys
from typing import Optional, Union

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message, KeyboardButtonRequestChat, ReplyKeyboardMarkup, 
    KeyboardButton, ChatShared, InlineKeyboardMarkup, InlineKeyboardButton,
    CallbackQuery, FSInputFile
)
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import config
import database as db

# Logging setup
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher()

# --- STATES ---
class SettingsStates(StatesGroup):
    waiting_for_start_msg = State()
    waiting_for_topic_name = State()

# Icons
USER_ICON = "👤"
ID_ICON = "🆔"
LINK_ICON = "🔗"
LANG_ICON = "🌐"
NEW_ICON = "🆕"

BANNER_PATH = "bot_settings_attention_banner.png" # You'll need to save the generated image here

# --- HELPERS ---

async def replace_keywords(template: str, user: types.User) -> str:
    res = template or ""
    res = res.replace("#FIRST_NAME", user.first_name or "")
    res = res.replace("#LAST_NAME", user.last_name or "")
    res = res.replace("#USERNAME", f"@{user.username}" if user.username else "")
    res = res.replace("#USER_ID", str(user.id))
    res = res.replace("#MENTION_USER", f'<a href="tg://user?id={user.id}">{user.first_name}</a>')
    return res

async def get_topic_name(user: types.User) -> str:
    template = await db.get_setting("topic_name_temp", config.TOPIC_NAME_TEMPLATE)
    name = await replace_keywords(template, user)
    return name[:127] # TG limit

async def check_setup(message: Message):
    if not config.ADMIN_GROUP_ID or config.ADMIN_GROUP_ID == 0:
        if message.chat.type == "private":
            kb = ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="⚙️ Налаштувати групу", request_chat=KeyboardButtonRequestChat(request_id=1, chat_is_channel=False, chat_is_forum=True, bot_is_member=True, bot_administrator_rights=types.ChatAdministratorRights(can_manage_chat=True, can_manage_topics=True, can_invite_users=True, can_pin_messages=True, is_anonymous=False)))]],
                resize_keyboard=True, one_time_keyboard=True
            )
            await message.answer("👋 **Вітаю! Я фідбек-бот.**\n\nДля роботи потрібно вибрати групу з Topics:", reply_markup=kb)
        return False
    return True

# --- SETTINGS MENU ---

def get_settings_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Start Message / Media", callback_data="set_start_msg")],
        [InlineKeyboardButton(text="👋 Change Topic Name", callback_data="set_topic_name")],
        [InlineKeyboardButton(text="😐 Toggle Anonymous Mode", callback_data="set_anon")],
        [InlineKeyboardButton(text="⚙️ Advanced", callback_data="advanced")],
        [InlineKeyboardButton(text="📊 Statistics", callback_data="stats"), InlineKeyboardButton(text="❌ Delete Bot", callback_data="delete_bot")]
    ])

@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.chat.type != "private": return
    # Basic check - you might want to white-list user IDs
    await message.answer_photo(
        photo=FSInputFile(BANNER_PATH) if os.path.exists(BANNER_PATH) else "https://telegra.ph/file/default.jpg",
        caption="<b>Attention ❗️</b>\n\nYou can customize the appearance of the bot using the buttons below",
        reply_markup=get_settings_kb(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "set_topic_name")
async def cb_topic_name(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_caption(
        caption="Please send a new message (less than 127 characters) to save custom topic name.\n\n"
                "Keywords:\n#FIRST_NAME, #LAST_NAME, #USERNAME, #USER_ID",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Go Back", callback_data="admin_main")]]),
        parse_mode="HTML"
    )
    await state.set_state(SettingsStates.waiting_for_topic_name)

@dp.callback_query(F.data == "admin_main")
async def cb_admin_main(callback: CallbackQuery, state: FSMContext = None):
    if state: await state.clear()
    await callback.message.edit_caption(
        caption="<b>Attention ❗️</b>\n\nYou can customize the appearance of the bot using the buttons below",
        reply_markup=get_settings_kb(),
        parse_mode="HTML"
    )

@dp.message(SettingsStates.waiting_for_topic_name)
async def process_topic_name(message: Message, state: FSMContext):
    await db.set_setting("topic_name_temp", message.text)
    await message.answer(f"✅ Template saved: <code>{message.text}</code>", parse_mode="HTML")
    await state.clear()

@dp.callback_query(F.data == "stats")
async def cb_stats(callback: CallbackQuery):
    total_users = await db.get_total_users()
    total_msgs = await db.get_total_messages()
    
    stats_text = (
        "📊 <b>Bot Statistics</b>\n\n"
        f"👥 Total Users: <code>{total_users}</code>\n"
        f"✉️ Total Messages: <code>{total_msgs}</code>\n\n"
        "<i>Last 24 hours stats could be added here.</i>"
    )
    
    await callback.message.edit_caption(
        caption=stats_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Go Back", callback_data="admin_main")]]),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "advanced")
async def cb_advanced(callback: CallbackQuery):
    await callback.message.edit_caption(
        caption="⚙️ <b>Advanced Settings</b>\n\nCustomize technical aspects of the bot here.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🧹 Clear Cache", callback_data="clear_cache")],
            [InlineKeyboardButton(text="📁 Export Data", callback_data="export_data")],
            [InlineKeyboardButton(text="⬅️ Go Back", callback_data="admin_main")]
        ]),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "set_anon")
async def cb_set_anon(callback: CallbackQuery):
    current = await db.get_setting("anon_mode", "False")
    new_status = "True" if current == "False" else "False"
    await db.set_setting("anon_mode", new_status)
    
    status_text = "enabled ✅" if new_status == "True" else "disabled ❌"
    await callback.answer(f"Anonymous mode {status_text}", show_alert=True)
    
    # Refresh menu
    await callback.message.edit_reply_markup(reply_markup=get_settings_kb())

@dp.callback_query(F.data == "set_start_msg")
async def cb_start_msg(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_caption(
        caption="Please send a new message (less than 1000 characters) to save a custom start message.\n\n"
                "Keywords:\n#FIRST_NAME, #LAST_NAME, #USERNAME, #MENTION_USER, #USER_ID\n\n"
                "HTML tags are supported.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Go Back", callback_data="admin_main")]]),
        parse_mode="HTML"
    )
    await state.set_state(SettingsStates.waiting_for_start_msg)

@dp.message(SettingsStates.waiting_for_start_msg)
async def process_start_msg(message: Message, state: FSMContext):
    await db.set_setting("start_msg", message.text)
    await message.answer(f"✅ Start message saved!", parse_mode="HTML")
    await state.clear()

@dp.callback_query(F.data == "delete_bot")
async def cb_delete_bot(callback: CallbackQuery):
    await callback.message.edit_caption(
        caption="⚠️ <b>Are you sure?</b>\n\nThis will not delete the bot but will clear all settings and conversation mappings from the database.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Yes, Clear Data", callback_data="confirm_delete")],
            [InlineKeyboardButton(text="❌ Cancel", callback_data="admin_main")]
        ]),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "confirm_delete")
async def cb_confirm_delete(callback: CallbackQuery):
    # Logic to clear DB could be here
    await callback.answer("Data cleared (simulated)", show_alert=True)
    await cb_admin_main(callback, None)

# --- MAIN LOGIC ---

@dp.message(CommandStart())
async def cmd_start(message: Message):
    if not await check_setup(message): return
    
    user_id = message.from_user.id
    topic_id = await db.get_topic_by_user(user_id)
    
    raw_start_text = await db.get_setting("start_msg", config.START_MESSAGE)
    start_text = await replace_keywords(raw_start_text, message.from_user)
    
    if not topic_id:
        try:
            name = await get_topic_name(message.from_user)
            forum_topic = await bot.create_forum_topic(chat_id=config.ADMIN_GROUP_ID, name=name)
            topic_id = forum_topic.message_thread_id
            await db.register_user_topic(user_id, topic_id, message.from_user.username, message.from_user.full_name)
            
            # Detailed card
            info = (f"{NEW_ICON} <b>New user!</b>\n\n{ID_ICON} <code>{user_id}</code>\n"
                    f"🤑 @{message.from_user.username}\n{USER_ICON} {message.from_user.full_name}\n"
                    f"{LANG_ICON} Language: {message.from_user.language_code}")
            
            await bot.send_message(config.ADMIN_GROUP_ID, message_thread_id=topic_id, text=info, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Setup error: {e}")
            return

    await message.answer(start_text)

@dp.message(F.chat.type == "private")
async def handle_user_message(message: Message):
    if not await check_setup(message): return
    topic_id = await db.get_topic_by_user(message.from_user.id)
    if not topic_id: return # Or create
    
    sent = await message.copy_to(chat_id=config.ADMIN_GROUP_ID, message_thread_id=topic_id)
    await db.save_message_map(message.message_id, sent.message_id, message.from_user.id)

@dp.message(F.chat.id == config.ADMIN_GROUP_ID, F.is_topic_message)
async def handle_admin_reply(message: Message):
    if message.text and message.text.startswith("/"): return
    user_id = await db.get_user_by_topic(message.message_thread_id)
    if user_id:
        sent = await message.copy_to(chat_id=user_id)
        await db.save_message_map(sent.message_id, message.message_id, user_id)

@dp.message_reaction()
async def handle_reaction(reaction: types.MessageReactionUpdated):
    if reaction.chat.id == config.ADMIN_GROUP_ID:
        u_msg, u_id = await db.get_user_msg_id(reaction.message_id)
        if u_id: await bot.set_message_reaction(u_id, u_msg, reaction.new_reaction)
    else:
        a_msg = await db.get_admin_msg_id(reaction.message_id)
        if a_msg: await bot.set_message_reaction(config.ADMIN_GROUP_ID, a_msg, reaction.new_reaction)

@dp.message(F.chat_shared)
async def handle_chat_shared(message: Message):
    await message.answer(f"✅ Group ID: <code>{message.chat_shared.chat_id}</code>\nUpdate your .env and restart!", parse_mode="HTML")

async def main():
    await db.init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    import os
    asyncio.run(main())
