import os
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ===== CONFIG =====
BOT_TOKEN = os.getenv("BOT_TOKEN")

OWNER_ID = 8145485145
GROUP_ID = -1003296016362

API_URL = "https://upi-api.onrender.com/api/upi"

# ===== AUTH CHECK =====
def is_authorized(update: Update):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    return user_id == OWNER_ID or chat_id == GROUP_ID

# ===== /start =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return
    await update.message.reply_text(
        "🤖 UPI Info Bot Active\n\n"
        "Use:\n/upi 8707448099@ybl"
    )

# ===== /upi =====
async def upi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return

    if not context.args:
        await update.message.reply_text("❌ Usage: /upi upi_id")
        return

    upi_id = context.args[0]

    try:
        r = requests.get(API_URL, params={"upi": upi_id}, timeout=10)
        data = r.json()

        if not data.get("success"):
            await update.message.reply_text("❌ Invalid or not found")
            return

        msg = (
            f"🔎 UPI: {data['upi']}\n"
            f"🏦 Bank: {data['bank']}\n"
            f"🏧 IFSC: {data['ifsc']}\n"
            f"🏢 Branch: {data['branch']}\n"
            f"📍 City: {data['city']}\n"
            f"🗺 State: {data['state']}"
        )

        await update.message.reply_text(msg)

    except Exception as e:
        await update.message.reply_text("⚠️ API Error")

# ===== MAIN =====
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("upi", upi))

    print("🤖 Bot running...")
    app.run_polling()
