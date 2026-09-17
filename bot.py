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
        "Напиши назву пісні або виконавця — "
        "я знайду трек для тебе 🔎\n\n"
        "Наприклад:\n"
        "🎤 The Weeknd Blinding Lights"
    )


def find_youtube_track(query: str):
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(
            f"ytsearch1:{query}",
            download=False
        )

    entries = info.get("entries") or []

    if not entries:
        return None

    video = entries[0]

    video_id = video.get("id")
    if not video_id:
        return None

    return {
        "title": video.get("title") or query,
        "channel": (
            video.get("channel")
            or video.get("uploader")
            or "YouTube"
        ),
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "thumbnail": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
    }


async def search_music(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.message.text.strip()

    if not query:
        return

    status = await update.message.reply_text(
        f"🔎 Шукаю: {query}..."
    )

    try:
        track = await asyncio.to_thread(
            find_youtube_track,
            query
        )

        if not track:
            await status.edit_text(
                "😕 Нічого не знайшов. Спробуй іншу назву."
            )
            return

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "▶️ Відкрити на YouTube",
                    url=track["url"]
                )
            ]
        ])

        caption = (
            f"🎵 {track['title']}\n"
            f"👤 {track['channel']}\n\n"
            "👇 Натисни, щоб відкрити трек"
        )

        try:
            await update.message.reply_photo(
                photo=track["thumbnail"],
                caption=caption,
                reply_markup=keyboard
            )
        except Exception:
            # Якщо Telegram не зможе завантажити обкладинку,
            # результат все одно буде показаний.
            await update.message.reply_text(
                caption,
                reply_markup=keyboard
            )

        await status.delete()

    except Exception as error:
        print(f"Search error: {error}")

        await status.edit_text(
            "⚠️ Не вдалося знайти трек.\n"
            "Спробуй ще раз через кілька секунд."
        )


def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(
        CommandHandler("start", start)
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
