import os
import asyncio
import random
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

FAVORITES_PER_PAGE = 5


# =========================================================
# КЛАВІАТУРИ
# =========================================================

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["🔎 Пошук музики", "❤️ Моя музика"],
        ["📂 Мої плейлисти"],
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
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:

            # Стару таблицю НЕ видаляємо
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

            # Плейлисти
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS playlists (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    name TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, name)
                );
                """
            )

            # Треки плейлистів
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS playlist_tracks (
                    id SERIAL PRIMARY KEY,
                    playlist_id INTEGER NOT NULL
                        REFERENCES playlists(id)
                        ON DELETE CASCADE,
                    video_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    artist TEXT,
                    duration INTEGER,
                    thumbnail TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(playlist_id, video_id)
                );
                """
            )

        conn.commit()

    print("PostgreSQL ready")


# =========================================================
# FAVORITES DB
# =========================================================

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

    return [
        {
            "id": row[0],
            "title": row[1],
            "artist": row[2],
            "duration": row[3],
            "thumbnail": row[4],
        }
        for row in rows
    ]


def db_search_favorites(user_id, search_text):
    search_value = f"%{search_text}%"

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
                AND (
                    title ILIKE %s
                    OR artist ILIKE %s
                )
                ORDER BY created_at DESC;
                """,
                (
                    user_id,
                    search_value,
                    search_value,
                ),
            )

            rows = cur.fetchall()

    return [
        {
            "id": row[0],
            "title": row[1],
            "artist": row[2],
            "duration": row[3],
            "thumbnail": row[4],
        }
        for row in rows
    ]


def db_remove_favorite(user_id, video_id):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM favorites
                WHERE user_id = %s
                AND video_id = %s;
                """,
                (user_id, video_id),
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
# PLAYLISTS DB
# =========================================================

def db_create_playlist(user_id, name):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO playlists (
                    user_id,
                    name
                )
                VALUES (%s, %s)
                ON CONFLICT (user_id, name)
                DO NOTHING
                RETURNING id;
                """,
                (user_id, name),
            )

            result = cur.fetchone()

        conn.commit()

    return result is not None


def db_get_playlists(user_id):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    p.id,
                    p.name,
                    COUNT(pt.id)
                FROM playlists p
                LEFT JOIN playlist_tracks pt
                    ON pt.playlist_id = p.id
                WHERE p.user_id = %s
                GROUP BY p.id, p.name, p.created_at
                ORDER BY p.created_at DESC;
                """,
                (user_id,),
            )

            rows = cur.fetchall()

    return [
        {
            "id": row[0],
            "name": row[1],
            "count": row[2],
        }
        for row in rows
    ]


def db_get_playlist(user_id, playlist_id):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name
                FROM playlists
                WHERE id = %s
                AND user_id = %s;
                """,
                (playlist_id, user_id),
            )

            row = cur.fetchone()

    if not row:
        return None

    return {
        "id": row[0],
        "name": row[1],
    }


def db_get_playlist_tracks(user_id, playlist_id):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    pt.video_id,
                    pt.title,
                    pt.artist,
                    pt.duration,
                    pt.thumbnail
                FROM playlist_tracks pt
                JOIN playlists p
                    ON p.id = pt.playlist_id
                WHERE pt.playlist_id = %s
                AND p.user_id = %s
                ORDER BY pt.created_at DESC;
                """,
                (playlist_id, user_id),
            )

            rows = cur.fetchall()

    return [
        {
            "id": row[0],
            "title": row[1],
            "artist": row[2],
            "duration": row[3],
            "thumbnail": row[4],
        }
        for row in rows
    ]


