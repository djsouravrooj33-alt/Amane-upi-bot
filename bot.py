import os
import asyncio
import requests
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ========= ENV =========
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "8145485145"))
ALLOWED_GROUP = int(os.getenv("ALLOWED_GROUP", "-1003296016362"))

API_URL = "https://upi-api.onrender.com/api/upi"

# ========= FLASK =========
app = Flask(__name__)

# ========= TELEGRAM APP (Webhook only) =========
tg_app = (
    Application.builder()
    .token(BOT_TOKEN)
    .updater(None)   # 🔥 VERY IMPORTANT
    .build()
)

# ========= AUTH =========
def is_authorized(update: Update) -> bool:
    user = update.effective_user
    chat = update.effective_chat

    if user and user.id == OWNER_ID:
        return True
    if chat and chat.id == ALLOWED_GROUP:
        return True
    return False

# ========= COMMANDS =========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return
    await update.message.reply_text(
        "🤖 UPI Info Bot Active\n\n"
        "Use:\n/upi 8707448099@ybl"
    )

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
            f"🏢 Branch: {data.get('branch','N/A')}\n"
            f"📍 City: {data.get('city','N/A')}\n"
            f"🗺 State: {data.get('state','N/A')}"
        )

        await update.message.reply_text(msg)

    except Exception:
        await update.message.reply_text("⚠️ API Error")

# ========= HANDLERS =========
tg_app.add_handler(CommandHandler("start", start))
tg_app.add_handler(CommandHandler("upi", upi))

# ========= WEBHOOK =========
@app.route("/", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), tg_app.bot)
    tg_app.update_queue.put_nowait(update)
    return "OK"

@app.route("/", methods=["GET"])
def health():
    return "Bot running"

# ========= STARTUP =========
async def startup():
    await tg_app.bot.delete_webhook(drop_pending_updates=True)

    webhook_url = os.environ.get("RENDER_EXTERNAL_URL")
    if webhook_url:
        await tg_app.bot.set_webhook(webhook_url)

# ========= MAIN =========
if __name__ == "__main__":
    asyncio.run(startup())
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))