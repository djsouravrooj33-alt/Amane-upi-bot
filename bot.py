import os
import asyncio
import requests
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import logging
import sys

# ========= লগিং সেটআপ =========
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# ========= ENV =========
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN not set!")

try:
    OWNER_ID = int(os.getenv("OWNER_ID", "8145485145"))
    ALLOWED_GROUP = int(os.getenv("ALLOWED_GROUP", "-1003296016362"))
except ValueError as e:
    logger.error(f"❌ Invalid ID format: {e}")
    OWNER_ID = 8145485145
    ALLOWED_GROUP = -1003296016362

API_URL = "https://upi-api.onrender.com/api/upi"

# ========= FLASK =========
app = Flask(__name__)

# ========= GLOBAL FLAGS (multiple workers issue fix) =========
BOT_STARTED = False
tg_app = None

# ========= TELEGRAM APP INIT =========
def init_bot_app():
    """Initialize bot application"""
    global tg_app
    try:
        tg_app = (
            Application.builder()
            .token(BOT_TOKEN)
            .updater(None)
            .build()
        )
        
        tg_app.add_handler(CommandHandler("start", start))
        tg_app.add_handler(CommandHandler("upi", upi))
        
        logger.info("✅ Bot application initialized successfully")
        return tg_app
    except Exception as e:
        logger.error(f"❌ Failed to initialize bot: {e}")
        return None

# ========= AUTH =========
def is_authorized(update: Update) -> bool:
    if not update:
        return False
        
    user = update.effective_user
    chat = update.effective_chat

    if user and user.id == OWNER_ID:
        return True
    if chat and chat.id == ALLOWED_GROUP:
        return True
    
    if user:
        logger.warning(f"⚠️ Unauthorized access from user {user.id}")
    return False

# ========= COMMANDS =========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not is_authorized(update):
            await update.message.reply_text("⛔ Unauthorized")
            return

        await update.message.reply_text(
            "🤖 *UPI Info Bot Active*\n\n"
            "Use: `/upi 8707448099@ybl`",
            parse_mode='Markdown'
        )
        logger.info(f"✅ Start command from user {update.effective_user.id}")
    except Exception as e:
        logger.error(f"❌ Start command error: {e}")

async def upi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not is_authorized(update):
            await update.message.reply_text("⛔ Unauthorized")
            return

        if not context.args:
            await update.message.reply_text("❌ Usage: /upi upi_id")
            return

        upi_id = context.args[0]
        
        if '@' not in upi_id:
            await update.message.reply_text("❌ Invalid UPI ID format")
            return

        logger.info(f"🔍 Fetching UPI info for: {upi_id}")

        # API call (production-এ aiohttp use করলে better)
        try:
            r = requests.get(API_URL, params={"upi": upi_id}, timeout=10)
            r.raise_for_status()
            data = r.json()
        except requests.Timeout:
            await update.message.reply_text("⏱️ API timeout")
            return
        except requests.RequestException as e:
            logger.error(f"❌ API request failed: {e}")
            await update.message.reply_text("⚠️ API unavailable")
            return
        except ValueError as e:
            logger.error(f"❌ JSON decode error: {e}")
            await update.message.reply_text("⚠️ Invalid API response")
            return

        if not data.get("success"):
            await update.message.reply_text("❌ UPI ID not found")
            return

        msg = (
            f"✅ *UPI Information*\n\n"
            f"🔎 *UPI:* `{data.get('upi', 'N/A')}`\n"
            f"🏦 *Bank:* {data.get('bank', 'N/A')}\n"
            f"🏧 *IFSC:* `{data.get('ifsc', 'N/A')}`\n"
            f"🏢 *Branch:* {data.get('branch', 'N/A')}\n"
            f"📍 *City:* {data.get('city', 'N/A')}\n"
            f"🗺 *State:* {data.get('state', 'N/A')}"
        )

        await update.message.reply_text(msg, parse_mode='Markdown')
        logger.info(f"✅ Success: {upi_id}")

    except Exception as e:
        logger.error(f"❌ UPI command error: {e}")
        await update.message.reply_text("⚠️ Internal error")

# ========= WEBHOOK (Content-Type fix) =========
@app.route("/webhook", methods=["POST"])
def webhook():
    if not tg_app:
        return "Bot not initialized", 500
    
    try:
        # 🔥 FIXED: Content-Type check now flexible
        content_type = request.headers.get("Content-Type", "")
        if "application/json" not in content_type:
            logger.warning(f"Invalid content type: {content_type}")
            return "Invalid content type", 400
        
        update = Update.de_json(request.get_json(force=True), tg_app.bot)
        tg_app.update_queue.put_nowait(update)
        return "OK"
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
        return "Error", 500

@app.route("/", methods=["GET"])
def health():
    return jsonify({
        "status": "running",
        "bot_initialized": tg_app is not None,
        "bot_started": BOT_STARTED,
        "owner_id": OWNER_ID,
        "allowed_group": ALLOWED_GROUP
    })

@app.route("/setwebhook", methods=["GET"])
def manual_webhook():
    webhook_url = os.environ.get("RENDER_EXTERNAL_URL")
    if not webhook_url:
        return "RENDER_EXTERNAL_URL not set", 400
    
    if not tg_app:
        return "Bot not initialized", 500
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        full_url = webhook_url.rstrip('/') + '/webhook'
        loop.run_until_complete(set_webhook(full_url))
        return f"✅ Webhook set to: {full_url}"
    except Exception as e:
        return f"❌ Error: {e}", 500
    finally:
        loop.close()

async def set_webhook(url):
    await tg_app.bot.set_webhook(url)
    logger.info(f"✅ Webhook set to {url}")

# ========= STARTUP =========
async def startup():
    global tg_app, BOT_STARTED
    
    try:
        # 🔥 FIXED: Skip if already started
        if BOT_STARTED:
            logger.info("⏭️ Bot already started, skipping...")
            return
            
        tg_app = init_bot_app()
        if not tg_app:
            return
        
        await tg_app.initialize()
        await tg_app.bot.delete_webhook(drop_pending_updates=True)
        
        webhook_url = os.environ.get("RENDER_EXTERNAL_URL")
        if webhook_url:
            full_url = webhook_url.rstrip('/') + '/webhook'
            await set_webhook(full_url)
            BOT_STARTED = True  # Mark as started
        else:
            logger.warning("⚠️ RENDER_EXTERNAL_URL not set")
            
    except Exception as e:
        logger.error(f"❌ Startup error: {e}")

def run_startup():
    """Run startup in event loop"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(startup())
    finally:
        loop.close()

# ========= gunicorn-safe initialization with duplicate prevention =========
@app.before_first_request
def initialize_on_first_request():
    """🔥 FIXED: Will run only once even with multiple workers"""
    global BOT_STARTED
    if BOT_STARTED:
        return
    
    logger.info("🚀 Initializing bot on first request (gunicorn mode)")
    run_startup()

# ========= লোকাল টেস্টিং-এর জন্য =========
if __name__ == "__main__":
    logger.info("🚀 Running in local development mode")
    run_startup()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)