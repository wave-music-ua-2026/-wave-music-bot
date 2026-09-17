import os
import asyncio
import random
from collections import Counter
from datetime import datetime
from urllib.parse import quote_plus

import yt_dlp
import psycopg

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

TOKEN = os.environ["BOT_TOKEN"]
DATABASE_URL = os.environ["DATABASE_URL"]

PER_PAGE = 5

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["🔎 Пошук музики", "❤️ Моя музика"],
        ["📂 Мої плейлисти", "🎯 Рекомендації"],
        ["🕘 Історія", "🔥 Популярне"],
        ["👤 Профіль", "⭐ Виконавці"],
        ["🚗 В авто", "🏋️ Для спорту"],
        ["😴 Для сну", "🎉 Для вечірки"],
        ["🇺🇦 Українська музика", "🆕 Новинки"],
        ["⚙️ Налаштування", "🎧 Як слухати в Telegram"],
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
# DATABASE
# =========================================================

def init_database():
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
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
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS playlists (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    name TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, name)
                );
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS playlist_tracks (
                    id SERIAL PRIMARY KEY,
                    playlist_id INTEGER NOT NULL
                        REFERENCES playlists(id) ON DELETE CASCADE,
                    video_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    artist TEXT,
                    duration INTEGER,
                    thumbnail TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(playlist_id, video_id)
                );
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS search_history (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    query TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_history_user
                ON search_history(user_id, created_at DESC);
            """)

        conn.commit()

    print("PostgreSQL ready")


def db_register_user(user_id, username, first_name):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO users (user_id, username, first_name)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id)
                DO UPDATE SET
                    username = EXCLUDED.username,
                    first_name = EXCLUDED.first_name;
            """, (user_id, username, first_name))
        conn.commit()


def db_add_history(user_id, search_text):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO search_history (user_id, query) VALUES (%s, %s);",
                (user_id, search_text),
            )
            # Не даємо історії одного користувача рости безмежно.
            cur.execute("""
                DELETE FROM search_history
                WHERE user_id = %s
                AND id NOT IN (
                    SELECT id FROM search_history
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                    LIMIT 100
                );
            """, (user_id, user_id))
        conn.commit()


def db_get_history(user_id, limit=10):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT query, created_at
                FROM search_history
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT %s;
            """, (user_id, limit))
            return cur.fetchall()


def db_clear_history(user_id):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM search_history WHERE user_id = %s;", (user_id,))
        conn.commit()


def db_popular_searches(limit=10):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT query, COUNT(*) AS uses
                FROM search_history
                GROUP BY query
                ORDER BY uses DESC, MAX(created_at) DESC
                LIMIT %s;
            """, (limit,))
            return cur.fetchall()


def db_add_favorite(user_id, track):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO favorites (
                    user_id, video_id, title, artist, duration, thumbnail
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id, video_id)
                DO NOTHING
                RETURNING id;
            """, (
                user_id, track["id"], track["title"], track["artist"],
                track.get("duration"), track.get("thumbnail")
            ))
            result = cur.fetchone()
        conn.commit()
    return result is not None


def db_get_favorite(user_id, video_id):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT video_id, title, artist, duration, thumbnail
                FROM favorites
                WHERE user_id = %s AND video_id = %s;
            """, (user_id, video_id))
            row = cur.fetchone()
    if not row:
        return None
    return {
        "id": row[0], "title": row[1], "artist": row[2],
        "duration": row[3], "thumbnail": row[4]
    }


def db_get_favorites(user_id):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT video_id, title, artist, duration, thumbnail
                FROM favorites
                WHERE user_id = %s
                ORDER BY created_at DESC;
            """, (user_id,))
            rows = cur.fetchall()
    return [
        {"id": r[0], "title": r[1], "artist": r[2], "duration": r[3], "thumbnail": r[4]}
        for r in rows
    ]


def db_search_favorites(user_id, text):
    value = f"%{text}%"
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT video_id, title, artist, duration, thumbnail
                FROM favorites
                WHERE user_id = %s
                  AND (title ILIKE %s OR artist ILIKE %s)
                ORDER BY created_at DESC;
            """, (user_id, value, value))
            rows = cur.fetchall()
    return [
        {"id": r[0], "title": r[1], "artist": r[2], "duration": r[3], "thumbnail": r[4]}
        for r in rows
    ]


