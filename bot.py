import os
from urllib.parse import quote_plus

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN = os.environ["BOT_TOKEN"]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎵 WAVE | Твоя музика 🇺🇦\n\n"
        "Напиши назву пісні, виконавця або просто свій настрій.\n\n"
        "Наприклад:\n"
        "🚗 музика в авто\n"
        "🏋️ музика для спорту\n"
        "😴 музика для сну\n"
        "🎉 музика для вечірки\n"
        "🎤 The Weeknd Blinding Lights"
    )


async def search_music(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()

    youtube = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
    spotify = f"https://open.spotify.com/search/{quote_plus(query)}"
    soundcloud = f"https://soundcloud.com/search?q={quote_plus(query)}"

    keyboard = [
        [InlineKeyboardButton("▶️ YouTube", url=youtube)],
        [InlineKeyboardButton("🟢 Spotify", url=spotify)],
        [InlineKeyboardButton("☁️ SoundCloud", url=soundcloud)],
    ]

    await update.message.reply_text(
        f"🎧 Знайшов варіанти для:\n\n🔎 {query}\n\n"
        "Обери, де шукати музику 👇",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_music))

    print("WAVE bot started")
    app.run_polling()


if __name__ == "__main__":
    main()
