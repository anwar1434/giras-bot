# cSpell:disable

import os
import sqlite3
import logging
from datetime import datetime
import asyncio
import gspread
from google.oauth2.service_account import Credentials

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("contest-bot")
DB_PATH = "registrations.sqlite3"

os.getenv("BOT_TOKEN")


TRACKS = {
    "t1": {"title": "حفظ الأربعين النووية (يوجد 3 مستويات)", "options": {"o1": "حفظ 15 حديث", "o2": "حفظ 30 حديث", "o3": "حفظ 42 حديث"}},
    "t2": {"title": "مشروع على كتاب |لأنك الله|", "options": {}},
    "t3": {"title": "حفظ منظومة أحسن الأخلاق", "options": {}},
}

# ===================================

NAME, USER, GRADE, TRACK, OPTION, CONFIRM = range(6)


SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SPREADSHEET_ID = "1di3hHm23biLNOuM8dMmn9Bv_oS0VVsRWfuNh-_XlgZs"
WORKSHEET_NAME = "Sheet1"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDS_FILE = os.getenv("CREDS_FILE", "/etc/secrets/gcp_service_account.json")

def _append_row_blocking(values: list[str]):
    creds = Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPES)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SPREADSHEET_ID)
    ws = sh.worksheet(WORKSHEET_NAME)
    ws.append_row(values)

async def append_row_async(values: list[str]):
    await asyncio.to_thread(_append_row_blocking, values)

GRADES = {
    "g4": "الصف الرابع",
    "g5": "الصف الخامس",
    "g6": "الصف السادس",
}