def db_remove_favorite(user_id, video_id):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM favorites WHERE user_id = %s AND video_id = %s;",
                (user_id, video_id),
            )
        conn.commit()


def db_clear_favorites(user_id):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM favorites WHERE user_id = %s;", (user_id,))
        conn.commit()


def db_create_playlist(user_id, name):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO playlists (user_id, name)
                VALUES (%s, %s)
                ON CONFLICT (user_id, name)
                DO NOTHING
                RETURNING id;
            """, (user_id, name))
            result = cur.fetchone()
        conn.commit()
    return result is not None


def db_get_playlists(user_id):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT p.id, p.name, COUNT(pt.id)
                FROM playlists p
                LEFT JOIN playlist_tracks pt ON pt.playlist_id = p.id
                WHERE p.user_id = %s
                GROUP BY p.id, p.name, p.created_at
                ORDER BY p.created_at DESC;
            """, (user_id,))
            rows = cur.fetchall()
    return [{"id": r[0], "name": r[1], "count": r[2]} for r in rows]


def db_get_playlist(user_id, playlist_id):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name FROM playlists WHERE id = %s AND user_id = %s;",
                (playlist_id, user_id),
            )
            row = cur.fetchone()
    return {"id": row[0], "name": row[1]} if row else None


def db_get_playlist_tracks(user_id, playlist_id):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT pt.video_id, pt.title, pt.artist, pt.duration, pt.thumbnail
                FROM playlist_tracks pt
                JOIN playlists p ON p.id = pt.playlist_id
                WHERE pt.playlist_id = %s AND p.user_id = %s
                ORDER BY pt.created_at DESC;
            """, (playlist_id, user_id))
            rows = cur.fetchall()
    return [
        {"id": r[0], "title": r[1], "artist": r[2], "duration": r[3], "thumbnail": r[4]}
        for r in rows
    ]


def db_get_playlist_track(user_id, playlist_id, video_id):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT pt.video_id, pt.title, pt.artist, pt.duration, pt.thumbnail
                FROM playlist_tracks pt
                JOIN playlists p ON p.id = pt.playlist_id
                WHERE p.user_id = %s
                  AND pt.playlist_id = %s
                  AND pt.video_id = %s;
            """, (user_id, playlist_id, video_id))
            row = cur.fetchone()
    if not row:
        return None
    return {
        "id": row[0], "title": row[1], "artist": row[2],
        "duration": row[3], "thumbnail": row[4]
    }


def db_add_track_to_playlist(user_id, playlist_id, track):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM playlists WHERE id = %s AND user_id = %s;",
                (playlist_id, user_id),
            )
            if not cur.fetchone():
                return False

            cur.execute("""
                INSERT INTO playlist_tracks (
                    playlist_id, video_id, title, artist, duration, thumbnail
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (playlist_id, video_id)
                DO NOTHING
                RETURNING id;
            """, (
                playlist_id, track["id"], track["title"], track["artist"],
                track.get("duration"), track.get("thumbnail")
            ))
            result = cur.fetchone()
        conn.commit()
    return result is not None


def db_remove_playlist_track(user_id, playlist_id, video_id):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM playlist_tracks
                WHERE playlist_id = %s
                  AND video_id = %s
                  AND EXISTS (
                      SELECT 1 FROM playlists
                      WHERE id = %s AND user_id = %s
                  );
            """, (playlist_id, video_id, playlist_id, user_id))
        conn.commit()


def db_delete_playlist(user_id, playlist_id):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM playlists WHERE id = %s AND user_id = %s;",
                (playlist_id, user_id),
            )
        conn.commit()


def db_profile(user_id):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT username, first_name, joined_at
                FROM users WHERE user_id = %s;
            """, (user_id,))
            user = cur.fetchone()

            cur.execute("SELECT COUNT(*) FROM favorites WHERE user_id = %s;", (user_id,))
            favorites = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM playlists WHERE user_id = %s;", (user_id,))
            playlists = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM search_history WHERE user_id = %s;", (user_id,))
            searches = cur.fetchone()[0]

    return user, favorites, playlists, searches


def db_top_artists(user_id, limit=10):
    favorites = db_get_favorites(user_id)
    artists = [t["artist"] for t in favorites if t.get("artist")]
    return Counter(artists).most_common(limit)


