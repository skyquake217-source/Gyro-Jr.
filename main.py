import asyncio
import logging
import os
from telegram.ext import Application, MessageHandler, CommandHandler, CallbackQueryHandler, filters
from gyro.config import settings
from gyro.db import Database
from gyro.handlers import (
    on_group_message, start, panel, panel_callback, set_sticker,
    set_song, status, group_id
)

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
log = logging.getLogger("gyro")

async def post_init(app: Application):
    app.bot_data["db"] = Database(settings.database_url)
    await app.bot_data["db"].connect()
    log.info("GYRO JR iniciado. Grupo autorizado: %s", settings.group_id)

async def post_shutdown(app: Application):
    db = app.bot_data.get("db")
    if db:
        await db.close()

def main():
    if not settings.telegram_token:
        raise RuntimeError("Falta TELEGRAM_TOKEN en las variables de entorno.")
    if not settings.groq_api_key:
        raise RuntimeError("Falta GROQ_API_KEY en las variables de entorno.")
    if not settings.database_url:
        raise RuntimeError("Falta DATABASE_URL. Usa PostgreSQL de Render.")
    if not settings.group_id:
        raise RuntimeError("Falta GROUP_ID: el ID numerico del grupo.")

    app = (
        Application.builder()
        .token(settings.telegram_token)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("panel", panel))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("id", group_id))
    app.add_handler(CommandHandler("setsticker", set_sticker))
    app.add_handler(CommandHandler("setsong", set_song))
    app.add_handler(CallbackQueryHandler(panel_callback))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, on_group_message), group=10)

    log.info("Arrancando polling...")
    app.run_polling(allowed_updates=["message", "callback_query", "my_chat_member"])

if __name__ == "__main__":
    main()