def db_add_track_to_playlist(
    user_id,
    playlist_id,
    track,
):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:

            # Перевіряємо, що плейлист належить користувачу
            cur.execute(
                """
                SELECT id
                FROM playlists
                WHERE id = %s
                AND user_id = %s;
                """,
                (playlist_id, user_id),
            )

            if not cur.fetchone():
                return False

            cur.execute(
                """
                INSERT INTO playlist_tracks (
                    playlist_id,
                    video_id,
                    title,
                    artist,
                    duration,
                    thumbnail
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (playlist_id, video_id)
                DO NOTHING
                RETURNING id;
                """,
                (
                    playlist_id,
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


def db_remove_playlist_track(
    user_id,
    playlist_id,
    video_id,
):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM playlist_tracks
                WHERE playlist_id = %s
                AND video_id = %s
                AND EXISTS (
                    SELECT 1
                    FROM playlists
                    WHERE id = %s
                    AND user_id = %s
                );
                """,
                (
                    playlist_id,
                    video_id,
                    playlist_id,
                    user_id,
                ),
            )

        conn.commit()


def db_delete_playlist(user_id, playlist_id):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM playlists
                WHERE id = %s
                AND user_id = %s;
                """,
                (playlist_id, user_id),
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


def clear_modes(context):
    context.user_data.pop(
        "favorite_search_mode",
        None,
    )
    context.user_data.pop(
        "playlist_create_mode",
        None,
    )


# =========================================================
# START
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    clear_modes(context)

    await update.message.reply_text(
        "🎵 WAVE | Твоя музика 🇺🇦\n\n"
        "🔎 Шукай музику та виконавців.\n"
        "❤️ Зберігай улюблені треки.\n"
        "📂 Створюй власні плейлисти.\n\n"
        "🎧 Також можеш надіслати свій MP3/M4A.",
        reply_markup=MAIN_KEYBOARD,
    )


# =========================================================
# YOUTUBE SEARCH
# =========================================================

def youtube_search_sync(search_text, limit=5):
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
                f"ytsearch{limit}:{search_text}",
                download=False,
            )

            return result.get("entries", [])

    except Exception as error:
        print("YouTube search error:", error)
        return []


async def youtube_search(search_text, limit=5):
    return await asyncio.to_thread(
        youtube_search_sync,
        search_text,
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
    playlist_id=None,
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

    # Якщо це трек усередині плейлиста
    if playlist_id is not None:
        buttons.append(
            [
                InlineKeyboardButton(
                    "🗑 Прибрати з плейлиста",
                    callback_data=(
                        f"plremove:{playlist_id}:{video_id}"
                    ),
                )
            ]
        )

    else:
        # Додати в плейлист можна з результатів
        # пошуку та з "Моя музика"
        buttons.append(
            [
                InlineKeyboardButton(
                    "➕ До плейлиста",
                    callback_data=f"plchoose:{video_id}",
                )
            ]
        )

        if favorite_mode:
            buttons.append(
                [
                    InlineKeyboardButton(
                        "🗑 Видалити з обраного",
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
    search_text,
):
    status = await update.message.reply_text(
        f"🔎 Шукаю «{search_text}»..."
    )

    results = await youtube_search(
        search_text,
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
        f"🔎 {search_text}\n\n"
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
# ❤️ МОЯ МУЗИКА
# =========================================================

async def send_favorites_page(
    message,
    user_id,
    page=0,
):
    try:
        favorites = await asyncio.to_thread(
            db_get_favorites,
            user_id,
        )

    except Exception as error:
        print("Database read error:", error)

        await message.reply_text(
            "😕 Не вдалося відкрити «Моя музика»."
        )
        return

    total = len(favorites)

    if total == 0:
        await message.reply_text(
            "❤️ У «Моя музика» поки порожньо.\n\n"
            "Знайди пісню та натисни "
            "«❤️ Зберегти».",
            reply_markup=MAIN_KEYBOARD,
        )
        return

    total_pages = (
        total + FAVORITES_PER_PAGE - 1
    ) // FAVORITES_PER_PAGE

    page = max(
        0,
        min(page, total_pages - 1),
    )

    start_index = page * FAVORITES_PER_PAGE
    end_index = start_index + FAVORITES_PER_PAGE

    page_tracks = favorites[
        start_index:end_index
    ]

    await message.reply_text(
        f"❤️ Моя музика\n\n"
        f"🎵 Збережено: {total}\n"
        f"📄 Сторінка {page + 1} із {total_pages}"
    )

    for offset, track in enumerate(
        page_tracks,
        start=1,
    ):
        await send_track_card(
            message,
            track,
            index=start_index + offset,
            favorite_mode=True,
        )

    rows = []

    navigation = []

    if page > 0:
        navigation.append(
            InlineKeyboardButton(
                "⬅️ Назад",
                callback_data=f"favpage:{page - 1}",
            )
        )

    if page < total_pages - 1:
        navigation.append(
            InlineKeyboardButton(
                "Далі ➡️",
                callback_data=f"favpage:{page + 1}",
            )
        )

    if navigation:
        rows.append(navigation)

    rows.append(
        [
            InlineKeyboardButton(
                "🔀 Випадковий трек",
                callback_data="random_favorite",
            )
        ]
    )

    rows.append(
        [
            InlineKeyboardButton(
                "🔍 Пошук у моїй музиці",
                callback_data="search_favorites",
            )
        ]
    )

    rows.append(
        [
            InlineKeyboardButton(
                "📂 Мої плейлисти",
                callback_data="playlists",
            )
        ]
    )

    rows.append(
        [
            InlineKeyboardButton(
                "🗑 Очистити обране",
                callback_data="clear_favorites",
            )
        ]
    )

    await message.reply_text(
        "🎧 Керування «Моя музика»",
        reply_markup=InlineKeyboardMarkup(rows),
    )


async def show_favorites(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    clear_modes(context)

    await send_favorites_page(
        update.message,
        update.effective_user.id,
        page=0,
    )


async def search_my_music(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    search_text,
):
    user_id = update.effective_user.id

    try:
        results = await asyncio.to_thread(
            db_search_favorites,
            user_id,
            search_text,
        )

    except Exception as error:
        print("Favorite search error:", error)

        await update.message.reply_text(
            "😕 Помилка пошуку в «Моя музика»."
        )
        return

    if not results:
        await update.message.reply_text(
            f"🔍 У «Моя музика» нічого не знайдено "
            f"за запитом:\n\n{search_text}",
            reply_markup=MAIN_KEYBOARD,
        )
        return

    await update.message.reply_text(
        f"🔍 Знайдено: {len(results)} 👇"
    )

    for index, track in enumerate(
        results,
        start=1,
    ):
        await send_track_card(
            update.message,
            track,
            index=index,
            favorite_mode=True,
        )


# =========================================================
# 📂 ПЛЕЙЛИСТИ
# =========================================================

async def send_playlists(message, user_id):
    try:
        playlists = await asyncio.to_thread(
            db_get_playlists,
            user_id,
        )

    except Exception as error:
        print("Playlists error:", error)

        await message.reply_text(
            "😕 Не вдалося відкрити плейлисти."
        )
        return

    rows = []

    for playlist in playlists:
        rows.append(
            [
                InlineKeyboardButton(
                    (
                        f"🎵 {playlist['name']} "
                        f"({playlist['count']})"
                    ),
                    callback_data=(
                        f"plopen:{playlist['id']}"
                    ),
                )
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                "➕ Створити плейлист",
                callback_data="plcreate",
            )
        ]
    )

    if playlists:
        text = (
            "📂 Мої плейлисти\n\n"
            "Обери плейлист 👇"
        )
    else:
        text = (
            "📂 Мої плейлисти\n\n"
            "Плейлистів поки немає.\n"
            "Створи перший 👇"
        )

    await message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(rows),
    )


async def send_playlist(
    message,
    user_id,
    playlist_id,
):
    playlist = await asyncio.to_thread(
        db_get_playlist,
        user_id,
        playlist_id,
    )

    if not playlist:
        await message.reply_text(
            "😕 Плейлист не знайдено."
        )
        return

    tracks = await asyncio.to_thread(
        db_get_playlist_tracks,
        user_id,
        playlist_id,
    )

    await message.reply_text(
        f"📂 {playlist['name']}\n\n"
        f"🎵 Треків: {len(tracks)}"
    )

    if tracks:
        for index, track in enumerate(
            tracks,
            start=1,
        ):
            await send_track_card(
                message,
                track,
                index=index,
                playlist_id=playlist_id,
            )
    else:
        await message.reply_text(
            "Тут поки немає треків 🎵"
        )

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "⬅️ До плейлистів",
                    callback_data="playlists",
                )
            ],
            [
                InlineKeyboardButton(
                    "🗑 Видалити плейлист",
                    callback_data=(
                        f"pldelete:{playlist_id}"
                    ),
                )
            ],
        ]
    )

    await message.reply_text(
        "⚙️ Керування плейлистом",
        reply_markup=keyboard,
    )


