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


# =========================================================
# ГОЛОВНЕ МЕНЮ
# =========================================================

def main_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["🔎 Пошук музики"],
            ["🚗 В авто", "🏋️ Для спорту"],
            ["😴 Для сну", "🎉 Для вечірки"],
            ["🇺🇦 Українська музика"],
            ["🎧 Як слухати в Telegram"],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


# =========================================================
# START
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        "🎵 WAVE | Твоя музика 🇺🇦\n\n"
        "Знайди музику під свій настрій ✨\n\n"
        "🔎 Напиши назву пісні або виконавця\n"
        "або обери категорію нижче 👇\n\n"
        "🎧 Також можеш надіслати свій MP3/M4A — "
        "його можна слухати прямо в Telegram.",
        reply_markup=main_keyboard(),
    )


# =========================================================
# КНОПКА ПОШУКУ
# =========================================================

async def search_button(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        "🔎 Що хочеш послухати?\n\n"
        "Напиши назву пісні або виконавця 👇\n\n"
        "Наприклад:\n"
        "The Weeknd Blinding Lights\n"
        "Океан Ельзи Обійми"
    )


# =========================================================
# HELP
# =========================================================

async def help_audio(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        "🎧 Як слухати музику у WAVE\n\n"
        "🔎 Напиши назву пісні — бот знайде "
        "варіанти на музичних сервісах.\n\n"
        "▶️ YouTube — відкриває оригінал.\n"
        "🟢 Spotify — шукає трек у Spotify.\n"
        "☁️ SoundCloud — шукає у SoundCloud.\n\n"
        "📎 Свій MP3/M4A можеш надіслати прямо "
        "в цей чат — він відкриється у плеєрі Telegram."
    )


# =========================================================
# YOUTUBE SEARCH
# =========================================================

def youtube_search(query: str):
    options = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "skip_download": True,
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        data = ydl.extract_info(
            f"ytsearch15:{query}",
            download=False,
        )

    return data.get("entries", [])


# =========================================================
# ФІЛЬТР РЕЗУЛЬТАТІВ
# =========================================================

def is_bad_result(item):
    title = (item.get("title") or "").lower()

    bad_words = [
        "1 hour",
        "1hour",
        "one hour",
        "2 hours",
        "3 hours",
        "10 hours",
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

    return any(word in title for word in bad_words)


def prepare_results(entries):
    good = []
    fallback = []
    seen = set()

    for item in entries:

        if not item:
            continue

        video_id = item.get("id")

        if not video_id:
            continue

        if video_id in seen:
            continue

        seen.add(video_id)

        if is_bad_result(item):
            fallback.append(item)
        else:
            good.append(item)

    results = good[:5]

    if len(results) < 5:
        results.extend(
            fallback[:5 - len(results)]
        )

    return results


# =========================================================
# ВІДПРАВКА РЕЗУЛЬТАТІВ
# =========================================================

async def perform_search(
    update: Update,
    query: str,
    display_query: str = None,
):

    if display_query is None:
        display_query = query

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
                "Спробуй інший запит."
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
            f"🎧 {display_query}\n\n"
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

                print("PHOTO ERROR:", error)

                await update.message.reply_text(
                    caption,
                    reply_markup=keyboard,
                )

    except Exception as error:

        print("SEARCH ERROR:", error)

        try:
            await loading.delete()
        except Exception:
            pass

        await update.message.reply_text(
            "⚠️ WAVE зараз не зміг виконати пошук.\n"
            "Спробуй ще раз."
        )


# =========================================================
# ЗВИЧАЙНИЙ ПОШУК
# =========================================================

async def search_music(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.message.text.strip()

    if not query:
        return

    # Невідома команда
    if query.startswith("/"):

        await update.message.reply_text(
            "💡 Для запуску WAVE використовуй /start",
            reply_markup=main_keyboard(),
        )

        return

    await perform_search(
        update,
        query,
        f"Результати для:\n🔎 {query}",
    )


# =========================================================
# КАТЕГОРІЇ
# =========================================================

async def car_music(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await perform_search(
        update,
        "best driving music playlist hits",
        "🚗 Музика в авто",
    )


async def sport_music(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await perform_search(
        update,
        "best workout gym music hits",
        "🏋️ Музика для спорту",
    )


async def sleep_music(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await perform_search(
        update,
        "relaxing sleep music",
        "😴 Музика для сну",
    )


async def party_music(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await perform_search(
        update,
        "best party hits music",
        "🎉 Музика для вечірки",
    )


async def ukrainian_music(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await perform_search(
        update,
        "українські пісні хіти",
        "🇺🇦 Українська музика",
    )


# =========================================================
# ВЛАСНІ MP3 / M4A
# =========================================================

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

        await message.reply_text(
            "⚠️ Не вдалося відкрити цей аудіофайл."
        )


# =========================================================
# MAIN
# =========================================================

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

    # Пошук
    app.add_handler(
        MessageHandler(
            filters.Regex(
                r"^🔎 Пошук музики$"
            ),
            search_button,
        )
    )

    # Категорії
    app.add_handler(
        MessageHandler(
            filters.Regex(
                r"^🚗 В авто$"
            ),
            car_music,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Regex(
                r"^🏋️ Для спорту$"
            ),
            sport_music,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Regex(
                r"^😴 Для сну$"
            ),
            sleep_music,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Regex(
                r"^🎉 Для вечірки$"
            ),
            party_music,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Regex(
                r"^🇺🇦 Українська музика$"
            ),
            ukrainian_music,
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

    # Аудіо
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

    # Звичайний текст
    app.add_handler(
        MessageHandler(
            filters.TEXT
            & ~filters.COMMAND,
            search_music,
        )
    )

    print(
        "🎵 WAVE 2.0 started"
    )

    app.run_polling()


if __name__ == "__main__":
    main()
