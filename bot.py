import os
import asyncio
from urllib.parse import quote_plus

import yt_dlp
import psycopg

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
    CallbackQueryHandler,
    ContextTypes,
    filters,
)


# =========================================================
# НАЛАШТУВАННЯ
# =========================================================

TOKEN = os.environ["BOT_TOKEN"]
DATABASE_URL = os.environ["DATABASE_URL"]


# =========================================================
# ГОЛОВНЕ МЕНЮ
# =========================================================

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["🔎 Пошук музики", "❤️ Моя музика"],
        ["🚗 В авто", "🏋️ Для спорту"],
        ["😴 Для сну", "🎉 Для вечірки"],
        ["🇺🇦 Українська музика"],
        ["🎧 Як слухати в Telegram"],
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


# =========================================================
# POSTGRESQL
# =========================================================

def init_database():
    """
    Створює таблицю favorites автоматично,
    якщо її ще немає.
    """

    with psycopg.connect(DATABASE_URL) as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS favorites (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    video_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    artist TEXT,
                    duration INTEGER,
                    thumbnail TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, video_id)
                );
                """
            )

        conn.commit()

    print("PostgreSQL ready")


def db_add_favorite(user_id, track):

    with psycopg.connect(DATABASE_URL) as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                INSERT INTO favorites (
                    user_id,
                    video_id,
                    title,
                    artist,
                    duration,
                    thumbnail
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id, video_id)
                DO NOTHING
                RETURNING id;
                """,
                (
                    user_id,
                    track["id"],
                    track["title"],
                    track["artist"],
                    track.get("duration"),
                    track.get("thumbnail"),
                ),
            )

            result = cur.fetchone()

        conn.commit()

    return result is not None


def db_get_favorites(user_id):

    with psycopg.connect(DATABASE_URL) as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    video_id,
                    title,
                    artist,
                    duration,
                    thumbnail
                FROM favorites
                WHERE user_id = %s
                ORDER BY created_at DESC;
                """,
                (user_id,),
            )

            rows = cur.fetchall()

    tracks = []

    for row in rows:

        tracks.append(
            {
                "id": row[0],
                "title": row[1],
                "artist": row[2],
                "duration": row[3],
                "thumbnail": row[4],
            }
        )

    return tracks


def db_remove_favorite(user_id, video_id):

    with psycopg.connect(DATABASE_URL) as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                DELETE FROM favorites
                WHERE user_id = %s
                AND video_id = %s;
                """,
                (
                    user_id,
                    video_id,
                ),
            )

        conn.commit()


