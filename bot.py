import os
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

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["🔎 Пошук музики"],
        ["🚗 В авто", "🏋️ Для спорту"],
        ["😴 Для сну", "🎉 Для вечірки"],
        ["🇺🇦 Українська музика"],
        ["🎧 Як слухати в Telegram"],
    ],
    resize_keyboard=True,
)


BACK_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["⬅️ Назад", "🏠 Головне меню"],
    ],
    resize_keyboard=True,
)


UKRAINIAN_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["🔥 Українські хіти", "🎤 Український поп"],
        ["🎸 Український рок", "🎧 Український реп"],
        ["💙 Українська класика"],
        ["⬅️ Назад", "🏠 Головне меню"],
    ],
    resize_keyboard=True,
)


CAR_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["🔥 Хіти в авто", "🌙 Нічна поїздка"],
        ["⚡ Енергійна музика", "😌 Спокійна дорога"],
        ["⬅️ Назад", "🏠 Головне меню"],
    ],
    resize_keyboard=True,
)


SPORT_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["🔥 Workout Hits", "🏃 Для бігу"],
        ["🏋️ Для залу", "⚡ Максимум енергії"],
        ["⬅️ Назад", "🏠 Головне меню"],
    ],
    resize_keyboard=True,
)


PARTY_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["🔥 Party Hits", "💃 Dance"],
        ["🎧 EDM", "🪩 Disco"],
        ["⬅️ Назад", "🏠 Головне меню"],
    ],
    resize_keyboard=True,
)


SLEEP_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["🌙 Sleep Music", "🌧 Звуки дощу"],
        ["🎹 Piano", "🌊 Relax"],
        ["⬅️ Назад", "🏠 Головне меню"],
    ],
    resize_keyboard=True,
)


# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "🎵 WAVE | Твоя музика 🇺🇦\n\n"
        "🔎 Напиши назву пісні або виконавця.\n\n"
        "Наприклад:\n"
        "• The Weeknd Blinding Lights\n"
        "• Океан Ельзи Обійми\n"
        "• музика в авто\n\n"
        "🎧 Також можеш надіслати свій MP3/M4A — "
        "його можна слухати прямо в Telegram.",
        reply_markup=MAIN_KEYBOARD,
    )


# =========================
# ПОШУК YOUTUBE
# =========================

def youtube_search(query, limit=5):

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "skip_download": True,
    }

    try:

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:

            result = ydl.extract_info(
                f"ytsearch{limit}:{query}",
                download=False,
            )

            return result.get("entries", [])

    except Exception as e:

        print("YouTube search error:", e)

        return []


# =========================
# РЕЗУЛЬТАТИ
# =========================