def get_track_for_playlist(
    context,
    video_id,
):
    tracks = context.user_data.get(
        "search_tracks",
        {},
    )

    return tracks.get(video_id)


# =========================================================
# CALLBACK
# =========================================================

async def button_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id

    # ❤️ SAVE

    if data.startswith("save:"):
        video_id = data.split(":", 1)[1]

        track = get_track_for_playlist(
            context,
            video_id,
        )

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

        except Exception as error:
            print("Save error:", error)

            await query.answer(
                "Помилка збереження 😕",
                show_alert=True,
            )

        return

    # 🗑 FAVORITE

    if data.startswith("remove:"):
        video_id = data.split(":", 1)[1]

        try:
            await asyncio.to_thread(
                db_remove_favorite,
                user_id,
                video_id,
            )

            await query.answer("🗑 Видалено")

            try:
                await query.message.delete()
            except Exception:
                pass

        except Exception as error:
            print("Remove error:", error)

            await query.answer(
                "Не вдалося видалити 😕",
                show_alert=True,
            )

        return

    # FAVORITE PAGE

    if data.startswith("favpage:"):
        page = int(
            data.split(":", 1)[1]
        )

        await query.answer()

        await send_favorites_page(
            query.message,
            user_id,
            page,
        )
        return

    # RANDOM

    if data == "random_favorite":
        await query.answer()

        favorites = await asyncio.to_thread(
            db_get_favorites,
            user_id,
        )

        if not favorites:
            await query.message.reply_text(
                "❤️ У «Моя музика» порожньо."
            )
            return

        track = random.choice(favorites)

        # Зберігаємо для кнопки "До плейлиста"
        context.user_data.setdefault(
            "search_tracks",
            {},
        )[track["id"]] = track

        await query.message.reply_text(
            "🔀 Твій випадковий трек 👇"
        )

        await send_track_card(
            query.message,
            track,
            favorite_mode=True,
        )
        return

    # SEARCH FAVORITES

    if data == "search_favorites":
        await query.answer()

        clear_modes(context)

        context.user_data[
            "favorite_search_mode"
        ] = True

        await query.message.reply_text(
            "🔍 Напиши назву треку "
            "або виконавця 👇"
        )
        return

    # CLEAR FAVORITES

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
            print("Clear error:", error)

            await query.answer(
                "Помилка бази даних 😕",
                show_alert=True,
            )

        return

    # =====================================================
    # 📂 PLAYLISTS
    # =====================================================

    if data == "playlists":
        await query.answer()

        await send_playlists(
            query.message,
            user_id,
        )
        return

    # CREATE

    if data == "plcreate":
        await query.answer()

        clear_modes(context)

        context.user_data[
            "playlist_create_mode"
        ] = True

        await query.message.reply_text(
            "➕ Новий плейлист\n\n"
            "Напиши назву плейлиста 👇\n\n"
            "Наприклад: В авто"
        )
        return

    # OPEN

    if data.startswith("plopen:"):
        playlist_id = int(
            data.split(":", 1)[1]
        )

        await query.answer()

        await send_playlist(
            query.message,
            user_id,
            playlist_id,
        )
        return

    # CHOOSE PLAYLIST FOR TRACK

    if data.startswith("plchoose:"):
        video_id = data.split(":", 1)[1]

        track = get_track_for_playlist(
            context,
            video_id,
        )

        # Якщо картка з "Моя музика",
        # шукаємо трек у базі favorites
        if not track:
            favorites = await asyncio.to_thread(
                db_get_favorites,
                user_id,
            )

            for favorite in favorites:
                if favorite["id"] == video_id:
                    track = favorite
                    break

        if not track:
            await query.answer(
                "Відкрий трек ще раз 🎵",
                show_alert=True,
            )
            return

        context.user_data[
            "playlist_track"
        ] = track

        playlists = await asyncio.to_thread(
            db_get_playlists,
            user_id,
        )

        await query.answer()

        if not playlists:
            await query.message.reply_text(
                "📂 У тебе ще немає плейлистів.\n\n"
                "Спочатку створи плейлист.",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "➕ Створити плейлист",
                                callback_data="plcreate",
                            )
                        ]
                    ]
                ),
            )
            return

        rows = []

        for playlist in playlists:
            rows.append(
                [
                    InlineKeyboardButton(
                        f"📂 {playlist['name']}",
                        callback_data=(
                            f"pladd:{playlist['id']}"
                        ),
                    )
                ]
            )

        await query.message.reply_text(
            "➕ В який плейлист додати трек?",
            reply_markup=InlineKeyboardMarkup(rows),
        )
        return

    # ADD TRACK

    if data.startswith("pladd:"):
        playlist_id = int(
            data.split(":", 1)[1]
        )

        track = context.user_data.get(
            "playlist_track"
        )

        if not track:
            await query.answer(
                "Вибери трек ще раз 🎵",
                show_alert=True,
            )
            return

        try:
            added = await asyncio.to_thread(
                db_add_track_to_playlist,
                user_id,
                playlist_id,
                track,
            )

            if added:
                await query.answer(
                    "🎵 Додано до плейлиста",
                    show_alert=True,
                )
            else:
                await query.answer(
                    "Трек уже є в цьому плейлисті",
                    show_alert=True,
                )

        except Exception as error:
            print("Playlist add error:", error)

            await query.answer(
                "Не вдалося додати 😕",
                show_alert=True,
            )

        return

    # REMOVE TRACK FROM PLAYLIST

    if data.startswith("plremove:"):
        parts = data.split(":", 2)

        playlist_id = int(parts[1])
        video_id = parts[2]

        try:
            await asyncio.to_thread(
                db_remove_playlist_track,
                user_id,
                playlist_id,
                video_id,
            )

            await query.answer(
                "🗑 Прибрано з плейлиста"
            )

            try:
                await query.message.delete()
            except Exception:
                pass

        except Exception as error:
            print("Playlist remove error:", error)

            await query.answer(
                "Помилка видалення 😕",
                show_alert=True,
            )

        return

    # DELETE PLAYLIST

    if data.startswith("pldelete:"):
        playlist_id = int(
            data.split(":", 1)[1]
        )

        try:
            await asyncio.to_thread(
                db_delete_playlist,
                user_id,
                playlist_id,
            )

            await query.answer(
                "🗑 Плейлист видалено",
                show_alert=True,
            )

            await query.message.reply_text(
                "📂 Плейлист видалено.",
                reply_markup=MAIN_KEYBOARD,
            )

        except Exception as error:
            print("Playlist delete error:", error)

            await query.answer(
                "Не вдалося видалити 😕",
                show_alert=True,
            )

        return

    await query.answer()


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
# TEXT
# =========================================================