def grades_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(GRADES["g4"], callback_data="grade:g4")],
        [InlineKeyboardButton(GRADES["g5"], callback_data="grade:g5")],
        [InlineKeyboardButton(GRADES["g6"], callback_data="grade:g6")],
        [InlineKeyboardButton("إلغاء", callback_data="cancel")],
    ])

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_user_id INTEGER NOT NULL,
            tg_username TEXT,
            full_name TEXT NOT NULL,
            grade TEXT,
            track_key TEXT NOT NULL,
            track_title TEXT NOT NULL,
            option_key TEXT,
            option_title TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(tg_user_id)
        )
        """
    )
    cur.execute("PRAGMA table_info(registrations)")
    cols = {row[1] for row in cur.fetchall()}  # row[1] = column name
    if "grade" not in cols:
        cur.execute("ALTER TABLE registrations ADD COLUMN grade TEXT")
    conn.commit()
    conn.close()


def upsert_registration(user_id: int, username: str | None, full_name: str, grade: str, track_key: str, option_key: str | None):
    track_title = TRACKS[track_key]["title"]
    option_title = None
    if option_key:
        option_title = TRACKS[track_key]["options"].get(option_key)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO registrations (
            tg_user_id, tg_username, full_name, grade, track_key, track_title,
            option_key, option_title, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(tg_user_id) DO UPDATE SET
            tg_username=excluded.tg_username,
            full_name=excluded.full_name,
            grade=excluded.grade,
            track_key=excluded.track_key,
            track_title=excluded.track_title,
            option_key=excluded.option_key,
            option_title=excluded.option_title,
            created_at=excluded.created_at
        """,
        (
            user_id,
            username,
            full_name,
            grade,
            track_key,
            track_title,
            option_key,
            option_title,
            datetime.utcnow().isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def get_registration(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT full_name, track_title, option_title, created_at
        FROM registrations WHERE tg_user_id = ?
        """,
        (user_id,),
    )
    row = cur.fetchone()
    conn.close()
    return row


def tracks_keyboard():
    rows = []
    for k, v in TRACKS.items():
        rows.append([InlineKeyboardButton(v["title"], callback_data=f"track:{k}")])
    rows.append([InlineKeyboardButton("إلغاء", callback_data="cancel")])
    return InlineKeyboardMarkup(rows)


def options_keyboard(track_key: str):
    opts = TRACKS[track_key]["options"]
    rows = [[InlineKeyboardButton(title, callback_data=f"opt:{track_key}:{ok}")]
            for ok, title in opts.items()]
    rows.append([InlineKeyboardButton("رجوع للمسارات", callback_data="back_to_tracks")])
    rows.append([InlineKeyboardButton("إلغاء", callback_data="cancel")])
    return InlineKeyboardMarkup(rows)


def confirm_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ تأكيد التسجيل", callback_data="confirm")],
        [InlineKeyboardButton("🔁 تعديل", callback_data="edit")],
        [InlineKeyboardButton("إلغاء", callback_data="cancel")],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("حياك الله عزيزي الطالب! اكتب اسمك الكامل للتسجيل في المسابقة:")
    return NAME


async def name_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    full_name = (update.message.text or "").strip()
    if len(full_name) < 3:
        await update.message.reply_text("الاسم قصير جداً. اكتب اسمك الكامل مرة ثانية:")
        return NAME

    context.user_data["full_name"] = full_name
    await update.message.reply_text("ما هو صفّك؟", reply_markup=grades_keyboard())
    return GRADE

async def grade_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.data == "cancel":
        await q.edit_message_text("تم الإلغاء.")
        return ConversationHandler.END

    if not q.data.startswith("grade:"):
        return GRADE

    grade_key = q.data.split("grade:", 1)[1]
    if grade_key not in GRADES:
        await q.edit_message_text("اختيار غير صحيح. اختر الصف:", reply_markup=grades_keyboard())
        return GRADE

    context.user_data["grade"] = GRADES[grade_key]
    await q.edit_message_text("اختر المسار:", reply_markup=tracks_keyboard())
    return TRACK

async def track_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.data == "cancel":
        await q.edit_message_text("تم الإلغاء.")
        return ConversationHandler.END

    if not q.data.startswith("track:"):
        return TRACK

    track_key = q.data.split("track:", 1)[1]
    if track_key not in TRACKS:
        await q.edit_message_text("مسار غير صحيح. اختر مرة ثانية:", reply_markup=tracks_keyboard())
        return TRACK

    context.user_data["track_key"] = track_key

    # إذا المسار فيه خيارات → نعرض submenu
    if TRACKS[track_key]["options"]:
        await q.edit_message_text("اختر أحد الخيارات:", reply_markup=options_keyboard(track_key))
        return OPTION

    # إذا ما فيه خيارات → نروح للتأكيد مباشرة
    return await show_summary(q, context)


async def option_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.data == "cancel":
        await q.edit_message_text("تم الإلغاء.")
        return ConversationHandler.END

    if q.data == "back_to_tracks":
        await q.edit_message_text("اختر المسار:", reply_markup=tracks_keyboard())
        return TRACK

    if not q.data.startswith("opt:"):
        return OPTION

    _, track_key, opt_key = q.data.split(":", 2)
    if track_key not in TRACKS or opt_key not in TRACKS[track_key]["options"]:
        await q.edit_message_text("خيار غير صحيح. اختر مرة ثانية:", reply_markup=options_keyboard(track_key))
        return OPTION

    context.user_data["track_key"] = track_key
    context.user_data["option_key"] = opt_key
    return await show_summary(q, context)


async def show_summary(q, context: ContextTypes.DEFAULT_TYPE):
    full_name = context.user_data.get("full_name")
    grade = context.user_data.get("grade", "")
    track_key = context.user_data.get("track_key")
    option_key = context.user_data.get("option_key")
    track_title = TRACKS[track_key]["title"]
    option_title = TRACKS[track_key]["options"].get(option_key) if option_key else None

    txt = f"راجع معلوماتك:\n\n👤 الاسم: {full_name}\n🏫 الصف: {grade}\n🧭 المسار: {track_title}"
    if option_title:
        txt += f"\n🎯 الخيار: {option_title}"
    txt += "\n\nتأكيد التسجيل؟"

    await q.edit_message_text(txt, reply_markup=confirm_keyboard())
    return CONFIRM

def get_registration_id(tg_user_id: int) -> int:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id FROM registrations WHERE tg_user_id = ?", (tg_user_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else 0

async def confirm_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.data == "cancel":
        await q.edit_message_text("تم الإلغاء.")
        return ConversationHandler.END

    if q.data == "edit":
        # رجّع للمسارات لتعديل سريع
        context.user_data.pop("track_key", None)
        context.user_data.pop("option_key", None)
        await q.edit_message_text("اختر المسار:", reply_markup=tracks_keyboard())
        return TRACK

    if q.data != "confirm":
        return CONFIRM

    user = q.from_user
    full_name = context.user_data["full_name"]
    grade = context.user_data.get("grade", "")
    track_key = context.user_data["track_key"]
    option_key = context.user_data.get("option_key")

    upsert_registration(
        user_id=user.id,
        username=user.username,
        full_name=full_name,
        grade=grade,
        track_key=track_key,
        option_key=option_key,
    )
    reg_id = get_registration_id(user.id)
    track_title = TRACKS[track_key]["title"]
    option_title = TRACKS[track_key]["options"].get(option_key) if option_key else ""
    grade = context.user_data.get("grade", "")
    
    await append_row_async([
    str(reg_id),  
    user.username or "",
    full_name,
    grade,
    track_title,
    option_title, 
    ])
    await q.edit_message_text("✅ تم تسجيلك بنجاح! شكراً لك.")
    return ConversationHandler.END

async def my_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    row = get_registration(update.effective_user.id)
    if not row:
        await update.message.reply_text("ما عندك تسجيل حالياً. اكتب /start للتسجيل.")
        return
    
    full_name, track_title, option_title, created_at = row
    msg = f"تسجيلك الحالي:\n\n👤 {full_name}\n🧭 {track_title}"
    if option_title:
        msg += f"\n🎯 {option_title}"
    msg += f"\n🕒 {created_at} (UTC)"
    await update.message.reply_text(msg)

async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("تم الإلغاء.")
    return ConversationHandler.END


def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("Missing BOT_TOKEN env var")

    init_db()

    app = ApplicationBuilder().token(token).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, name_step)],
            GRADE: [CallbackQueryHandler(grade_step)],
            TRACK: [CallbackQueryHandler(track_step)],
            OPTION: [CallbackQueryHandler(option_step)],
            CONFIRM: [CallbackQueryHandler(confirm_step)],
        },
        fallbacks=[CommandHandler("cancel", cancel_cmd)],
        allow_reentry=True,
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("my", my_registration))
    log.info("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