def db_clear_favorites(user_id):

    with psycopg.connect(DATABASE_URL) as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                DELETE FROM favorites
                WHERE user_id = %s;
                """,
                (user_id,),
            )

        conn.commit()


# =========================================================
# ДОПОМІЖНІ ФУНКЦІЇ
# =========================================================

def format_duration(seconds):

    if not seconds:
        return "—"

    try:
        seconds = int(seconds)

    except (ValueError, TypeError):
        return "—"

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"

    return f"{minutes}:{secs:02d}"


def clean_text(text, max_length=500):

    if not text:
        return ""

    text = str(text)

    if len(text) > max_length:
        return text[:max_length] + "..."

    return text


# =========================================================
# START
# =========================================================

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
        "❤️ Зберігай улюблені треки "
        "в розділі «Моя музика».\n\n"
        "🎧 Також можеш надіслати свій MP3/M4A — "
        "його можна слухати прямо в Telegram.",
        reply_markup=MAIN_KEYBOARD,
    )


# =========================================================
# YOUTUBE SEARCH
# =========================================================

def youtube_search_sync(query, limit=5):

    options = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
        "skip_download": True,
        "noplaylist": True,
    }

    try:

        with yt_dlp.YoutubeDL(options) as ydl:

            result = ydl.extract_info(
                f"ytsearch{limit}:{query}",
                download=False,
            )

            return result.get("entries", [])

    except Exception as error:

        print("YouTube search error:", error)

        return []


async def youtube_search(query, limit=5):

    return await asyncio.to_thread(
        youtube_search_sync,
        query,
        limit,
    )


# =========================================================
# КАРТКА ТРЕКУ
# =========================================================

async def send_track_card(
    message,
    item,
    index=None,
    favorite_mode=False,
):

    video_id = item.get("id")

    if not video_id:
        return

    title = clean_text(
        item.get("title") or "Без назви",
        200,
    )

    artist = clean_text(
        item.get("artist")
        or item.get("channel")
        or item.get("uploader")
        or "YouTube",
        100,
    )

    duration = item.get("duration")

    youtube_url = (
        f"https://www.youtube.com/watch?v={video_id}"
    )

    service_query = f"{artist} {title}"

    spotify_url = (
        "https://open.spotify.com/search/"
        + quote_plus(service_query)
    )

    soundcloud_url = (
        "https://soundcloud.com/search?q="
        + quote_plus(service_query)
    )

    thumbnail = (
        item.get("thumbnail")
        or f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
    )

    number = f"{index}. " if index else ""

    caption = (
        f"🎵 {number}{title}\n\n"
        f"👤 {artist}\n"
        f"⏱ {format_duration(duration)}"
    )

    buttons = [
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

    if favorite_mode:

        buttons.append(
            [
                InlineKeyboardButton(
                    "🗑 Видалити",
                    callback_data=f"remove:{video_id}",
                )
            ]
        )

    else:

        buttons.append(
            [
                InlineKeyboardButton(
                    "❤️ Зберегти",
                    callback_data=f"save:{video_id}",
                )
            ]
        )

    keyboard = InlineKeyboardMarkup(buttons)

    try:

        await message.reply_photo(
            photo=thumbnail,
            caption=caption,
            reply_markup=keyboard,
        )

    except Exception as error:

        print("Photo error:", error)

        await message.reply_text(
            caption,
            reply_markup=keyboard,
        )


# =========================================================
# ПОШУК
# =========================================================

async def send_results(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    query,
):

    status = await update.message.reply_text(
        f"🔎 Шукаю «{query}»..."
    )

    results = await youtube_search(
        query,
        5,
    )

    try:
        await status.delete()

    except Exception:
        pass

    if not results:

        await update.message.reply_text(
            "😕 Нічого не знайшов.\n\n"
            "Спробуй написати назву трохи інакше."
        )

        return

    tracks = {}

    for item in results:

        video_id = item.get("id")

        if not video_id:
            continue

        tracks[video_id] = {
            "id": video_id,
            "title": item.get("title") or "Без назви",
            "artist": (
                item.get("channel")
                or item.get("uploader")
                or "YouTube"
            ),
            "duration": item.get("duration"),
            "thumbnail": (
                item.get("thumbnail")
                or f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
            ),
        }

    context.user_data["search_tracks"] = tracks

    await update.message.reply_text(
        f"🎧 Результати для:\n\n"
        f"🔎 {query}\n\n"
        f"Знайшов {len(tracks)} варіантів 👇"
    )

    for index, item in enumerate(
        results,
        start=1,
    ):

        await send_track_card(
            update.message,
            item,
            index=index,
        )


# =========================================================
# CALLBACK КНОПКИ
# =========================================================

async def button_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query

    data = query.data

    user_id = query.from_user.id

    # -----------------------------------------------------
    # ❤️ ЗБЕРЕГТИ
    # -----------------------------------------------------

    if data.startswith("save:"):

        video_id = data.split(":", 1)[1]

        tracks = context.user_data.get(
            "search_tracks",
            {},
        )

        track = tracks.get(video_id)

        if not track:

            await query.answer(
                "Зроби пошук треку ще раз 🎵",
                show_alert=True,
            )

            return

        try:

            added = await asyncio.to_thread(
                db_add_favorite,
                user_id,
                track,
            )

        except Exception as error:

            print("Database save error:", error)

            await query.answer(
                "Помилка збереження 😕",
                show_alert=True,
            )

            return

        if added:

            await query.answer(
                "❤️ Додано в «Моя музика»",
                show_alert=True,
            )

        else:

            await query.answer(
                "Цей трек уже збережений ❤️",
                show_alert=True,
            )

        return

    # -----------------------------------------------------
    # 🗑 ВИДАЛИТИ
    # -----------------------------------------------------

    if data.startswith("remove:"):

        video_id = data.split(":", 1)[1]

        try:

            await asyncio.to_thread(
                db_remove_favorite,
                user_id,
                video_id,
            )

            await query.answer(
                "🗑 Видалено",
            )

            try:
                await query.message.delete()

            except Exception:
                pass

        except Exception as error:

            print("Database remove error:", error)

            await query.answer(
                "Не вдалося видалити 😕",
                show_alert=True,
            )

        return

    # -----------------------------------------------------
    # 🗑 ОЧИСТИТИ ВСЕ
    # -----------------------------------------------------

    if data == "clear_favorites":

        try:

            await asyncio.to_thread(
                db_clear_favorites,
                user_id,
            )

            await query.answer(
                "🗑 Обране очищено",
                show_alert=True,
            )

            await query.message.reply_text(
                "❤️ У «Моя музика» тепер порожньо.",
                reply_markup=MAIN_KEYBOARD,
            )

        except Exception as error:

            print("Database clear error:", error)

            await query.answer(
                "Помилка бази даних 😕",
                show_alert=True,
            )

        return


# =========================================================
# ❤️ МОЯ МУЗИКА
# =========================================================

async def show_favorites(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    user_id = update.effective_user.id

    try:

        favorites = await asyncio.to_thread(
            db_get_favorites,
            user_id,
        )

    except Exception as error:

        print("Database read error:", error)

        await update.message.reply_text(
            "😕 Не вдалося відкрити «Моя музика»."
        )

        return

    if not favorites:

        await update.message.reply_text(
            "❤️ У «Моя музика» поки порожньо.\n\n"
            "Знайди пісню та натисни "
            "«❤️ Зберегти» під карткою.",
            reply_markup=MAIN_KEYBOARD,
        )

        return

    await update.message.reply_text(
        f"❤️ Моя музика\n\n"
        f"Збережено треків: {len(favorites)} 👇"
    )

    for index, track in enumerate(
        favorites,
        start=1,
    ):

        await send_track_card(
            update.message,
            track,
            index=index,
            favorite_mode=True,
        )

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🗑 Очистити обране",
                    callback_data="clear_favorites",
                )
            ]
        ]
    )

    await update.message.reply_text(
        "❤️ Кінець списку",
        reply_markup=keyboard,
    )


# =========================================================
# MP3 / AUDIO
# =========================================================

async def handle_audio(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    audio = update.message.audio

    if audio:

        title = (
            audio.title
            or audio.file_name
            or "Твоя музика"
        )

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
                (
                    ".mp3",
                    ".m4a",
                    ".aac",
                    ".wav",
                    ".ogg",
                )
            )
        ):

            file = await document.get_file()

            await update.message.reply_audio(
                audio=file.file_id,
                caption="🎧 Слухай прямо в Telegram ▶️",
            )


# =========================================================
# ТЕКСТОВЕ МЕНЮ
# =========================================================

async def handle_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    text = update.message.text.strip()

    # -----------------------------------------------------
    # ГОЛОВНЕ МЕНЮ
    # -----------------------------------------------------

    if text in (
        "🏠 Головне меню",
        "⬅️ Назад",
    ):

        await update.message.reply_text(
            "🎵 WAVE | Головне меню",
            reply_markup=MAIN_KEYBOARD,
        )

        return

    # -----------------------------------------------------
    # МОЯ МУЗИКА
    # -----------------------------------------------------

    if text == "❤️ Моя музика":

        await show_favorites(
            update,
            context,
        )

        return

    # -----------------------------------------------------
    # ПОШУК
    # -----------------------------------------------------

    if text == "🔎 Пошук музики":

        await update.message.reply_text(
            "🔎 Напиши назву пісні або виконавця 👇",
            reply_markup=MAIN_KEYBOARD,
        )

        return

    # -----------------------------------------------------
    # TELEGRAM AUDIO
    # -----------------------------------------------------

    if text == "🎧 Як слухати в Telegram":

        await update.message.reply_text(
            "🎧 Як слухати музику прямо в Telegram\n\n"
            "Надішли боту свій MP3 або M4A файл.\n\n"
            "Telegram покаже вбудований плеєр ▶️",
            reply_markup=MAIN_KEYBOARD,
        )

        return

    # -----------------------------------------------------
    # УКРАЇНСЬКА МУЗИКА
    # -----------------------------------------------------

    if text == "🇺🇦 Українська музика":

        await update.message.reply_text(
            "🇺🇦 Українська музика\n\n"
            "Обери жанр 👇",
            reply_markup=UKRAINIAN_KEYBOARD,
        )

        return

    # -----------------------------------------------------
    # АВТО
    # -----------------------------------------------------

    if text == "🚗 В авто":

        await update.message.reply_text(
            "🚗 Музика в авто\n\n"
            "Обери настрій 👇",
            reply_markup=CAR_KEYBOARD,
        )

        return

    # -----------------------------------------------------
    # СПОРТ
    # -----------------------------------------------------

    if text == "🏋️ Для спорту":

        await update.message.reply_text(
            "🏋️ Музика для спорту\n\n"
            "Обери режим 👇",
            reply_markup=SPORT_KEYBOARD,
        )

        return

    # -----------------------------------------------------
    # ВЕЧІРКА
    # -----------------------------------------------------

    if text == "🎉 Для вечірки":

        await update.message.reply_text(
            "🎉 Музика для вечірки\n\n"
            "Обери стиль 👇",
            reply_markup=PARTY_KEYBOARD,
        )

        return

    # -----------------------------------------------------
    # СОН
    # -----------------------------------------------------

    if text == "😴 Для сну":

        await update.message.reply_text(
            "😴 Музика для сну\n\n"
            "Обери 👇",
            reply_markup=SLEEP_KEYBOARD,
        )

        return

    # -----------------------------------------------------
    # КАТЕГОРІЇ
    # -----------------------------------------------------

    categories = {

        "🔥 Українські хіти":
            "українські музичні хіти",

        "🎤 Український поп":
            "українська поп музика",

        "🎸 Український рок":
            "український рок",

        "🎧 Український реп":
            "український реп",

        "💙 Українська класика":
            "кращі українські класичні пісні",

        "🔥 Хіти в авто":
            "best driving music hits",

        "🌙 Нічна поїздка":
            "night drive music",

        "⚡ Енергійна музика":
            "energetic driving music",

        "😌 Спокійна дорога":
            "chill driving music",

        "🔥 Workout Hits":
            "workout music hits",

        "🏃 Для бігу":
            "running workout music",

        "🏋️ Для залу":
            "gym workout music",

        "⚡ Максимум енергії":
            "high energy workout music",

        "🔥 Party Hits":
            "party music hits",

        "💃 Dance":
            "dance music hits",

        "🎧 EDM":
            "EDM music hits",

        "🪩 Disco":
            "disco dance hits",

        "🌙 Sleep Music":
            "relaxing sleep music",

        "🌧 Звуки дощу":
            "rain sounds sleep",

        "🎹 Piano":
            "relaxing piano music",

        "🌊 Relax":
            "relaxing chill music",
    }

    if text in categories:

        await send_results(
            update,
            context,
            categories[text],
        )

        return

    # -----------------------------------------------------
    # ЗВИЧАЙНИЙ ПОШУК
    # -----------------------------------------------------

    await send_results(
        update,
        context,
        text,
    )


# =========================================================
# MAIN
# =========================================================

def main():

    print("Connecting to PostgreSQL...")

    init_database()

    print("Starting WAVE bot...")

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
        CallbackQueryHandler(
            button_callback,
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

    print("🎵 WAVE bot started")

    app.run_polling()


if __name__ == "__main__":
    main()
