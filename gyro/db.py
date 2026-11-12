import asyncpg
import json
from datetime import datetime, timezone

class Database:
    def __init__(self, url):
        self.url = url
        self.pool = None

    async def connect(self):
        self.pool = await asyncpg.create_pool(self.url, min_size=1, max_size=5)
        async with self.pool.acquire() as c:
            await c.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY, value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS memories (
                user_id BIGINT NOT NULL, username TEXT, display_name TEXT,
                memory JSONB NOT NULL DEFAULT '{}'::jsonb,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY(user_id)
            );
            CREATE TABLE IF NOT EXISTS chat_history (
                id BIGSERIAL PRIMARY KEY, user_id BIGINT NOT NULL,
                username TEXT, display_name TEXT, role TEXT NOT NULL,
                content TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS media_slots (
                kind TEXT NOT NULL, slot INTEGER NOT NULL, file_id TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '', PRIMARY KEY(kind, slot)
            );
            CREATE TABLE IF NOT EXISTS runtime (
                key TEXT PRIMARY KEY, value TEXT NOT NULL
            );
            """)

    async def close(self):
        if self.pool:
            await self.pool.close()

    async def get_setting(self, key, default=None):
        async with self.pool.acquire() as c:
            row = await c.fetchrow("SELECT value FROM settings WHERE key=$1", key)
            return row["value"] if row else default

    async def set_setting(self, key, value):
        async with self.pool.acquire() as c:
            await c.execute("""
                INSERT INTO settings(key,value) VALUES($1,$2)
                ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value
            """, key, str(value))

    async def add_message(self, user_id, username, display_name, role, content):
        async with self.pool.acquire() as c:
            await c.execute("""
                INSERT INTO chat_history(user_id,username,display_name,role,content)
                VALUES($1,$2,$3,$4,$5)
            """, user_id, username, display_name, role, content[:3000])
            # Retain a bounded recent context; durable user notes are separate.
            await c.execute("""
                DELETE FROM chat_history
                WHERE created_at < NOW() - INTERVAL '14 days'
            """)

    async def recent_history(self, limit=18):
        async with self.pool.acquire() as c:
            rows = await c.fetch("""
                SELECT username,display_name,role,content
                FROM chat_history ORDER BY id DESC LIMIT $1
            """, limit)
            return list(reversed(rows))

    async def user_memory(self, user_id):
        async with self.pool.acquire() as c:
            row = await c.fetchrow("SELECT memory FROM memories WHERE user_id=$1", user_id)
            return row["memory"] if row else {}

    async def save_user(self, user_id, username, display_name):
        async with self.pool.acquire() as c:
            await c.execute("""
                INSERT INTO memories(user_id,username,display_name)
                VALUES($1,$2,$3)
                ON CONFLICT(user_id) DO UPDATE SET
                username=EXCLUDED.username, display_name=EXCLUDED.display_name,
                updated_at=NOW()
            """, user_id, username, display_name)

    async def save_slot(self, kind, slot, file_id, description):
        async with self.pool.acquire() as c:
            await c.execute("""
                INSERT INTO media_slots(kind,slot,file_id,description)
                VALUES($1,$2,$3,$4)
                ON CONFLICT(kind,slot) DO UPDATE SET
                file_id=EXCLUDED.file_id, description=EXCLUDED.description
            """, kind, slot, file_id, description)

    async def get_slots(self, kind):
        async with self.pool.acquire() as c:
            return await c.fetch("SELECT slot,file_id,description FROM media_slots WHERE kind=$1 ORDER BY slot", kind)

    async def get_runtime(self, key, default=None):
        async with self.pool.acquire() as c:
            row = await c.fetchrow("SELECT value FROM runtime WHERE key=$1", key)
            return row["value"] if row else default

    async def set_runtime(self, key, value):
        async with self.pool.acquire() as c:
            await c.execute("""
                INSERT INTO runtime(key,value) VALUES($1,$2)
                ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value
            """, key, str(value))
