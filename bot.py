import os
import asyncio
from urllib.parse import quote_plus

import yt_dlp

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
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
# ГОЛОВНЕ МЕНЮ
# =========================

def main_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["🔎 Пошук музики"],
            ["🎧 Як слухати в Telegram"],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


# =========================
# START
# =========================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        "🎵 WAVE | Твоя музика 🇺🇦\n\n"
        "🔎 Напиши назву пісні або виконавця.\n\n"
        "Наприклад:\n"
        "• The Weeknd Blinding Lights\n"
        "• Океан Ельзи Обійми\n"
        "• музика в авто\n\n"
        "🎧 Також можеш надіслати свій MP3/M4A — "
        "його можна слухати прямо в Telegram.",
        reply_markup=main_keyboard(),
    )


# =========================
# КНОПКА ПОШУКУ
# =========================

async def search_button(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        "🔎 Напиши назву пісні або виконавця 👇\n\n"
        "Наприклад:\n"
        "The Weeknd Blinding Lights"
    )


# =========================
# ЯК СЛУХАТИ
# =========================

async def help_audio(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        "🎧 Як працює WAVE\n\n"
        "🔎 Напиши назву пісні — WAVE знайде "
        "варіанти на музичних сервісах.\n\n"
        "📎 Якщо надішлеш свій MP3/M4A файл, "
        "WAVE поверне його як аудіоплеєр Telegram ▶️"
    )


# =========================
# YOUTUBE SEARCH
# =========================

def youtube_search(query: str):
    options = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "skip_download": True,
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        data = ydl.extract_info(
            f"ytsearch12:{query}",
            download=False,
        )

    return data.get("entries", [])


# =========================
# ФІЛЬТРАЦІЯ
# =========================

def is_bad_result(item):
    title = (item.get("title") or "").lower()

    bad_words = [
        "1 hour",
        "1hour",
        "one hour",
        "10 hours",
        "10 hour",
        "8d audio",
        "slowed",
        "reverb",
        "nightcore",
        "sped up",
        "karaoke",
        "instrumental",
        "reaction",
        "tutorial",
        "cover",
    ]

    return any(
        word in title
        for word in bad_words
    )


def prepare_results(entries):
    good = []
    fallback = []
    seen_ids = set()

    for item in entries:
        if not item:
            continue

        video_id = item.get("id")

        if not video_id:
            continue

        if video_id in seen_ids:
            continue

        seen_ids.add(video_id)

        if is_bad_result(item):
            fallback.append(item)
        else:
            good.append(item)

    results = good[:5]

    if len(results) < 5:
        needed = 5 - len(results)
        results.extend(
            fallback[:needed]
        )

    return results


# =========================
# ПОШУК МУЗИКИ
# =========================

async def search_music(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.message.text.strip()

    if not query:
        return

    # Не відправляємо /команди у пошук
    if query.startswith("/"):
        await update.message.reply_text(
            "💡 Для запуску WAVE натисни /start",
            reply_markup=main_keyboard(),
        )
        return

    loading = await update.message.reply_text(
        "🔎 WAVE шукає музику..."
    )

    try:
        entries = await asyncio.to_thread(
            youtube_search,
            query,
        )

        results = prepare_results(entries)

        try:
            await loading.delete()
        except Exception:
            pass

        if not results:
            await update.message.reply_text(
                "😕 Нічого не знайшов.\n\n"
                "Спробуй написати назву пісні "
                "та виконавця точніше."
            )
            return

        encoded_query = quote_plus(query)

        spotify_url = (
            "https://open.spotify.com/search/"
            + encoded_query
        )

        soundcloud_url = (
            "https://soundcloud.com/search?q="
            + encoded_query
        )

        await update.message.reply_text(
            "🎧 Результати для:\n\n"
            f"🔎 {query}\n\n"
            f"Знайшов {len(results)} варіантів 👇"
        )

        for number, item in enumerate(
            results,
            start=1,
        ):
            video_id = item.get("id")

            title = (
                item.get("title")
                or "Без назви"
            )

            artist = (
                item.get("channel")
                or item.get("uploader")
                or "Невідомий виконавець"
            )

            youtube_url = (
                "https://www.youtube.com/watch?v="
                + video_id
            )

            thumbnail = (
                "https://i.ytimg.com/vi/"
                + video_id
                + "/hqdefault.jpg"
            )

            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "▶️ YouTube",
                            url=youtube_url,
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "🟢 Spotify",
                            url=spotify_url,
                        ),
                        InlineKeyboardButton(
                            "☁️ SoundCloud",
                            url=soundcloud_url,
                        ),
                    ],
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

            except Exception as error:
                print(
                    "PHOTO ERROR:",
                    error,
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
            await loading.delete()
        except Exception:
            pass

        await update.message.reply_text(
            "⚠️ Не вдалося виконати пошук.\n"
            "Спробуй ще раз."
        )


# =========================
# ВЛАСНІ АУДІОФАЙЛИ
# =========================

async def receive_audio(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.message

    if message.audio:
        audio = message.audio

        title = (
            audio.title
            or audio.file_name
            or "WAVE Track"
        )

        performer = (
            audio.performer
            or "WAVE"
        )

        await message.reply_audio(
            audio=audio.file_id,
            title=title,
            performer=performer,
            caption="🎧 Слухай прямо в Telegram ▶️",
        )

        return

    document = message.document

    if not document:
        return

    filename = (
        document.file_name
        or "WAVE Track"
    )

    mime = (
        document.mime_type
        or ""
    )

    allowed_extensions = (
        ".mp3",
        ".m4a",
        ".aac",
        ".ogg",
        ".wav",
        ".flac",
    )

    allowed = (
        mime.startswith("audio/")
        or filename.lower().endswith(
            allowed_extensions
        )
    )

    if not allowed:
        return

    try:
        await message.reply_audio(
            audio=document.file_id,
            title=filename,
            performer="WAVE",
            caption="🎧 Слухай прямо в Telegram ▶️",
        )

    except Exception as error:
        print(
            "AUDIO ERROR:",
            error,
        )


# =========================
# MAIN
# =========================

def main():
    app = (
        Application.builder()
        .token(TOKEN)
        .build()
    )

    # /start
    app.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    # Кнопка пошуку
    app.add_handler(
        MessageHandler(
            filters.Regex(
                r"^🔎 Пошук музики$"
            ),
            search_button,
        )
    )

    # Допомога
    app.add_handler(
        MessageHandler(
            filters.Regex(
                r"^🎧 Як слухати в Telegram$"
            ),
            help_audio,
        )
    )

    # MP3 / audio
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

    # Звичайний текст = пошук
    app.add_handler(
        MessageHandler(
            filters.TEXT
            & ~filters.COMMAND,
            search_music,
        )
    )

    print("🎵 WAVE bot started")

    app.run_polling()


if __name__ == "__main__":
    main()