async def send_results(update, query):

    await update.message.reply_text(
        f"🔎 Шукаю: {query}..."
    )

    results = youtube_search(query, 5)

    if not results:

        await update.message.reply_text(
            "😕 Нічого не знайшов.\n\n"
            "Спробуй написати назву трохи інакше."
        )

        return

    await update.message.reply_text(
        f"🎧 Результати для:\n\n"
        f"🔎 {query}\n\n"
        f"Знайшов {len(results)} варіантів 👇"
    )

    for index, item in enumerate(results, start=1):

        video_id = item.get("id")

        if not video_id:
            continue

        title = item.get("title", "Без назви")

        artist = (
            item.get("channel")
            or item.get("uploader")
            or "YouTube"
        )

        youtube_url = (
            f"https://www.youtube.com/watch?v={video_id}"
        )

        thumbnail = (
            f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
        )

        spotify_url = (
            "https://open.spotify.com/search/"
            + quote_plus(query)
        )

        soundcloud_url = (
            "https://soundcloud.com/search?q="
            + quote_plus(query)
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
            f"🎵 {index}. {title}\n"
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


# =========================
# MP3 / AUDIO
# =========================

async def handle_audio(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    audio = update.message.audio

    if audio:

        title = audio.title or audio.file_name or "Твоя музика"

        performer = audio.performer or ""

        text = f"🎵 {title}"

        if performer:
            text += f"\n👤 {performer}"

        text += "\n\n🎧 Слухай прямо в Telegram ▶️"

        await update.message.reply_text(text)

        return


    document = update.message.document

    if document:

        mime = document.mime_type or ""

        filename = document.file_name or ""

        if (
            mime.startswith("audio/")
            or filename.lower().endswith(
                (".mp3", ".m4a", ".aac", ".wav", ".ogg")
            )
        ):

            file = await document.get_file()

            await update.message.reply_audio(
                audio=file.file_id,
                caption="🎧 Слухай прямо в Telegram ▶️",
            )

            return


# =========================
# ОБРОБКА ТЕКСТУ
# =========================

async def handle_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    text = update.message.text.strip()


    # ГОЛОВНЕ МЕНЮ

    if text == "🏠 Головне меню":

        await start(update, context)

        return


    if text == "⬅️ Назад":

        await update.message.reply_text(
            "🎵 Головне меню",
            reply_markup=MAIN_KEYBOARD,
        )

        return


    if text == "🔎 Пошук музики":

        await update.message.reply_text(
            "🔎 Напиши назву пісні або виконавця 👇",
            reply_markup=MAIN_KEYBOARD,
        )

        return


    if text == "🎧 Як слухати в Telegram":

        await update.message.reply_text(
            "🎧 Як слухати музику прямо в Telegram\n\n"
            "Надішли боту MP3 або M4A файл.\n\n"
            "Telegram покаже вбудований плеєр ▶️\n"
            "і ти зможеш слухати трек прямо в чаті.",
            reply_markup=MAIN_KEYBOARD,
        )

        return


    # =========================
    # УКРАЇНСЬКА МУЗИКА
    # =========================

    if text == "🇺🇦 Українська музика":

        await update.message.reply_text(
            "🇺🇦 Українська музика\n\n"
            "Обери жанр 👇",
            reply_markup=UKRAINIAN_KEYBOARD,
        )

        return


    if text == "🔥 Українські хіти":

        await send_results(
            update,
            "українські хіти 2025 2026",
        )

        return


    if text == "🎤 Український поп":

        await send_results(
            update,
            "українська поп музика хіти",
        )

        return


    if text == "🎸 Український рок":

        await send_results(
            update,
            "український рок кращі пісні",
        )

        return


    if text == "🎧 Український реп":

        await send_results(
            update,
            "український реп хіти",
        )

        return


    if text == "💙 Українська класика":

        await send_results(
            update,
            "кращі українські пісні класика",
        )

        return


    # =========================
    # АВТО
    # =========================

    if text == "🚗 В авто":

        await update.message.reply_text(
            "🚗 Музика в авто\n\n"
            "Який настрій? 👇",
            reply_markup=CAR_KEYBOARD,
        )

        return


    if text == "🔥 Хіти в авто":

        await send_results(
            update,
            "best driving music hits",
        )

        return


    if text == "🌙 Нічна поїздка":

        await send_results(
            update,
            "night drive music",
        )

        return


    if text == "⚡ Енергійна музика":

        await send_results(
            update,
            "energetic driving music",
        )

        return


    if text == "😌 Спокійна дорога":

        await send_results(
            update,
            "chill driving music",
        )

        return


    # =========================
    # СПОРТ
    # =========================

    if text == "🏋️ Для спорту":

        await update.message.reply_text(
            "🏋️ Музика для спорту\n\n"
            "Обери режим 👇",
            reply_markup=SPORT_KEYBOARD,
        )

        return


    if text == "🔥 Workout Hits":

        await send_results(
            update,
            "workout music hits",
        )

        return


    if text == "🏃 Для бігу":

        await send_results(
            update,
            "running music workout",
        )

        return


    if text == "🏋️ Для залу":

        await send_results(
            update,
            "gym workout music",
        )

        return


    if text == "⚡ Максимум енергії":

        await send_results(
            update,
            "high energy workout music",
        )

        return


    # =========================
    # ВЕЧІРКА
    # =========================

    if text == "🎉 Для вечірки":

        await update.message.reply_text(
            "🎉 Музика для вечірки\n\n"
            "Обери стиль 👇",
            reply_markup=PARTY_KEYBOARD,
        )

        return


    if text == "🔥 Party Hits":

        await send_results(
            update,
            "party hits",
        )

        return


    if text == "💃 Dance":

        await send_results(
            update,
            "dance music hits",
        )

        return


    if text == "🎧 EDM":

        await send_results(
            update,
            "EDM hits",
        )

        return


    if text == "🪩 Disco":

        await send_results(
            update,
            "disco dance hits",
        )

        return


    # =========================
    # СОН / RELAX
    # =========================

    if text == "😴 Для сну":

        await update.message.reply_text(
            "😴 Музика для сну\n\n"
            "Обери 👇",
            reply_markup=SLEEP_KEYBOARD,
        )

        return


    if text == "🌙 Sleep Music":

        await send_results(
            update,
            "sleep music relaxing",
        )

        return


    if text == "🌧 Звуки дощу":

        await send_results(
            update,
            "rain sounds sleep",
        )

        return


    if text == "🎹 Piano":

        await send_results(
            update,
            "relaxing piano music",
        )

        return


    if text == "🌊 Relax":

        await send_results(
            update,
            "relaxing chill music",
        )

        return


    # =========================
    # ЗВИЧАЙНИЙ ПОШУК
    # =========================

    await send_results(update, text)


# =========================
# MAIN
# =========================

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
            filters.AUDIO | filters.Document.AUDIO,
            handle_audio,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_text,
        )
    )

    print("WAVE bot started")

    app.run_polling()


if __name__ == "__main__":
    main()
