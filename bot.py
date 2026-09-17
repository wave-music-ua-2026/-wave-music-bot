import os
import asyncio
import yt_dlp

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
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
        "🔎 Напиши назву пісні — я знайду її.\n\n"
        "🎧 Також можеш надіслати свій MP3/M4A — "
        "його можна слухати прямо в Telegram."
    )


def find_track(query):
    options = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": True,
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        result = ydl.extract_info(
            f"ytsearch1:{query}",
            download=False,
        )

    entries = result.get("entries", [])

    if not entries:
        return None

    track = entries[0]

    video_id = track.get("id")

    if not video_id:
        return None

    return {
        "title": track.get("title") or query,
        "artist": (
            track.get("channel")
            or track.get("uploader")
            or "Невідомий виконавець"
        ),
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "thumbnail": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
    }


async def search_music(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.message.text.strip()

    if not query:
        return

    status = await update.message.reply_text(
        "🔎 Шукаю трек..."
    )

    try:
        track = await asyncio.to_thread(
            find_track,
            query,
        )

        await status.delete()

        if not track:
            await update.message.reply_text(
                "😕 Нічого не знайшов.\n"
                "Спробуй написати назву та виконавця."
            )
            return

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "▶️ Відкрити на YouTube",
                        url=track["url"],
                    )
                ]
            ]
        )

        caption = (
            f"🎵 {track['title']}\n"
            f"👤 {track['artist']}\n\n"
            "▶️ Відкрити оригінал:"
        )

        try:
            await update.message.reply_photo(
                photo=track["thumbnail"],
                caption=caption,
                reply_markup=keyboard,
            )

        except Exception:
            await update.message.reply_text(
                caption,
                reply_markup=keyboard,
            )

    except Exception as error:
        print("SEARCH ERROR:", error)

        try:
            await status.delete()
        except Exception:
            pass

        await update.message.reply_text(
            "⚠️ Не вдалося знайти трек.\n"
            "Спробуй ще раз трохи пізніше."
        )


async def receive_audio(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    audio = update.message.audio

    if not audio:
        return

    await update.message.reply_audio(
        audio=audio.file_id,
        title=audio.title or audio.file_name or "WAVE Track",
        performer=audio.performer or "WAVE",
        caption="🎧 Слухай прямо в Telegram ▶️",
    )


async def receive_document(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    document = update.message.document

    if not document:
        return

    filename = (document.file_name or "").lower()

    allowed = filename.endswith(
        (
            ".mp3",
            ".m4a",
            ".aac",
            ".ogg",
            ".wav",
        )
    )

    if not allowed:
        await update.message.reply_text(
            "⚠️ Надішли MP3, M4A, AAC, OGG або WAV."
        )
        return

    await update.message.reply_audio(
        audio=document.file_id,
        title=document.file_name or "WAVE Track",
        caption="🎧 Слухай прямо в Telegram ▶️",
    )


def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.AUDIO,
            receive_audio,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Document.ALL,
            receive_document,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            search_music,
        )
    )

    print("WAVE bot started")

    app.run_polling()


if __name__ == "__main__":
    main()
