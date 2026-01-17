# cSpell:disable
import os
import logging
from datetime import datetime
import asyncio

import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

load_dotenv()

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("replies-bot")

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "1di3hHm23biLNOuM8dMmn9Bv_oS0VVsRWfuNh-_XlgZs")
WORKSHEET_NAME = os.getenv("WORKSHEET_NAME", "المشاركات")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDS_FILE = os.getenv("CREDS_FILE")
if not CREDS_FILE:
    local = os.path.join(BASE_DIR, "gcp_service_account.json")
    CREDS_FILE = local if os.path.exists(local) else "/etc/secrets/gcp_service_account.json"

ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "-5193954757")  # ضع chat id للمسؤول هنا عبر env

def _append_row_blocking(values: list[str]) -> None:
    if not SPREADSHEET_ID:
        raise RuntimeError("Missing SPREADSHEET_ID env var")

    creds = Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPES)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SPREADSHEET_ID)
    ws = sh.worksheet(WORKSHEET_NAME)
    ws.append_row(values)

async def append_row_async(values: list[str]) -> None:
    await asyncio.to_thread(_append_row_blocking, values)

def _message_type(update: Update) -> str:
    m = update.effective_message
    if not m:
        return "unknown"
    if m.text:
        return "text"
    if m.photo:
        return "photo"
    if m.document:
        return "document"
    if m.voice:
        return "voice"
    if m.audio:
        return "audio"
    if m.video:
        return "video"
    if m.video_note:
        return "video_note"
    if m.sticker:
        return "sticker"
    if m.contact:
        return "contact"
    if m.location:
        return "location"
    return "other"

def _extract_content(update: Update) -> tuple[str, str]:
    m = update.effective_message
    if not m:
        return ("", "")

    if m.text:
        return (m.text, "")

    caption = m.caption or ""

    if m.photo:
        return (caption, m.photo[-1].file_id)

    if m.document:
        return (caption, m.document.file_id)
    if m.voice:
        return (caption, m.voice.file_id)
    if m.audio:
        return (caption, m.audio.file_id)
    if m.video:
        return (caption, m.video.file_id)
    if m.video_note:
        return (caption, m.video_note.file_id)
    if m.sticker:
        return (caption, m.sticker.file_id)

    return (caption, "")

def _clip(s: str, limit: int = 15000) -> str:
    s = s or ""
    return s if len(s) <= limit else (s[:limit] + "…")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["awaiting_name"] = True
    await update.message.reply_text("أهلاً! ما هو اسمك الكامل؟")

async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # يفيدك لتجيب ADMIN_CHAT_ID
    await update.message.reply_text(f"chat_id: {update.effective_chat.id}\nuser_id: {update.effective_user.id}")

async def handle_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    m = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    if not m or not user or not chat:
        return

    # 1) إذا لسه ما سجل الاسم: خذ الرسالة كنص اسم
    if context.user_data.get("awaiting_name") or not context.user_data.get("student_name"):
        if not m.text:
            await m.reply_text("لو سمحت ابعت اسمك كنص (مو ملف/صورة).")
            return

        student_name = (m.text or "").strip()
        if len(student_name) < 3:
            await m.reply_text("الاسم قصير. اكتب اسمك الكامل مرة ثانية:")
            return

        context.user_data["student_name"] = student_name
        context.user_data["awaiting_name"] = False
        await m.reply_text(f"تمام يا {student_name} ✅ الآن ابعت مشاركتك (نص/صورة/ملف/صوت).")
        return

    # 2) إذا الاسم موجود → اعتبر الرسالة مشاركة
    student_name = context.user_data.get("student_name", "")

    msg_type = _message_type(update)
    content, file_id = _extract_content(update)
    ts = datetime.utcnow().isoformat()

    # سجل بالشيت (أضفت عمود للاسم الذي أدخله المستخدم)
    row = [
        ts,                      # الوقت UTC
        str(user.id),            # user_id
        user.username or "",     # username
        user.full_name or "",    # اسم تيليغرام
        student_name,            # الاسم الذي أدخله المستخدم ✅
        msg_type,                # نوع الرسالة
        _clip(content),          # النص/الكابشن
        file_id or "",           # file_id للمرفقات
    ]

    try:
        await append_row_async(row)
    except Exception:
        log.exception("Failed to save to sheet")
        await m.reply_text("وصلتني مشاركتك ✅ بس صار خطأ بالتخزين على الشيت. بلغ الإدارة.")
        return

    # إرسال للمسؤول + فورورد الرسالة كما هي
    if ADMIN_CHAT_ID:
        try:
            admin_id = int(ADMIN_CHAT_ID)

            # رسالة ملخّص (مثل ما هي) + إضافة الاسم
            await context.bot.send_message(
                chat_id=admin_id,
                text=(
                    f"📩 مشاركة جديدة\n"
                    f"👤 {user.full_name} (@{user.username or '-'}) | ID: {user.id}\n"
                    f"🧾 الاسم المُدخل: {student_name}\n"   # ✅ الإضافة المطلوبة
                    f"🧾 النوع: {msg_type}\n"
                    f"🕒 {ts} UTC\n"
                    f"✍️ {(_clip(content, 2000) or '[بدون نص]')}"
                ),
            )

            # Forward للرسالة الأصلية (كما هي)
            await context.bot.forward_message(
                chat_id=admin_id,
                from_chat_id=chat.id,
                message_id=m.message_id,
            )
        except Exception as e:
            log.warning("Failed to notify admin: %s", e)

    await m.reply_text("تم الاستلام ✅")


def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("Missing BOT_TOKEN env var")

    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("id", get_id))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_reply))

    render_url = os.getenv("RENDER_EXTERNAL_URL")
    if render_url:
        port = int(os.getenv("PORT", "10000"))
        render_url = render_url.rstrip("/")
        secret_token = os.getenv("WEBHOOK_SECRET_TOKEN", "CHANGE_ME")
        webhook_path = os.getenv("WEBHOOK_PATH", "replies-hook")
        webhook_url = f"{render_url}/{webhook_path}"

        log.info("Replies bot webhook URL: %s", webhook_url)

        app.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=webhook_path,
            webhook_url=webhook_url,
            secret_token=secret_token,
        )
    else:
        app.run_polling()

if __name__ == "__main__":
    main()
