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


# =========================
# /START
# =========================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        "🎵 WAVE | Твоя музика 🇺🇦\n\n"
        "🔎 Напиши назву пісні або виконавця — "
        "я знайду варіанти.\n\n"
        "🎧 Також можеш надіслати свій MP3/M4A — "
        "його можна слухати прямо в Telegram."
    )


# =========================
# ПОШУК 5 РЕЗУЛЬТАТІВ
# =========================

def find_tracks(query):
    options = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": True,
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        result = ydl.extract_info(
            f"ytsearch5:{query}",
            download=False,
        )

    tracks = []

    for item in result.get("entries", []):
        if not item:
            continue

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

        tracks.append(
            {
                "title": title,
                "artist": artist,
                "url": youtube_url,
                "thumbnail": thumbnail,
            }
        )

    return tracks


# =========================
# ОБРОБКА ТЕКСТОВОГО ПОШУКУ
# =========================

async def search_music(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.message.text.strip()

    if not query:
        return

    status = await update.message.reply_text(
        "🔎 Шукаю музику..."
    )

    try:
        tracks = await asyncio.to_thread(
            find_tracks,
            query,
        )

        try:
            await status.delete()
        except Exception:
            pass

        if not tracks:
            await update.message.reply_text(
                "😕 Нічого не знайшов.\n\n"
                "Спробуй написати назву пісні "
                "та виконавця."
            )
            return

        await update.message.reply_text(
            f"🎧 Результати для:\n\n"
            f"🔎 {query}\n\n"
            f"Знайшов {len(tracks)} варіантів 👇"
        )

        for number, track in enumerate(
            tracks,
            start=1,
        ):
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
                f"🎵 {number}. {track['title']}\n"
                f"👤 {track['artist']}"
            )

            try:
                await update.message.reply_photo(
                    photo=track["thumbnail"],
                    caption=caption,
                    reply_markup=keyboard,
                )

            except Exception as photo_error:
                print(
                    "PHOTO ERROR:",
                    photo_error,
                )

                await update.message.reply_text(
                    caption,
                    reply_markup=keyboard,
                )

    except Exception as error:
        print(
            "SEARCH ERROR:",
            error,
        )

        try:
            await status.delete()
        except Exception:
            pass

        await update.message.reply_text(
            "⚠️ Не вдалося виконати пошук.\n\n"
            "Спробуй ще раз трохи пізніше."
        )


# =========================
# MP3 / AUDIO
# =========================

async def receive_audio(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    audio = update.message.audio

    if not audio:
        return

    try:
        await update.message.reply_audio(
            audio=audio.file_id,
            title=(
                audio.title
                or audio.file_name
                or "WAVE Track"
            ),
            performer=(
                audio.performer
                or "WAVE"
            ),
            caption=(
                "🎧 Слухай прямо в Telegram ▶️"
            ),
        )

    except Exception as error:
        print(
            "AUDIO ERROR:",
            error,
        )

        await update.message.reply_text(
            "⚠️ Не вдалося обробити аудіо."
        )


# =========================
# MP3/M4A ЯК DOCUMENT
# =========================

async def receive_document(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    document = update.message.document

    if not document:
        return

    filename = (
        document.file_name or ""
    ).lower()

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
            "⚠️ Надішли аудіофайл:\n"
            "MP3, M4A, AAC, OGG або WAV."
        )
        return

    try:
        await update.message.reply_audio(
            audio=document.file_id,
            title=(
                document.file_name
                or "WAVE Track"
            ),
            performer="WAVE",
            caption=(
                "🎧 Слухай прямо в Telegram ▶️"
            ),
        )

    except Exception as error:
        print(
            "DOCUMENT ERROR:",
            error,
        )

        await update.message.reply_text(
            "⚠️ Не вдалося відкрити цей файл "
            "як аудіо."
        )


# =========================
# ЗАПУСК БОТА
# =========================

def main():
    app = (
        Application
        .builder()
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
            filters.Document.ALL,
            receive_document,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT
            & ~filters.COMMAND,
            search_music,
        )
    )

    print("WAVE bot started")

    app.run_polling()


if __name__ == "__main__":
    main()
