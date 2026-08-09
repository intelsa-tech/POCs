"""
Claude-powered Telegram bot (OpenClaw-style).

Features:
- Multi-turn conversations with per-user history
- Claude claude-opus-4-6 with adaptive thinking
- Image understanding
- /new to reset conversation
- Optional user whitelist
"""

import os
import logging
import base64
from io import BytesIO

from dotenv import load_dotenv
from telegram import Update, constants
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
import anthropic

load_dotenv()

# ── Configuration ────────────────────────────────────────────────────────────

TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
SYSTEM_PROMPT = os.getenv(
    "SYSTEM_PROMPT",
    "You are a helpful AI assistant powered by Claude. Be concise, clear, and friendly.",
)
MAX_HISTORY_TURNS = int(os.getenv("MAX_HISTORY_TURNS", "20"))

_raw_ids = os.getenv("ALLOWED_USER_IDS", "").strip()
ALLOWED_USER_IDS: set[int] = (
    {int(uid) for uid in _raw_ids.split(",") if uid.strip()} if _raw_ids else set()
)

MODEL = "claude-opus-4-6"
MAX_TOKENS = 4096

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Claude client ─────────────────────────────────────────────────────────────

claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# ── Per-user conversation history ─────────────────────────────────────────────
# { user_id: [ {"role": "user"|"assistant", "content": ...}, ... ] }
conversations: dict[int, list[dict]] = {}


def get_history(user_id: int) -> list[dict]:
    return conversations.setdefault(user_id, [])


def trim_history(user_id: int) -> None:
    """Keep at most MAX_HISTORY_TURNS message pairs."""
    history = conversations.get(user_id, [])
    max_messages = MAX_HISTORY_TURNS * 2  # each "turn" = user + assistant
    if len(history) > max_messages:
        conversations[user_id] = history[-max_messages:]


# ── Auth helper ───────────────────────────────────────────────────────────────

def is_allowed(user_id: int) -> bool:
    return not ALLOWED_USER_IDS or user_id in ALLOWED_USER_IDS


# ── Claude call ───────────────────────────────────────────────────────────────

def ask_claude(history: list[dict]) -> str:
    """Send the full conversation history to Claude and return its reply."""
    response = claude.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        thinking={"type": "adaptive"},
        system=SYSTEM_PROMPT,
        messages=history,
    )
    # Extract the text block (thinking blocks come first with adaptive thinking)
    for block in response.content:
        if block.type == "text":
            return block.text
    return "(No response)"


# ── Telegram handlers ─────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not is_allowed(user.id):
        await update.message.reply_text("⛔ No tienes acceso a este bot.")
        return

    await update.message.reply_text(
        f"👋 Hola, {user.first_name}!\n\n"
        "Soy tu asistente de IA powered by **Claude**.\n\n"
        "Escríbeme cualquier cosa, envíame imágenes, o usa:\n"
        "• /new — iniciar una conversación nueva\n"
        "• /help — ver esta ayuda",
        parse_mode=constants.ParseMode.MARKDOWN,
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "*Comandos disponibles:*\n"
        "/start — Bienvenida\n"
        "/new — Borrar historial e iniciar conversación nueva\n"
        "/help — Esta ayuda\n\n"
        "*Capacidades:*\n"
        "• Conversación multi-turno con memoria\n"
        "• Análisis de imágenes\n"
        "• Respuestas largas y detalladas\n"
        "• Razonamiento avanzado (adaptive thinking)",
        parse_mode=constants.ParseMode.MARKDOWN,
    )


async def cmd_new(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not is_allowed(user.id):
        await update.message.reply_text("⛔ No tienes acceso a este bot.")
        return

    conversations.pop(user.id, None)
    await update.message.reply_text("🔄 Conversación reiniciada. ¿En qué puedo ayudarte?")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not is_allowed(user.id):
        await update.message.reply_text("⛔ No tienes acceso a este bot.")
        return

    user_text = update.message.text.strip()
    if not user_text:
        return

    history = get_history(user.id)
    history.append({"role": "user", "content": user_text})

    # Show typing indicator
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action=constants.ChatAction.TYPING,
    )

    try:
        reply = ask_claude(history)
    except anthropic.APIError as exc:
        logger.error("Claude API error: %s", exc)
        history.pop()  # Roll back the user message
        await update.message.reply_text(f"❌ Error al contactar a Claude: {exc}")
        return

    history.append({"role": "assistant", "content": reply})
    trim_history(user.id)

    # Telegram messages are capped at 4096 chars; split if needed
    for chunk in _split_message(reply):
        await update.message.reply_text(chunk, parse_mode=constants.ParseMode.MARKDOWN)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not is_allowed(user.id):
        await update.message.reply_text("⛔ No tienes acceso a este bot.")
        return

    # Grab highest-resolution photo
    photo = update.message.photo[-1]
    caption = update.message.caption or "¿Qué ves en esta imagen?"

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action=constants.ChatAction.TYPING,
    )

    # Download image
    photo_file = await photo.get_file()
    buf = BytesIO()
    await photo_file.download_to_memory(buf)
    image_b64 = base64.standard_b64encode(buf.getvalue()).decode()

    # Build multi-modal message
    user_content = [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": image_b64,
            },
        },
        {"type": "text", "text": caption},
    ]

    history = get_history(user.id)
    history.append({"role": "user", "content": user_content})

    try:
        reply = ask_claude(history)
    except anthropic.APIError as exc:
        logger.error("Claude API error: %s", exc)
        history.pop()
        await update.message.reply_text(f"❌ Error al contactar a Claude: {exc}")
        return

    history.append({"role": "assistant", "content": reply})
    trim_history(user.id)

    for chunk in _split_message(reply):
        await update.message.reply_text(chunk, parse_mode=constants.ParseMode.MARKDOWN)


# ── Utilities ─────────────────────────────────────────────────────────────────

def _split_message(text: str, limit: int = 4000) -> list[str]:
    """Split text into Telegram-safe chunks."""
    if len(text) <= limit:
        return [text]
    chunks = []
    while text:
        chunks.append(text[:limit])
        text = text[limit:]
    return chunks


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("new", cmd_new))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    logger.info("Bot iniciado. Modelo: %s", MODEL)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
