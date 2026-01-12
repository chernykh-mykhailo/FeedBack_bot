import asyncio
import logging
import sys
from typing import Optional

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, KeyboardButtonRequestChat, ReplyKeyboardMarkup, KeyboardButton, ChatShared
from aiogram.exceptions import TelegramBadRequest

from config import config
import database as db

# Logging setup
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher()

# Icons
USER_ICON = "👤"
ID_ICON = "🆔"
LINK_ICON = "🔗"
LANG_ICON = "🌐"
NEW_ICON = "🆕"

# --- HELPERS ---

async def check_setup(message: Message):
    if not config.ADMIN_GROUP_ID or config.ADMIN_GROUP_ID == 0:
        if message.chat.type == "private":
            # Modern request_chat button
            kb = ReplyKeyboardMarkup(
                keyboard=[
                    [
                        KeyboardButton(
                            text="⚙️ Налаштувати групу",
                            request_chat=KeyboardButtonRequestChat(
                                request_id=1,
                                chat_is_channel=False,
                                chat_is_forum=True, # Require topics
                                bot_is_member=True,
                                bot_administrator_rights=types.ChatAdministratorRights(
                                    can_manage_chat=True,
                                    can_manage_topics=True,
                                    can_invite_users=True,
                                    can_pin_messages=True,
                                    is_anonymous=False
                                )
                            )
                        )
                    ]
                ],
                resize_keyboard=True,
                one_time_keyboard=True
            )
            await message.answer(
                "👋 **Вітаю! Я фідбек-бот.**\n\n"
                "Для моєї роботи потрібно створити групу з увімкненими темами (Forum) "
                "та додати мене туди як адміністратора.\n\n"
                "Натисніть кнопку нижче, щоб вибрати або створити таку групу:",
                reply_markup=kb
            )
        return False
    return True

# --- SETUP HANDLERS ---

@dp.message(F.chat_shared)
async def handle_chat_shared(message: Message):
    chat_id = message.chat_shared.chat_id
    await message.answer(
        f"✅ **Групу вибрано!**\n\n"
        f"Тепер зробіть останній крок:\n\n"
        f"1. Відкрийте файл <code>.env</code>\n"
        f"2. Замініть <code>ADMIN_GROUP_ID={config.ADMIN_GROUP_ID}</code> на <code>ADMIN_GROUP_ID={chat_id}</code>\n"
        f"3. Перезапустіть бота.\n\n"
        f"Після цього я буду готовий приймати повідомлення!"
    )

@dp.message(Command("setup"))
async def cmd_setup(message: Message):
    await check_setup(message)

# --- USER HANDLERS ---

@dp.message(CommandStart())
async def cmd_start(message: Message):
    if not await check_setup(message): return
    
    user_id = message.from_user.id
    full_name = message.from_user.full_name
    username = f"@{message.from_user.username}" if message.from_user.username else "<i>немає</i>"
    lang = message.from_user.language_code or "uk"
    
    topic_id = await db.get_topic_by_user(user_id)
    
    start_info = (
        f"{NEW_ICON} <b>Новий користувач запустив бота!</b>\n\n"
        f"{ID_ICON} <code>{user_id}</code>\n"
        f"🤑 {username}\n"
        f"{USER_ICON} {full_name}\n"
        f"{LANG_ICON} Language: <code>{lang}</code>\n"
        f"📝 <i>Очікує на відповідь...</i>"
    )
    
    if not topic_id:
        try:
            forum_topic = await bot.create_forum_topic(
                chat_id=config.ADMIN_GROUP_ID,
                name=f"{full_name} ({user_id})"
            )
            topic_id = forum_topic.message_thread_id
            await db.register_user_topic(user_id, topic_id, username, full_name)
            
            photos = await message.from_user.get_profile_photos(limit=1)
            if photos.total_count > 0:
                await bot.send_photo(
                    chat_id=config.ADMIN_GROUP_ID,
                    message_thread_id=topic_id,
                    photo=photos.photos[0][-1].file_id,
                    caption=start_info,
                    parse_mode="HTML"
                )
            else:
                await bot.send_message(
                    chat_id=config.ADMIN_GROUP_ID,
                    message_thread_id=topic_id,
                    text=start_info,
                    parse_mode="HTML"
                )
        except Exception as e:
            logger.error(f"Failed to create topic: {e}")
            await message.answer("⚠️ Помилка створення чату. Перевірте права бота в групі.")
            return
    else:
        await bot.send_message(
            chat_id=config.ADMIN_GROUP_ID,
            message_thread_id=topic_id,
            text=f"🔄 Користувач знову прописав /start",
            parse_mode="HTML"
        )

    await message.answer("Привіт! Напиши своє питання або відгук. 😊")

@dp.message(F.chat.type == "private")
async def handle_user_message(message: Message):
    if not await check_setup(message): return
    
    temp_msg = await message.answer("⏳ <i>Відправляю ваше повідомлення...</i>", parse_mode="HTML")
    
    user_id = message.from_user.id
    topic_id = await db.get_topic_by_user(user_id)
    
    if not topic_id:
        try:
            forum_topic = await bot.create_forum_topic(chat_id=config.ADMIN_GROUP_ID, name=f"{message.from_user.full_name} ({user_id})")
            topic_id = forum_topic.message_thread_id
            await db.register_user_topic(user_id, topic_id, message.from_user.username, message.from_user.full_name)
        except Exception:
            await temp_msg.edit_text("❌ Помилка ініціалізації чату.")
            return

    try:
        sent_msg = await message.copy_to(chat_id=config.ADMIN_GROUP_ID, message_thread_id=topic_id)
        await db.save_message_map(message.message_id, sent_msg.message_id, user_id)
        await temp_msg.delete()
    except Exception as e:
        logger.error(f"Error forwarding: {e}")
        await temp_msg.edit_text("❌ Помилка при відправці.")

# --- ADMIN HANDLERS ---

@dp.message(F.chat.id == config.ADMIN_GROUP_ID, F.is_topic_message)
async def handle_admin_reply(message: Message):
    if message.text and message.text.startswith("/"): return
    user_id = await db.get_user_by_topic(message.message_thread_id)
    if user_id:
        try:
            sent_msg = await message.copy_to(chat_id=user_id)
            await db.save_message_map(sent_msg.message_id, message.message_id, user_id)
        except Exception:
            await message.reply("⚠️ Користувач заблокував бота.")

# --- REACTIONS ---

@dp.message_reaction()
async def handle_reaction(reaction: types.MessageReactionUpdated):
    if reaction.chat.id == config.ADMIN_GROUP_ID:
        user_msg_id, user_id = await db.get_user_msg_id(reaction.message_id)
        if user_msg_id and user_id:
            try:
                await bot.set_message_reaction(chat_id=user_id, message_id=user_msg_id, reaction=reaction.new_reaction)
            except Exception: pass
    else:
        admin_id = await db.get_admin_msg_id(reaction.message_id)
        if admin_id:
            try:
                await bot.set_message_reaction(chat_id=config.ADMIN_GROUP_ID, message_id=admin_id, reaction=reaction.new_reaction)
            except Exception: pass

async def main():
    await db.init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
