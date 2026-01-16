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


TRACKS_MATRIX = {
    "m": {  # ذكر
        "grp_1_3": {
            "m13_t1": {"title": "حفظ منظومة |أحسن الأخلاق|", "options": {}},
        },
        "grp_4_6": {
            "m46_t1": {"title": "حفظ الأربعين النووية (3 مستويات)", "options": {
                "o1":"حفظ 15 حديث", "o2":"حفظ 30 حديث", "o3":"حفظ 42 حديث"
            }},
            "m46_t2": {"title": "مشروع على كتاب |لأنك الله|", "options": {
                "o1":"المسار الصوتي", "o2":"المسار الكتابي", "o3":"المسار المرئي", "o4":"مسار التصميم"}},
            "m46_t3": {"title": "حفظ منظومة |أحسن الأخلاق|", "options": {}},
        },
        "grp_7_9": {
            "m79_t1": {"title": "حفظ الأربعين النووية", "options": {
                "o1":"حفظ 20 حديث", "o2":"حفظ 42 حديث"}},
            "m79_t2": {"title": "مشروع على كتاب |الحرب على الكسل|", "options": {
                "o1":"المسار الصوتي", "o2":"المسار الكتابي", "o3":"المسار المرئي", "o4":"مسار التصميم"}},
            "m79_t3": {"title": "حفظ منظومة |الأرجوزة الصغيرة في مهمات السيرة|", "options": {}},
        },
    },
    "f": {  # أنثى
        "grp_1_3": {
            "f13_t1": {"title": "حفظ منظومة |أحسن الأخلاق|", "options": {}},
        },
        "grp_4_6": {
            "f46_t1": {"title": "حفظ الأربعين النووية(3 مستويات)", "options": {
                "o1":"حفظ 15 حديث", "o2":"حفظ 30 حديث", "o3":"حفظ 42 حديث"
            }},
            "f46_t2": {"title": "مشروع على كتاب |لأنك الله|", "options": {
                "o1":"المسار الصوتي", "o2":"المسار الكتابي", "o3":"المسار المرئي", "o4":"مسار التصميم"}},
            "f46_t3": {"title": "حفظ منظومة |أحسن الأخلاق|", "options": {}},
        },
        "grp_7_9": {
            "f79_t1": {"title": "حفظ الأربعين النووية", "options": {
                "o1":"حفظ 20 حديث", "o2":"حفظ 42 حديث"}},
            "f79_t2": {"title": "مشروع على كتاب |الحرب على الكسل|", "options": {
                "o1":"المسار الصوتي", "o2":"المسار الكتابي", "o3":"المسار المرئي", "o4":"مسار التصميم"}},
            "f79_t3": {"title": "حفظ منظومة |الأرجوزة الصغيرة في مهمات السيرة|", "options": {}},
        },
    },
}

# ===================================

NAME, USER, GENDER, GRADE, TRACK, OPTION, CONFIRM = range(7)


SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SPREADSHEET_ID = "1di3hHm23biLNOuM8dMmn9Bv_oS0VVsRWfuNh-_XlgZs"
WORKSHEET_NAME = "Sheet1"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDS_FILE = os.getenv("CREDS_FILE")
if not CREDS_FILE:
    local = os.path.join(BASE_DIR, "gcp_service_account.json")
    CREDS_FILE = local if os.path.exists(local) else "/etc/secrets/gcp_service_account.json"


def _append_row_blocking(values: list[str]):
    creds = Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPES)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SPREADSHEET_ID)
    ws = sh.worksheet(WORKSHEET_NAME)
    ws.append_row(values)

async def append_row_async(values: list[str]):
    await asyncio.to_thread(_append_row_blocking, values)

GENDERS = {
    "m": "ذكر",
    "f": "أنثى",
}

def gender_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("ذكر", callback_data="gender:m")],
        [InlineKeyboardButton("أنثى", callback_data="gender:f")],
        [InlineKeyboardButton("إلغاء", callback_data="cancel")],
    ])

GRADES = {
    "g1":"الصف الأول","g2":"الصف الثاني","g3":"الصف الثالث",
    "g4":"الصف الرابع","g5":"الصف الخامس","g6":"الصف السادس",
    "g7":"الصف السابع","g8":"الصف الثامن","g9":"الصف التاسع",
}

def grades_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(GRADES["g1"], callback_data="grade:g1"),
            InlineKeyboardButton(GRADES["g2"], callback_data="grade:g2"),
            InlineKeyboardButton(GRADES["g3"], callback_data="grade:g3")],
        [InlineKeyboardButton(GRADES["g4"], callback_data="grade:g4"),
            InlineKeyboardButton(GRADES["g5"], callback_data="grade:g5"),
            InlineKeyboardButton(GRADES["g6"], callback_data="grade:g6")],
        [InlineKeyboardButton(GRADES["g7"], callback_data="grade:g7"),
            InlineKeyboardButton(GRADES["g8"], callback_data="grade:g8"),
            InlineKeyboardButton(GRADES["g9"], callback_data="grade:g9")],
        [InlineKeyboardButton("إلغاء", callback_data="cancel")],
    ])