async def handle_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    text = update.message.text.strip()
    user_id = update.effective_user.id

    # Створення плейлиста
    if context.user_data.get(
        "playlist_create_mode"
    ):
        context.user_data[
            "playlist_create_mode"
        ] = False

        name = text.strip()

        if len(name) < 1:
            await update.message.reply_text(
                "Напиши назву плейлиста."
            )
            return

        if len(name) > 50:
            await update.message.reply_text(
                "Назва занадто довга.\n"
                "Максимум 50 символів."
            )
            return

        try:
            created = await asyncio.to_thread(
                db_create_playlist,
                user_id,
                name,
            )

            if created:
                await update.message.reply_text(
                    f"✅ Плейлист «{name}» створено!",
                    reply_markup=MAIN_KEYBOARD,
                )
            else:
                await update.message.reply_text(
                    f"📂 Плейлист «{name}» вже існує.",
                    reply_markup=MAIN_KEYBOARD,
                )

        except Exception as error:
            print("Create playlist error:", error)

            await update.message.reply_text(
                "😕 Не вдалося створити плейлист."
            )

        return

    # Пошук у favorites
    if context.user_data.get(
        "favorite_search_mode"
    ):
        context.user_data[
            "favorite_search_mode"
        ] = False

        await search_my_music(
            update,
            context,
            text,
        )
        return

    # MAIN
    if text in (
        "🏠 Головне меню",
        "⬅️ Назад",
    ):
        clear_modes(context)

        await update.message.reply_text(
            "🎵 WAVE | Головне меню",
            reply_markup=MAIN_KEYBOARD,
        )
        return

    if text == "❤️ Моя музика":
        await show_favorites(
            update,
            context,
        )
        return

    if text == "📂 Мої плейлисти":
        clear_modes(context)

        await send_playlists(
            update.message,
            user_id,
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
            "Надішли боту свій MP3 або M4A файл.\n\n"
            "Telegram покаже вбудований плеєр ▶️",
            reply_markup=MAIN_KEYBOARD,
        )
        return

    if text == "🇺🇦 Українська музика":
        await update.message.reply_text(
            "🇺🇦 Українська музика\n\n"
            "Обери жанр 👇",
            reply_markup=UKRAINIAN_KEYBOARD,
        )
        return

    if text == "🚗 В авто":
        await update.message.reply_text(
            "🚗 Музика в авто\n\n"
            "Обери настрій 👇",
            reply_markup=CAR_KEYBOARD,
        )
        return

    if text == "🏋️ Для спорту":
        await update.message.reply_text(
            "🏋️ Музика для спорту\n\n"
            "Обери режим 👇",
            reply_markup=SPORT_KEYBOARD,
        )
        return

    if text == "🎉 Для вечірки":
        await update.message.reply_text(
            "🎉 Музика для вечірки\n\n"
            "Обери стиль 👇",
            reply_markup=PARTY_KEYBOARD,
        )
        return

    if text == "😴 Для сну":
        await update.message.reply_text(
            "😴 Музика для сну\n\n"
            "Обери 👇",
            reply_markup=SLEEP_KEYBOARD,
        )
        return

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
