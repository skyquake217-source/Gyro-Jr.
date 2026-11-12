import random
import re
import time
from datetime import datetime, timezone
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatType
from telegram.ext import ContextTypes
from gyro.config import settings
from gyro.brain import generate_reply

PENDING_MEDIA = {}
LAST_GLOBAL_REPLY = 0.0
LAST_USER_REPLY = {}
RECENT_REPLY_TIMES = []

def is_owner(update):
    return bool(update.effective_user and update.effective_user.id == settings.owner_id)

def main_menu(enabled, level):
    state = "ENCENDER" if not enabled else "APAGAR"
    keyboard = [
        [InlineKeyboardButton(f"⏻ {state}", callback_data="toggle")],
        [InlineKeyboardButton(f"Nivel: {level} · Cambiar", callback_data="level")],
        [InlineKeyboardButton("📦 Ver slots multimedia", callback_data="slots")],
        [InlineKeyboardButton("🔇 Silencio 1 hora", callback_data="mute")],
        [InlineKeyboardButton("ℹ️ Estado", callback_data="status")],
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("soy Gyro Jr. que queres, criatura")

async def panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update) or update.effective_chat.type != ChatType.PRIVATE:
        return
    db = context.application.bot_data["db"]
    enabled = (await db.get_setting("enabled", "true")) == "true"
    level = await db.get_setting("level", "picante")
    await update.message.reply_text(
        f"GYRO CONTROL\nEstado: {'encendido' if enabled else 'apagado'}\nNivel: {level}\n\n"
        "Para cargar multimedia:\n/setsticker 1 y responde a ese mensaje con un sticker.\n"
        "/setsong 1 y responde con un audio o archivo de musica.",
        reply_markup=main_menu(enabled, level)
    )

async def panel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    if query.from_user.id != settings.owner_id or query.message.chat.type != ChatType.PRIVATE:
        await query.answer("este panel no es tuyo", show_alert=True)
        return
    db = context.application.bot_data["db"]
    await query.answer()
    if query.data == "toggle":
        current = (await db.get_setting("enabled", "true")) == "true"
        await db.set_setting("enabled", "false" if current else "true")
    elif query.data == "level":
        current = await db.get_setting("level", "picante")
        levels = ["suave", "medio", "picante"]
        await db.set_setting("level", levels[(levels.index(current) + 1) % len(levels)])
    elif query.data == "mute":
        await db.set_setting("mute_until", str(time.time() + 3600))
    elif query.data == "slots":
        stickers = await db.get_slots("sticker")
        songs = await db.get_slots("song")
        s = ", ".join(str(x["slot"]) for x in stickers) or "ninguno"
        m = ", ".join(str(x["slot"]) for x in songs) or "ninguno"
        await query.message.reply_text(f"Stickers cargados: {s}\nCanciones cargadas: {m}")
    enabled = (await db.get_setting("enabled", "true")) == "true"
    level = await db.get_setting("level", "picante")
    await query.edit_message_reply_markup(reply_markup=main_menu(enabled, level))

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update) or update.effective_chat.type != ChatType.PRIVATE:
        return
    db = context.application.bot_data["db"]
    enabled = await db.get_setting("enabled", "true")
    level = await db.get_setting("level", "picante")
    await update.message.reply_text(f"Gyro: {enabled}\nNivel: {level}\nGrupo autorizado: {settings.group_id}")

async def group_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_owner(update):
        await update.message.reply_text(f"ID de este chat: {update.effective_chat.id}")

async def set_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update) or update.effective_chat.type != ChatType.PRIVATE:
        return
    if not context.args or not context.args[0].isdigit() or not 1 <= int(context.args[0]) <= 10:
        await update.message.reply_text("uso: /setsticker 1 (despues responde a este mensaje con el sticker)")
        return
    PENDING_MEDIA[settings.owner_id] = ("sticker", int(context.args[0]))
    await update.message.reply_text(f"listo, ahora responde a este mensaje con el sticker para el slot {context.args[0]}")

async def set_song(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update) or update.effective_chat.type != ChatType.PRIVATE:
        return
    if not context.args or not context.args[0].isdigit() or not 1 <= int(context.args[0]) <= 10:
        await update.message.reply_text("uso: /setsong 1 (despues responde a este mensaje con un audio)")
        return
    PENDING_MEDIA[settings.owner_id] = ("song", int(context.args[0]))
    await update.message.reply_text(f"listo, ahora responde a este mensaje con el audio para el slot {context.args[0]}")