def db_delete_user_data(user_id):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM playlist_tracks
                WHERE playlist_id IN (
                    SELECT id FROM playlists WHERE user_id = %s
                );
            """, (user_id,))
            cur.execute("DELETE FROM playlists WHERE user_id = %s;", (user_id,))
            cur.execute("DELETE FROM favorites WHERE user_id = %s;", (user_id,))
            cur.execute("DELETE FROM search_history WHERE user_id = %s;", (user_id,))
            cur.execute("DELETE FROM users WHERE user_id = %s;", (user_id,))
        conn.commit()


# =========================================================
# HELPERS
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
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def clean_text(text, max_length=500):
    text = str(text or "")
    return text[:max_length] + "..." if len(text) > max_length else text


def clear_modes(context):
    context.user_data.pop("favorite_search_mode", None)
    context.user_data.pop("playlist_create_mode", None)


async def register_current_user(update):
    user = update.effective_user
    if not user:
        return
    try:
        await asyncio.to_thread(
            db_register_user,
            user.id,
            user.username,
            user.first_name,
        )
    except Exception as error:
        print("Register user error:", error)


# =========================================================
# YOUTUBE
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
            result = ydl.extract_info(f"ytsearch{limit}:{search_text}", download=False)
            return result.get("entries", [])
    except Exception as error:
        print("YouTube search error:", error)
        return []


async def youtube_search(search_text, limit=5):
    return await asyncio.to_thread(youtube_search_sync, search_text, limit)


# =========================================================
# TRACK CARD
# =========================================================

async def send_track_card(message, item, index=None, favorite_mode=False, playlist_id=None):
    video_id = item.get("id")
    if not video_id:
        return

    title = clean_text(item.get("title") or "Без назви", 200)
    artist = clean_text(
        item.get("artist") or item.get("channel") or item.get("uploader") or "YouTube",
        100,
    )
    duration = item.get("duration")
    thumbnail = item.get("thumbnail") or f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

    youtube_url = f"https://www.youtube.com/watch?v={video_id}"
    service_query = f"{artist} {title}"
    spotify_url = "https://open.spotify.com/search/" + quote_plus(service_query)
    soundcloud_url = "https://soundcloud.com/search?q=" + quote_plus(service_query)

    number = f"{index}. " if index else ""
    caption = f"🎵 {number}{title}\n\n👤 {artist}\n⏱ {format_duration(duration)}"

    buttons = [
        [InlineKeyboardButton("▶️ YouTube", url=youtube_url)],
        [
            InlineKeyboardButton("🟢 Spotify", url=spotify_url),
            InlineKeyboardButton("☁️ SoundCloud", url=soundcloud_url),
        ],
    ]

    if playlist_id is not None:
        buttons.append([
            InlineKeyboardButton(
                "❤️ Зберегти",
                callback_data=f"plsave:{playlist_id}:{video_id}",
            )
        ])
        buttons.append([
            InlineKeyboardButton(
                "🗑 Прибрати з плейлиста",
                callback_data=f"plremove:{playlist_id}:{video_id}",
            )
        ])
    else:
        buttons.append([
            InlineKeyboardButton("➕ До плейлиста", callback_data=f"plchoose:{video_id}")
        ])
        if favorite_mode:
            buttons.append([
                InlineKeyboardButton("🗑 Видалити з обраного", callback_data=f"remove:{video_id}")
            ])
        else:
            buttons.append([
                InlineKeyboardButton("❤️ Зберегти", callback_data=f"save:{video_id}")
            ])

    keyboard = InlineKeyboardMarkup(buttons)

    try:
        await message.reply_photo(photo=thumbnail, caption=caption, reply_markup=keyboard)
    except Exception as error:
        print("Photo error:", error)
        await message.reply_text(caption, reply_markup=keyboard)


# =========================================================
# SEARCH
# =========================================================

async def send_results(update, context, search_text, save_history=True):
    await register_current_user(update)
    user_id = update.effective_user.id

    if save_history:
        try:
            await asyncio.to_thread(db_add_history, user_id, search_text)
        except Exception as error:
            print("History error:", error)

    status = await update.message.reply_text(f"🔎 Шукаю «{search_text}»...")
    results = await youtube_search(search_text, 5)

    try:
        await status.delete()
    except Exception:
        pass

    if not results:
        await update.message.reply_text(
            "😕 Нічого не знайшов.\n\nСпробуй написати назву трохи інакше."
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
            "artist": item.get("channel") or item.get("uploader") or "YouTube",
            "duration": item.get("duration"),
            "thumbnail": item.get("thumbnail") or f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
        }

    context.user_data["search_tracks"] = tracks

    await update.message.reply_text(
        f"🎧 Результати для:\n\n🔎 {search_text}\n\nЗнайшов {len(tracks)} варіантів 👇"
    )

    for index, item in enumerate(results, start=1):
        await send_track_card(update.message, item, index=index)


# =========================================================
# FAVORITES
# =========================================================

async def send_favorites_page(message, user_id, page=0):
    try:
        favorites = await asyncio.to_thread(db_get_favorites, user_id)
    except Exception as error:
        print("Favorites error:", error)
        await message.reply_text("😕 Не вдалося відкрити «Моя музика».")
        return

    total = len(favorites)
    if total == 0:
        await message.reply_text(
            "❤️ У «Моя музика» поки порожньо.\n\n"
            "Знайди пісню та натисни «❤️ Зберегти».",
            reply_markup=MAIN_KEYBOARD,
        )
        return

    total_pages = (total + PER_PAGE - 1) // PER_PAGE
    page = max(0, min(page, total_pages - 1))
    start = page * PER_PAGE
    page_tracks = favorites[start:start + PER_PAGE]

    await message.reply_text(
        f"❤️ Моя музика\n\n🎵 Збережено: {total}\n📄 Сторінка {page + 1} із {total_pages}"
    )

    for offset, track in enumerate(page_tracks, start=1):
        await send_track_card(
            message, track, index=start + offset, favorite_mode=True
        )

    rows = []
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"favpage:{page - 1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("Далі ➡️", callback_data=f"favpage:{page + 1}"))
    if nav:
        rows.append(nav)

    rows.extend([
        [InlineKeyboardButton("🔀 Випадковий трек", callback_data="random_favorite")],
        [InlineKeyboardButton("🔍 Пошук у моїй музиці", callback_data="search_favorites")],
        [InlineKeyboardButton("📂 Мої плейлисти", callback_data="playlists")],
        [InlineKeyboardButton("🗑 Очистити обране", callback_data="clear_favorites")],
    ])

    await message.reply_text(
        "🎧 Керування «Моя музика»",
        reply_markup=InlineKeyboardMarkup(rows),
    )


async def search_my_music(update, context, text):
    user_id = update.effective_user.id
    try:
        results = await asyncio.to_thread(db_search_favorites, user_id, text)
    except Exception as error:
        print("Favorite search error:", error)
        await update.message.reply_text("😕 Помилка пошуку в «Моя музика».")
        return

    if not results:
        await update.message.reply_text(
            f"🔍 У «Моя музика» нічого не знайдено за запитом:\n\n{text}",
            reply_markup=MAIN_KEYBOARD,
        )
        return

    await update.message.reply_text(f"🔍 Знайдено: {len(results)} 👇")
    for index, track in enumerate(results, start=1):
        await send_track_card(update.message, track, index=index, favorite_mode=True)


# =========================================================
# PLAYLISTS
# =========================================================

async def send_playlists(message, user_id):
    try:
        playlists = await asyncio.to_thread(db_get_playlists, user_id)
    except Exception as error:
        print("Playlists error:", error)
        await message.reply_text("😕 Не вдалося відкрити плейлисти.")
        return

    rows = [
        [
            InlineKeyboardButton(
                f"🎵 {p['name']} ({p['count']})",
                callback_data=f"plopen:{p['id']}",
            )
        ]
        for p in playlists
    ]
    rows.append([InlineKeyboardButton("➕ Створити плейлист", callback_data="plcreate")])

    text = (
        "📂 Мої плейлисти\n\nОбери плейлист 👇"
        if playlists
        else "📂 Мої плейлисти\n\nПлейлистів поки немає.\nСтвори перший 👇"
    )
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(rows))


async def send_playlist(message, user_id, playlist_id):
    playlist = await asyncio.to_thread(db_get_playlist, user_id, playlist_id)
    if not playlist:
        await message.reply_text("😕 Плейлист не знайдено.")
        return

    tracks = await asyncio.to_thread(db_get_playlist_tracks, user_id, playlist_id)
    await message.reply_text(f"📂 {playlist['name']}\n\n🎵 Треків: {len(tracks)}")

    if tracks:
        for index, track in enumerate(tracks, start=1):
            await send_track_card(
                message, track, index=index, playlist_id=playlist_id
            )
    else:
        await message.reply_text("Тут поки немає треків 🎵")

    await message.reply_text(
        "⚙️ Керування плейлистом",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ До плейлистів", callback_data="playlists")],
            [InlineKeyboardButton("🗑 Видалити плейлист", callback_data=f"pldeleteask:{playlist_id}")],
        ]),
    )


# =========================================================
# PROFILE / DISCOVERY
# =========================================================

async def show_profile(update):
    await register_current_user(update)
    user_id = update.effective_user.id
    try:
        user, favorites, playlists, searches = await asyncio.to_thread(db_profile, user_id)
    except Exception as error:
        print("Profile error:", error)
        await update.message.reply_text("😕 Не вдалося відкрити профіль.")
        return

    if user:
        username, first_name, joined_at = user
        name = first_name or username or "Користувач"
        joined = joined_at.strftime("%d.%m.%Y") if joined_at else "—"
    else:
        name, joined = "Користувач", "—"

    await update.message.reply_text(
        f"👤 Профіль WAVE\n\n"
        f"🙂 {name}\n"
        f"📅 З WAVE: {joined}\n\n"
        f"❤️ Збережених треків: {favorites}\n"
        f"📂 Плейлистів: {playlists}\n"
        f"🔎 Пошуків: {searches}",
        reply_markup=MAIN_KEYBOARD,
    )


async def show_history(update):
    user_id = update.effective_user.id
    rows = await asyncio.to_thread(db_get_history, user_id, 10)
    if not rows:
        await update.message.reply_text("🕘 Історія пошуку поки порожня.", reply_markup=MAIN_KEYBOARD)
        return

    text = "🕘 Останні пошуки\n\n"
    for i, (query, _) in enumerate(rows, start=1):
        text += f"{i}. {query}\n"

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🗑 Очистити історію", callback_data="history_clear_ask")]
        ]),
    )


async def show_popular(update):
    rows = await asyncio.to_thread(db_popular_searches, 10)
    if not rows:
        await update.message.reply_text(
            "🔥 Популярних пошуків поки немає.",
            reply_markup=MAIN_KEYBOARD,
        )
        return

    text = "🔥 Популярні пошуки WAVE\n\n"
    for i, (query, uses) in enumerate(rows, start=1):
        text += f"{i}. {query} — {uses}\n"
    await update.message.reply_text(text, reply_markup=MAIN_KEYBOARD)


async def show_artists(update):
    user_id = update.effective_user.id
    artists = await asyncio.to_thread(db_top_artists, user_id, 10)
    if not artists:
        await update.message.reply_text(
            "⭐ Ще недостатньо збереженої музики.\n\n"
            "Додай кілька треків у ❤️ «Моя музика».",
            reply_markup=MAIN_KEYBOARD,
        )
        return

    text = "⭐ Твої улюблені виконавці\n\n"
    for i, (artist, count) in enumerate(artists, start=1):
        text += f"{i}. {artist} — {count} трек(и)\n"
    await update.message.reply_text(text, reply_markup=MAIN_KEYBOARD)


async def recommendations(update, context):
    user_id = update.effective_user.id
    artists = await asyncio.to_thread(db_top_artists, user_id, 5)
    favorites = await asyncio.to_thread(db_get_favorites, user_id)

    if artists:
        artist_names = " ".join(a[0] for a in artists[:3])
        query = f"music similar to {artist_names}"
    elif favorites:
        query = f"music similar to {favorites[0]['artist']} {favorites[0]['title']}"
    else:
        query = "popular music hits"

    await send_results(update, context, query, save_history=False)


# =========================================================
# START
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clear_modes(context)
    await register_current_user(update)
    await update.message.reply_text(
        "🎵 WAVE | Твоя музика 🇺🇦\n\n"
        "🔎 Шукай музику\n"
        "❤️ Зберігай улюблене\n"
        "📂 Створюй плейлисти\n"
        "🎯 Отримуй рекомендації\n"
        "📊 Дивись свою статистику\n\n"
        "🎧 Можеш також надіслати свій MP3/M4A.",
        reply_markup=MAIN_KEYBOARD,
    )


# =========================================================
# CALLBACKS
# =========================================================

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id

    if data.startswith("save:"):
        video_id = data.split(":", 1)[1]
        track = context.user_data.get("search_tracks", {}).get(video_id)
        if not track:
            track = await asyncio.to_thread(db_get_favorite, user_id, video_id)
        if not track:
            await query.answer("Зроби пошук треку ще раз 🎵", show_alert=True)
            return

        try:
            added = await asyncio.to_thread(db_add_favorite, user_id, track)
            await query.answer(
                "❤️ Додано в «Моя музика»" if added else "Цей трек уже збережений ❤️",
                show_alert=True,
            )
        except Exception as error:
            print("Save error:", error)
            await query.answer("Помилка збереження 😕", show_alert=True)
        return

    if data.startswith("plsave:"):
        parts = data.split(":", 2)
        playlist_id = int(parts[1])
        video_id = parts[2]
        track = await asyncio.to_thread(
            db_get_playlist_track, user_id, playlist_id, video_id
        )
        if not track:
            await query.answer("Трек не знайдено 😕", show_alert=True)
            return
        added = await asyncio.to_thread(db_add_favorite, user_id, track)
        await query.answer(
            "❤️ Додано в «Моя музика»" if added else "Цей трек уже збережений ❤️",
            show_alert=True,
        )
        return

    if data.startswith("remove:"):
        video_id = data.split(":", 1)[1]
        await asyncio.to_thread(db_remove_favorite, user_id, video_id)
        await query.answer("🗑 Видалено")
        try:
            await query.message.delete()
        except Exception:
            pass
        return

    if data.startswith("favpage:"):
        page = int(data.split(":", 1)[1])
        await query.answer()
        await send_favorites_page(query.message, user_id, page)
        return

    if data == "random_favorite":
        favorites = await asyncio.to_thread(db_get_favorites, user_id)
        await query.answer()
        if not favorites:
            await query.message.reply_text("❤️ У «Моя музика» порожньо.")
            return
        track = random.choice(favorites)
        context.user_data.setdefault("search_tracks", {})[track["id"]] = track
        await query.message.reply_text("🔀 Твій випадковий трек 👇")
        await send_track_card(query.message, track, favorite_mode=True)
        return

    if data == "search_favorites":
        clear_modes(context)
        context.user_data["favorite_search_mode"] = True
        await query.answer()
        await query.message.reply_text("🔍 Напиши назву треку або виконавця 👇")
        return

    if data == "clear_favorites":
        await asyncio.to_thread(db_clear_favorites, user_id)
        await query.answer("🗑 Обране очищено", show_alert=True)
        await query.message.reply_text("❤️ У «Моя музика» тепер порожньо.", reply_markup=MAIN_KEYBOARD)
        return

    if data == "playlists":
        await query.answer()
        await send_playlists(query.message, user_id)
        return

    if data == "plcreate":
        clear_modes(context)
        context.user_data["playlist_create_mode"] = True
        await query.answer()
        await query.message.reply_text(
            "➕ Новий плейлист\n\nНапиши назву плейлиста 👇\n\nНаприклад: В авто"
        )
        return

    if data.startswith("plopen:"):
        playlist_id = int(data.split(":", 1)[1])
        await query.answer()
        await send_playlist(query.message, user_id, playlist_id)
        return

    if data.startswith("plchoose:"):
        video_id = data.split(":", 1)[1]
        track = context.user_data.get("search_tracks", {}).get(video_id)
        if not track:
            track = await asyncio.to_thread(db_get_favorite, user_id, video_id)
        if not track:
            await query.answer("Відкрий трек ще раз 🎵", show_alert=True)
            return

        context.user_data["playlist_track"] = track
        playlists = await asyncio.to_thread(db_get_playlists, user_id)
        await query.answer()

        if not playlists:
            await query.message.reply_text(
                "📂 У тебе ще немає плейлистів.\n\nСпочатку створи плейлист.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ Створити плейлист", callback_data="plcreate")]
                ]),
            )
            return

        rows = [
            [InlineKeyboardButton(f"📂 {p['name']}", callback_data=f"pladd:{p['id']}")]
            for p in playlists
        ]
        await query.message.reply_text(
            "➕ В який плейлист додати трек?",
            reply_markup=InlineKeyboardMarkup(rows),
        )
        return

    if data.startswith("pladd:"):
        playlist_id = int(data.split(":", 1)[1])
        track = context.user_data.get("playlist_track")
        if not track:
            await query.answer("Вибери трек ще раз 🎵", show_alert=True)
            return

        added = await asyncio.to_thread(
            db_add_track_to_playlist, user_id, playlist_id, track
        )
        await query.answer(
            "🎵 Додано до плейлиста" if added else "Трек уже є в цьому плейлисті",
            show_alert=True,
        )
        return

    if data.startswith("plremove:"):
        parts = data.split(":", 2)
        playlist_id = int(parts[1])
        video_id = parts[2]
        await asyncio.to_thread(
            db_remove_playlist_track, user_id, playlist_id, video_id
        )
        await query.answer("🗑 Прибрано з плейлиста")
        try:
            await query.message.delete()
        except Exception:
            pass
        return

    if data.startswith("pldeleteask:"):
        playlist_id = int(data.split(":", 1)[1])
        await query.answer()
        await query.message.reply_text(
            "⚠️ Видалити цей плейлист?\n\nТреки з ❤️ «Моя музика» не видаляться.",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Так", callback_data=f"pldelete:{playlist_id}"),
                    InlineKeyboardButton("❌ Ні", callback_data=f"plopen:{playlist_id}"),
                ]
            ]),
        )
        return

    if data.startswith("pldelete:"):
        playlist_id = int(data.split(":", 1)[1])
        await asyncio.to_thread(db_delete_playlist, user_id, playlist_id)
        await query.answer("🗑 Плейлист видалено", show_alert=True)
        await send_playlists(query.message, user_id)
        return

    if data == "history_clear_ask":
        await query.answer()
        await query.message.reply_text(
            "⚠️ Очистити всю історію пошуку?",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Так", callback_data="history_clear"),
                    InlineKeyboardButton("❌ Ні", callback_data="cancel"),
                ]
            ]),
        )
        return

    if data == "history_clear":
        await asyncio.to_thread(db_clear_history, user_id)
        await query.answer("🗑 Історію очищено", show_alert=True)
        await query.message.reply_text("🕘 Історія пошуку порожня.", reply_markup=MAIN_KEYBOARD)
        return

    if data == "delete_data_ask":
        await query.answer()
        await query.message.reply_text(
            "⚠️ Видалити ВСІ твої дані WAVE?\n\n"
            "Буде видалено ❤️ обране, 📂 плейлисти та 🕘 історію.",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🗑 Так, видалити", callback_data="delete_data"),
                    InlineKeyboardButton("❌ Ні", callback_data="cancel"),
                ]
            ]),
        )
        return

    if data == "delete_data":
        await asyncio.to_thread(db_delete_user_data, user_id)
        context.user_data.clear()
        await query.answer("Дані видалено", show_alert=True)
        await query.message.reply_text(
            "🗑 Твої дані WAVE видалено.\n\n/start — почати заново.",
            reply_markup=MAIN_KEYBOARD,
        )
        return

    if data == "cancel":
        await query.answer("Скасовано")
        return

    await query.answer()


# =========================================================
# AUDIO
# =========================================================

async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await register_current_user(update)
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
        if mime.startswith("audio/") or filename.lower().endswith(
            (".mp3", ".m4a", ".aac", ".wav", ".ogg")
        ):
            file = await document.get_file()
            await update.message.reply_audio(
                audio=file.file_id,
                caption="🎧 Слухай прямо в Telegram ▶️",
            )


# =========================================================
# TEXT
# =========================================================

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await register_current_user(update)
    text = update.message.text.strip()
    user_id = update.effective_user.id

    # Навігація має пріоритет над режимами вводу.
    if text in ("🏠 Головне меню", "⬅️ Назад"):
        clear_modes(context)
        await update.message.reply_text("🎵 WAVE | Головне меню", reply_markup=MAIN_KEYBOARD)
        return

    if context.user_data.get("playlist_create_mode"):
        context.user_data["playlist_create_mode"] = False
        name = text.strip()
        if not name or len(name) > 50:
            await update.message.reply_text(
                "Назва має містити від 1 до 50 символів.",
                reply_markup=MAIN_KEYBOARD,
            )
            return
        created = await asyncio.to_thread(db_create_playlist, user_id, name)
        await update.message.reply_text(
            f"✅ Плейлист «{name}» створено!" if created
            else f"📂 Плейлист «{name}» вже існує.",
            reply_markup=MAIN_KEYBOARD,
        )
        return

    if context.user_data.get("favorite_search_mode"):
        context.user_data["favorite_search_mode"] = False
        await search_my_music(update, context, text)
        return

    if text == "❤️ Моя музика":
        clear_modes(context)
        await send_favorites_page(update.message, user_id, 0)
        return

    if text == "📂 Мої плейлисти":
        clear_modes(context)
        await send_playlists(update.message, user_id)
        return

    if text == "🎯 Рекомендації":
        await recommendations(update, context)
        return

    if text == "👤 Профіль":
        await show_profile(update)
        return

    if text == "🕘 Історія":
        await show_history(update)
        return

    if text == "🔥 Популярне":
        await show_popular(update)
        return

    if text == "⭐ Виконавці":
        await show_artists(update)
        return

    if text == "🆕 Новинки":
        await send_results(update, context, "new music releases 2026", save_history=False)
        return

    if text == "⚙️ Налаштування":
        await update.message.reply_text(
            "⚙️ Налаштування WAVE\n\n"
            "Тут можна керувати своїми даними.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🗑 Очистити історію", callback_data="history_clear_ask")],
                [InlineKeyboardButton("⚠️ Видалити всі мої дані", callback_data="delete_data_ask")],
            ]),
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
            "🇺🇦 Українська музика\n\nОбери жанр 👇",
            reply_markup=UKRAINIAN_KEYBOARD,
        )
        return

    if text == "🚗 В авто":
        await update.message.reply_text("🚗 Музика в авто\n\nОбери настрій 👇", reply_markup=CAR_KEYBOARD)
        return

    if text == "🏋️ Для спорту":
        await update.message.reply_text("🏋️ Музика для спорту\n\nОбери режим 👇", reply_markup=SPORT_KEYBOARD)
        return

    if text == "🎉 Для вечірки":
        await update.message.reply_text("🎉 Музика для вечірки\n\nОбери стиль 👇", reply_markup=PARTY_KEYBOARD)
        return

    if text == "😴 Для сну":
        await update.message.reply_text("😴 Музика для сну\n\nОбери 👇", reply_markup=SLEEP_KEYBOARD)
        return

    categories = {
        "🔥 Українські хіти": "українські музичні хіти",
        "🎤 Український поп": "українська поп музика",
        "🎸 Український рок": "український рок",
        "🎧 Український реп": "український реп",
        "💙 Українська класика": "кращі українські класичні пісні",
        "🔥 Хіти в авто": "best driving music hits",
        "🌙 Нічна поїздка": "night drive music",
        "⚡ Енергійна музика": "energetic driving music",
        "😌 Спокійна дорога": "chill driving music",
        "🔥 Workout Hits": "workout music hits",
        "🏃 Для бігу": "running workout music",
        "🏋️ Для залу": "gym workout music",
        "⚡ Максимум енергії": "high energy workout music",
        "🔥 Party Hits": "party music hits",
        "💃 Dance": "dance music hits",
        "🎧 EDM": "EDM music hits",
        "🪩 Disco": "disco dance hits",
        "🌙 Sleep Music": "relaxing sleep music",
        "🌧 Звуки дощу": "rain sounds sleep",
        "🎹 Piano": "relaxing piano music",
        "🌊 Relax": "relaxing chill music",
    }

    if text in categories:
        await send_results(update, context, categories[text], save_history=False)
        return

    await send_results(update, context, text, save_history=True)


# =========================================================
# MAIN
# =========================================================

def main():
    print("Connecting to PostgreSQL...")
    init_database()
    print("Starting WAVE bot...")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.AUDIO | filters.Document.AUDIO, handle_audio))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("🎵 WAVE bot started")
    app.run_polling()


if __name__ == "__main__":
    main()
