import aiosqlite
import os
from typing import Any

DB_PATH = "feedback_bot.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                topic_id INTEGER UNIQUE,
                username TEXT,
                full_name TEXT,
                last_ack_id INTEGER
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                user_msg_id INTEGER,
                admin_msg_id INTEGER,
                chat_id INTEGER,
                PRIMARY KEY (user_msg_id, admin_msg_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        # Migration: Add last_ack_id to users if not exists
        try:
            await db.execute("ALTER TABLE users ADD COLUMN last_ack_id INTEGER")
        except Exception:
            pass # Column already exists
        await db.commit()

async def get_setting(key: str, default: Any = None):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM settings WHERE key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else default

async def set_setting(key: str, value: Any):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
        await db.commit()

async def save_message_map(user_msg_id: int, admin_msg_id: int, chat_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO messages (user_msg_id, admin_msg_id, chat_id) VALUES (?, ?, ?)",
            (user_msg_id, admin_msg_id, chat_id)
        )
        await db.commit()

async def get_admin_msg_id(user_msg_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT admin_msg_id FROM messages WHERE user_msg_id = ?", (user_msg_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

async def get_user_msg_id(admin_msg_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_msg_id, chat_id FROM messages WHERE admin_msg_id = ?", (admin_msg_id,)) as cursor:
            row = await cursor.fetchone()
            return row if row else (None, None)

async def get_topic_by_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT topic_id FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

async def get_user_by_topic(topic_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users WHERE topic_id = ?", (topic_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

async def register_user_topic(user_id: int, topic_id: int, username: str = None, full_name: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO users (user_id, topic_id, username, full_name) VALUES (?, ?, ?, ?)",
            (user_id, topic_id, username, full_name)
        )
        await db.commit()

async def get_total_users():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

async def get_total_messages():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM messages") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

async def set_user_ack(user_id: int, msg_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET last_ack_id = ? WHERE user_id = ?", (msg_id, user_id))
        await db.commit()

async def get_and_clear_user_ack(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT last_ack_id FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            ack_id = row[0] if row else None
            
        if ack_id:
            await db.execute("UPDATE users SET last_ack_id = NULL WHERE user_id = ?", (user_id,))
            await db.commit()
        return ack_id