async def handle_private_media(update, context):
    if not is_owner(update):
        return
    pending = PENDING_MEDIA.get(settings.owner_id)
    if not pending:
        return
    kind, slot = pending
    msg = update.message
    file_id = None
    if kind == "sticker" and msg.sticker:
        file_id = msg.sticker.file_id
    elif kind == "song" and (msg.audio or msg.document or msg.voice):
        media = msg.audio or msg.document or msg.voice
        file_id = media.file_id
    if file_id:
        db = context.application.bot_data["db"]
        await db.save_slot(kind, slot, file_id, f"slot {slot}")
        PENDING_MEDIA.pop(settings.owner_id, None)
        await msg.reply_text(f"guardado. {kind} slot {slot} listo.")
    else:
        await msg.reply_text("ese formato no me sirve para ese slot")

async def maybe_send_media(db, update, context, answer):
    # Low-frequency, contextual media use; never send more than one item.
    if random.random() > 0.025:
        return
    kind = "sticker" if random.random() < 0.75 else "song"
    slots = await db.get_slots(kind)
    if not slots:
        return
    chosen = random.choice(slots)
    try:
        if kind == "sticker":
            await context.bot.send_sticker(update.effective_chat.id, chosen["file_id"])
        else:
            await context.bot.send_audio(update.effective_chat.id, chosen["file_id"])
    except Exception:
        pass

async def on_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global LAST_GLOBAL_REPLY
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if not msg or not user or user.is_bot:
        return

    # Private owner media uploads are handled separately.
    if chat.type == ChatType.PRIVATE:
        await handle_private_media(update, context)
        return

    if chat.id != settings.group_id:
        return
    if msg.new_chat_members:
        for newcomer in msg.new_chat_members:
            if newcomer.is_bot:
                continue
            welcomes = [
                "bienvenido al circo, deja el sentido comun en la entrada",
                "epa, se sumo otro especialista en complicarla",
                "bienvenido, aca se viene a aportar o a decorar el chat",
                "uno mas para el grupo, la economia no levanta pero nosotros tampoco",
            ]
            await msg.reply_text(random.choice(welcomes))
        return

    if user.id == settings.owner_id:
        pass

    db = context.application.bot_data["db"]
    await db.save_user(user.id, user.username, user.full_name)
    await db.add_message(user.id, user.username, user.full_name, "user", msg.text or msg.caption or "[multimedia]")

    if (await db.get_setting("enabled", "true")) != "true":
        return
    mute_until = float(await db.get_setting("mute_until", "0") or "0")
    if time.time() < mute_until:
        return

    text = (msg.text or msg.caption or "").strip()
    if not text:
        return

    bot_username = context.bot.username or ""
    tagged = bot_username and f"@{bot_username.lower()}" in text.lower()
    says_gyro = re.search(r"\bgyro\b", text, re.IGNORECASE) is not None
    direct = bool(msg.reply_to_message and msg.reply_to_message.from_user and msg.reply_to_message.from_user.id == context.bot.id)
    explicit = tagged or says_gyro or direct

    # Social pacing: global, per-user, and hourly caps.
    now = time.time()
    global LAST_USER_REPLY, RECENT_REPLY_TIMES
    RECENT_REPLY_TIMES = [t for t in RECENT_REPLY_TIMES if now - t < 3600]
    if now - LAST_GLOBAL_REPLY < settings.global_cooldown_seconds:
        return
    if now - LAST_USER_REPLY.get(user.id, 0) < settings.user_cooldown_seconds:
        return
    if len(RECENT_REPLY_TIMES) >= settings.max_replies_per_hour:
        return

    spontaneous = random.random() < settings.spontaneous_probability
    if not explicit and not spontaneous:
        return

    # Do not dogpile on one participant: lower spontaneous odds for recent target.
    if not explicit and random.random() < 0.65:
        return

    answer = await generate_reply(db, user, text)
    if not answer:
        return
    await msg.reply_text(answer)
    await db.add_message(user.id, user.username, user.full_name, "assistant", answer)
    LAST_GLOBAL_REPLY = now
    LAST_USER_REPLY[user.id] = now
    RECENT_REPLY_TIMES.append(now)
    await maybe_send_media(db, update, context, answer)
