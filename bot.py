import os
import asyncio
import yt_dlp

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
        "🔎 Напиши назву пісні або виконавця — "
        "я знайду варіанти на YouTube.\n\n"
        "🎧 Або надішли свій MP3/M4A файл — "
        "його можна буде слухати прямо в Telegram."
    )


def youtube_search(query: str):
    options = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "skip_download": True,
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        data = ydl.extract_info(
            f"ytsearch5:{query}",
            download=False,
        )

    return data.get("entries", [])


async def search_music(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.message.text.strip()

    if not query:
        return

    loading = await update.message.reply_text(
        "🔎 Шукаю музику..."
    )

    try:
        results = await asyncio.to_thread(
            youtube_search,
            query,
        )

        await loading.delete()

        if not results:
            await update.message.reply_text(
                "😕 Нічого не знайшов."
            )
            return

        await update.message.reply_text(
            f"🎧 Результати для:\n\n"
            f"🔎 {query}\n\n"
            f"Знайшов {len(results)} варіантів 👇"
        )

        for number, item in enumerate(results, start=1):
            video_id = item.get("id")

            if not video_id:
                continue

            title = item.get("title") or "Без назви"
            artist = (
                item.get("channel")
                or item.get("uploader")
                or "Невідомий виконавець"
            )

            youtube_url = (
                f"https://www.youtube.com/watch?v={video_id}"
            )

            thumbnail = (
                f"https://i.ytimg.com/vi/"
                f"{video_id}/hqdefault.jpg"
            )

            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "▶️ Відкрити на YouTube",
                            url=youtube_url,
                        )
                    ]
                ]
            )

            caption = (
                f"🎵 {number}. {title}\n"
                f"👤 {artist}"
            )

            try:
                await update.message.reply_photo(
                    photo=thumbnail,
                    caption=caption,
                    reply_markup=keyboard,
                )
            except Exception:
                await update.message.reply_text(
                    caption,
                    reply_markup=keyboard,
                )

    except Exception as error:
        try:
            await loading.delete()
        except Exception:
            pass

        print("SEARCH ERROR:", error)

        await update.message.reply_text(
            "⚠️ Не вдалося виконати пошук.\n"
            "Спробуй ще раз."
        )


async def receive_audio(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.message

    if message.audio:
        audio = message.audio

        await message.reply_audio(
            audio=audio.file_id,
            title=audio.title or "WAVE Track",
            performer=audio.performer or "WAVE",
            caption="🎧 Слухай прямо в Telegram ▶️",
        )

        return

    document = message.document

    if not document:
        return

    mime = document.mime_type or ""

    allowed = (
        mime.startswith("audio/")
        or document.file_name.lower().endswith(
            (".mp3", ".m4a", ".aac", ".ogg", ".wav")
        )
    )

    if not allowed:
        return

    await message.reply_audio(
        audio=document.file_id,
        title=document.file_name or "WAVE Track",
        performer="WAVE",
        caption="🎧 Слухай прямо в Telegram ▶️",
    )


def main():
    app = (
        Application.builder()
        .token(TOKEN)
        .build()
    )

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
            filters.Document.AUDIO,
            receive_audio,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            search_music,
        )
    )

    print("🎵 WAVE bot started")

    app.run_polling()


if __name__ == "__main__":
    main()