GRADE_TO_GROUP = {
    "g1":"grp_1_3","g2":"grp_1_3","g3":"grp_1_3",
    "g4":"grp_4_6","g5":"grp_4_6","g6":"grp_4_6",
    "g7":"grp_7_9","g8":"grp_7_9","g9":"grp_7_9",
}

def get_tracks_for_user(context: ContextTypes.DEFAULT_TYPE) -> dict:
    gender_key = context.user_data.get("gender_key")   # "m" / "f"
    grade_key  = context.user_data.get("grade_key")    # "g1".."g9"
    group_key  = GRADE_TO_GROUP.get(grade_key)
    return TRACKS_MATRIX.get(gender_key, {}).get(group_key, {})

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
            gender TEXT,
            grade TEXT,
            track_key TEXT NOT NULL,
            track_title TEXT NOT NULL,
            option_key TEXT,
            option_title TEXT,
            created_at TEXT NOT NULL
        )
        """
    )

    cur.execute("PRAGMA table_info(registrations)")
    cols = {row[1] for row in cur.fetchall()}
    if "grade" not in cols:
        cur.execute("ALTER TABLE registrations ADD COLUMN grade TEXT")
    if "gender" not in cols:
        cur.execute("ALTER TABLE registrations ADD COLUMN gender TEXT")

    conn.commit()
    conn.close()



def insert_registration(
    user_id: int,
    username: str | None,
    full_name: str,
    gender: str,
    grade: str,
    track_key: str,
    track_title: str,
    option_key: str | None,
    option_title: str | None,
) -> int:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO registrations (
            tg_user_id, tg_username, full_name, gender, grade,
            track_key, track_title, option_key, option_title, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            username,
            full_name,
            gender,
            grade,
            track_key,
            track_title,
            option_key,
            option_title,
            datetime.utcnow().isoformat(),
        ),
    )
    reg_id = cur.lastrowid
    conn.commit()
    conn.close()
    return reg_id


def get_registration(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, full_name, gender, grade, track_title, option_title, created_at
        FROM registrations
        WHERE tg_user_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (user_id,),
    )
    row = cur.fetchone()
    conn.close()
    return row


def tracks_keyboard_for(context):
    tracks = get_tracks_for_user(context)
    rows = [[InlineKeyboardButton(v["title"], callback_data=f"track:{k}")] for k, v in tracks.items()]
    rows.append([InlineKeyboardButton("إلغاء", callback_data="cancel")])
    return InlineKeyboardMarkup(rows)

def options_keyboard(track_key: str, context):
    tracks = get_tracks_for_user(context)
    opts = tracks[track_key]["options"]
    rows = [[InlineKeyboardButton(title, callback_data=f"opt:{track_key}:{ok}")] for ok, title in opts.items()]
    rows.append([InlineKeyboardButton("رجوع للمسابقات", callback_data="back_to_tracks")])
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
    await update.message.reply_text("هل أنت ذكر أم أنثى؟", reply_markup=gender_keyboard())
    return GENDER

async def gender_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "cancel":
        await q.edit_message_text("تم الإلغاء.")
        return ConversationHandler.END

    if not q.data.startswith("gender:"):
        return GENDER

    gender_key = q.data.split("gender:", 1)[1]
    if gender_key not in GENDERS:
        await q.edit_message_text("اختيار غير صحيح. اختر:", reply_markup=gender_keyboard())
        return GENDER

    context.user_data["gender_key"] = gender_key
    context.user_data["gender"] = GENDERS[gender_key]

    await q.edit_message_text("ما هو صفّك؟", reply_markup=grades_keyboard())
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

    context.user_data["grade_key"] = grade_key
    context.user_data["grade"] = GRADES[grade_key]

    await q.edit_message_text("اختر المسابقة:", reply_markup=tracks_keyboard_for(context))
    return TRACK

async def track_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.data == "cancel":
        await q.edit_message_text("تم الإلغاء.")
        return ConversationHandler.END

    if not q.data.startswith("track:"):
        return TRACK

    tracks = get_tracks_for_user(context)

    track_key = q.data.split("track:", 1)[1]
    if track_key not in tracks:
        await q.edit_message_text("اختيار غير صحيح. اختر:", reply_markup=tracks_keyboard_for(context))
        return TRACK

    context.user_data["track_key"] = track_key

    # إذا المسار فيه خيارات → نعرض submenu
    if tracks[track_key]["options"]:
        await q.edit_message_text("اختر أحد الخيارات:", reply_markup=options_keyboard(track_key, context))
        return OPTION

    return await show_summary(q, context)


async def option_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.data == "cancel":
        await q.edit_message_text("تم الإلغاء.")
        return ConversationHandler.END

    tracks = get_tracks_for_user(context)
    if q.data == "back_to_tracks":
        await q.edit_message_text("اختر المسابقة:", reply_markup=tracks_keyboard_for(context))
        return TRACK

    if not q.data.startswith("opt:"):
        return OPTION

    _, track_key, opt_key = q.data.split(":", 2)
    if track_key not in tracks or opt_key not in tracks[track_key]["options"]:
        await q.edit_message_text("خيار غير صحيح. اختر:", reply_markup=options_keyboard(track_key, context))
        return OPTION

    context.user_data["track_key"] = track_key
    context.user_data["option_key"] = opt_key
    return await show_summary(q, context)


async def show_summary(q, context: ContextTypes.DEFAULT_TYPE):
    tracks = get_tracks_for_user(context)
    full_name = context.user_data.get("full_name")
    gender = context.user_data.get("gender","")
    grade  = context.user_data.get("grade","")
    track_key = context.user_data.get("track_key")
    option_key = context.user_data.get("option_key")
    track_title = tracks[track_key]["title"]
    option_title = tracks[track_key]["options"].get(option_key) if option_key else None


    txt = f"راجع معلوماتك:\n\n👤 الاسم: {full_name}\n⚧ الجنس: {gender}\n🏫 الصف: {grade}\n🏆 المسابقة: {track_title}"
    if option_title:
        txt += f"\n🎯 المستوى/الخيار: {option_title}"
    txt += "\n\nتأكيد التسجيل؟"

    await q.edit_message_text(txt, reply_markup=confirm_keyboard())
    return CONFIRM


async def confirm_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.data == "cancel":
        await q.edit_message_text("تم الإلغاء.")
        return ConversationHandler.END

    if q.data == "edit":
        context.user_data.pop("track_key", None)
        context.user_data.pop("option_key", None)
        await q.edit_message_text("اختر المسابقة:", reply_markup=tracks_keyboard_for(context))
        return TRACK

    if q.data != "confirm":
        return CONFIRM

    user = q.from_user
    full_name = context.user_data["full_name"]
    gender = context.user_data.get("gender", "")
    grade = context.user_data.get("grade", "")
    track_key = context.user_data["track_key"]
    option_key = context.user_data.get("option_key")

    tracks = get_tracks_for_user(context)
    track_title = tracks[track_key]["title"]
    option_title = tracks[track_key]["options"].get(option_key) if option_key else ""

    reg_id = insert_registration(
        user_id=user.id,
        username=user.username,
        full_name=full_name,
        gender=gender,
        grade=grade,
        track_key=track_key,
        track_title=track_title,
        option_key=option_key,
        option_title=option_title,
    )
    tracks = get_tracks_for_user(context)
    track_title = tracks[track_key]["title"]
    option_title = tracks[track_key]["options"].get(option_key) if option_key else ""
    grade = context.user_data.get("grade", "")
    
    await append_row_async([
    str(reg_id),  
    user.username or "",
    full_name,
    gender,
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
    
    reg_id, full_name, gender, grade, track_title, option_title, created_at = row
    msg = f"آخر تسجيل لك:\n\n🆔 {reg_id}\n👤 {full_name}\n⚧ {gender}\n🏫 {grade}\n🏆 {track_title}"
    if option_title:
        msg += f"\n🎯 {option_title}"
    msg += f"\n🕒 {created_at} (UTC)"
    await update.message.reply_text(msg)

async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("تم الإلغاء.")
    return ConversationHandler.END

conv = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        NAME:   [MessageHandler(filters.TEXT & ~filters.COMMAND, name_step)],
        GENDER: [CallbackQueryHandler(gender_step)],
        GRADE:  [CallbackQueryHandler(grade_step)],
        TRACK:  [CallbackQueryHandler(track_step)],
        OPTION: [CallbackQueryHandler(option_step)],
        CONFIRM:[CallbackQueryHandler(confirm_step)],
    },
    fallbacks=[CommandHandler("cancel", cancel_cmd)],
    allow_reentry=True,
)

def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("Missing BOT_TOKEN env var")

    init_db()
    app = ApplicationBuilder().token(token).build()

    # handlers...
    app.add_handler(conv)
    app.add_handler(CommandHandler("my", my_registration))
    
    render_url = os.getenv("RENDER_EXTERNAL_URL")  # Render بيعطيك رابط الخدمة تلقائياً
    if render_url:
        port = int(os.getenv("PORT", "10000"))  # لازم تسمع على PORT في Render
        render_url = render_url.rstrip("/")

        # سرّ للحماية (Telegram رح يبعت هالسر بالهيدر)
        secret_token = os.getenv("WEBHOOK_SECRET_TOKEN", "CHANGE_ME")

        # مسار webhook (خليه صعب التخمين)
        webhook_path = os.getenv("WEBHOOK_PATH", "tg-webhook")

        webhook_url = f"{render_url}/{webhook_path}"

        log.info("Bot webhook URL: %s", webhook_url)

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
