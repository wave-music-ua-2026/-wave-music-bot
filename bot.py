import os
from urllib.parse import quote_plus

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = os.environ["BOT_TOKEN"]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎵 WAVE | Твоя музика 🇺🇦\n\n"
        "🔎 Напиши назву пісні — я допоможу знайти її.\n\n"
        "🎧 Або надішли MP3/M4A файл — "
        "його можна буде слухати прямо в Telegram."
    )


async def search_music(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.message.text.strip()

    if not query:
        return

    encoded = quote_plus(query)

    youtube = (
        "https://www.youtube.com/results?"
        f"search_query={encoded}"
    )

    spotify = (
        "https://open.spotify.com/search/"
        f"{encoded}"
    )

    soundcloud = (
        "https://soundcloud.com/search?"
        f"q={encoded}"
    )

    keyboard = [
        [
            InlineKeyboardButton(
                "▶️ YouTube",
                url=youtube
            )
        ],
        [
            InlineKeyboardButton(
                "🟢 Spotify",
                url=spotify
            )
        ],
        [
            InlineKeyboardButton(
                "☁️ SoundCloud",
                url=soundcloud
            )
        ],
    ]

    await update.message.reply_text(
        f"🎧 Знайшов варіанти для:\n\n"
        f"🔎 {query}\n\n"
        "Обери сервіс 👇",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def receive_audio(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    audio = update.message.audio

    if not audio:
        return

    await update.message.reply_audio(
        audio=audio.file_id,
        title=audio.title or audio.file_name or "WAVE Track",
        performer=audio.performer or "WAVE",
        caption="🎧 Готово — слухай прямо в Telegram ▶️",
    )


async def receive_document(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    document = update.message.document

    if not document:
        return

    mime = document.mime_type or ""

    allowed = (
        mime.startswith("audio/")
        or (document.file_name or "").lower().endswith(
            (".mp3", ".m4a", ".aac", ".ogg", ".wav")
        )
    )

    if not allowed:
        await update.message.reply_text(
            "⚠️ Надішли аудіофайл MP3, M4A, AAC, OGG або WAV."
        )
        return

    await update.message.reply_audio(
        audio=document.file_id,
        title=document.file_name or "WAVE Track",
        caption="🎧 Тепер файл можна слухати прямо в Telegram ▶️",
    )


def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        MessageHandler(
            filters.AUDIO,
            receive_audio
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Document.ALL,
            receive_document
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            search_music
        )
    )

    print("WAVE bot started")

    app.run_polling()


if __name__ == "__main__":
    main()
