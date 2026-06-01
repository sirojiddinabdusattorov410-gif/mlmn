import logging
import os
import re
import json
import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters, ConversationHandler
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8391861533:AAEPc3FG8ubqW4M-sC-K8aomi5Vh0j6-mJo")

TEACHER_PASSWORDS = {}
VERIFIED_TEACHERS = set()
ADMIN_PASSWORD = "admin123"

CHOOSING_ROLE       = 5

TEACHER_MENU        = 10
TEACHER_TEST_NAME   = 11
TEACHER_ANSWERS     = 12
TEACHER_TEST_START_TIME = 13
TEACHER_TEST_END_TIME   = 14

STUDENT_MENU        = 20
WAITING_ANSWERS     = 21

ENTER_PASSWORD      = 30
SET_NEW_PASSWORD    = 31
CONFIRM_PASSWORD    = 32
CHANGE_PASSWORD_OLD = 33
CHANGE_PASSWORD_NEW = 34
CHANGE_PASSWORD_CNF = 35

TEACHER_SCHEDULE_MENU   = 100
TEACHER_SCHEDULE_NAME   = 101
TEACHER_SCHEDULE_DAY    = 102
TEACHER_SCHEDULE_START  = 103
TEACHER_SCHEDULE_END    = 104
TEACHER_SCHEDULE_SELECT = 105
TEACHER_SCHEDULE_REMOVE = 106
TEACHER_SCHEDULE_DELETE = 107

STUDENT_SCHEDULE_VIEW   = 200
STUDENT_SCHEDULE_JOIN   = 201

DATA_DIR       = os.path.dirname(os.path.abspath(__file__))
TESTS_FILE     = os.path.join(DATA_DIR, "tests.json")
PASSWORDS_FILE = os.path.join(DATA_DIR, "passwords.json")
SCHEDULE_FILE  = os.path.join(DATA_DIR, "schedule.json")
USER_ROLES_FILE = os.path.join(DATA_DIR, "user_roles.json")

TESTS = {}
test_counter = [0]
SCHEDULE = {}
USER_ROLES = {}

WEEKDAYS = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]

def load_data():
    global TESTS, test_counter, TEACHER_PASSWORDS, SCHEDULE
    if os.path.exists(TESTS_FILE):
        try:
            with open(TESTS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                TESTS = saved.get("tests", {})
                test_counter[0] = saved.get("counter", 0)
            logger.info(f"{len(TESTS)} ta test yuklandi.")
        except Exception as e:
            logger.error(f"Testlarni yuklashda xato: {e}")

    if os.path.exists(PASSWORDS_FILE):
        try:
            with open(PASSWORDS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                TEACHER_PASSWORDS = {int(k): v for k, v in data.items()}
            logger.info(f"{len(TEACHER_PASSWORDS)} ta parol yuklandi.")
        except Exception as e:
            logger.error(f"Parollarni yuklashda xato: {e}")

    if os.path.exists(SCHEDULE_FILE):
        try:
            with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
                SCHEDULE = json.load(f)
            logger.info(f"{len(SCHEDULE)} ta dars yuklandi.")
        except Exception as e:
            logger.error(f"Jadvalni yuklashda xato: {e}")

    load_user_roles()

def save_tests():
    try:
        with open(TESTS_FILE, "w", encoding="utf-8") as f:
            json.dump({"tests": TESTS, "counter": test_counter[0]}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Testlarni saqlashda xato: {e}")

def save_passwords():
    try:
        with open(PASSWORDS_FILE, "w", encoding="utf-8") as f:
            json.dump({str(k): v for k, v in TEACHER_PASSWORDS.items()}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Parollarni saqlashda xato: {e}")

def save_schedule():
    try:
        with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
            json.dump(SCHEDULE, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Jadvalni saqlashda xato: {e}")

def load_user_roles():
    global USER_ROLES
    if os.path.exists(USER_ROLES_FILE):
        try:
            with open(USER_ROLES_FILE, "r", encoding="utf-8") as f:
                USER_ROLES = json.load(f)
        except Exception as e:
            logger.error(f"Foydalanuvchi rollarni yuklashda xato: {e}")

def save_user_roles():
    try:
        with open(USER_ROLES_FILE, "w", encoding="utf-8") as f:
            json.dump(USER_ROLES, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Foydalanuvchi rollarni saqlashda xato: {e}")

def parse_answers_string(text: str):
    text = text.strip()
    code = None
    answers_part = text
    star_match = re.match(r'^([^*,]+)\*(.+)$', text, re.DOTALL)
    if star_match:
        code = star_match.group(1).strip()
        answers_part = star_match.group(2).strip()
    answers = [a.strip() for a in answers_part.split(',') if a.strip()]
    return code, answers

def calc_score(correct_answers, student_answers, balls):
    results = []
    n = len(correct_answers)
    for i in range(n):
        s_ans = student_answers[i].strip().lower().replace(" ", "") if i < len(student_answers) else ""
        c_ans = correct_answers[i].strip().lower().replace(" ", "")
        is_correct = (s_ans == c_ans)
        ball = balls[i] if i < len(balls) else 10
        results.append({
            "num": i + 1,
            "correct": correct_answers[i],
            "student": student_answers[i] if i < len(student_answers) else "\u2014",
            "ball_earned": ball if is_correct else 0,
            "max_ball": ball,
            "is_correct": is_correct,
        })
    return results

def get_now_weekday():
    return WEEKDAYS[datetime.datetime.now().weekday()]

def time_now_str():
    return datetime.datetime.now().strftime("%H:%M")

def is_time_between(start, end, current=None):
    if not current:
        current = time_now_str()
    return start <= current <= end

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.message.from_user.id)
    context.user_data.clear()

    if uid in USER_ROLES:
        role = USER_ROLES[uid]
        context.user_data["role"] = role
        if role == "teacher":
            if int(uid) in VERIFIED_TEACHERS:
                return await show_teacher_menu(update.message, context)
            else:
                await update.message.reply_text("🔐 Parolni kiriting:")
                return ENTER_PASSWORD
        elif role == "student":
            return await show_student_menu(update.message, context)

    keyboard = [
        [InlineKeyboardButton("👨‍🏫 O'qituvchi", callback_data="role_teacher")],
        [InlineKeyboardButton("👨‍🎓 O'quvchi",   callback_data="role_student")],
    ]
    await update.message.reply_text(
        "👋 *Test Botiga Xush Kelibsiz!*\n\nSiz kimsiz?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CHOOSING_ROLE

async def role_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass

    if query.data == "role_teacher":
        context.user_data["role"] = "teacher"
        uid = str(query.from_user.id)
        USER_ROLES[uid] = "teacher"
        save_user_roles()

        if int(uid) in VERIFIED_TEACHERS:
            return await show_teacher_menu(query.message, context)

        await query.message.reply_text("🔐 Parolni kiriting:")
        return ENTER_PASSWORD

    elif query.data == "role_student":
        context.user_data["role"] = "student"
        USER_ROLES[str(query.from_user.id)] = "student"
        save_user_roles()
        return await show_student_menu(query.message, context)

async def check_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    entered = update.message.text.strip()

    if uid in TEACHER_PASSWORDS:
        correct = TEACHER_PASSWORDS[uid]
    else:
        correct = ADMIN_PASSWORD

    if entered == correct:
        VERIFIED_TEACHERS.add(uid)
        await update.message.reply_text("✅ Xush kelibsiz, O'qituvchi!")
        return await show_teacher_menu(update.message, context)
    else:
        await update.message.reply_text("❌ Noto'g'ri parol.\nQayta urinib ko'ring:")
        return ENTER_PASSWORD

async def set_new_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pwd = update.message.text.strip()
    if len(pwd) < 4:
        await update.message.reply_text("⚠️ Parol kamida 4 ta belgidan iborat bo'lishi kerak.\nQayta kiriting:")
        return SET_NEW_PASSWORD
    context.user_data["pendign_password"] = pwd
    await update.message.reply_text("🔁 Parolni tasdiqlang (qayta kiriting):")
    return CONFIRM_PASSWORD

async def confirm_new_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    confirm = update.message.text.strip()
    pending = context.user_data.get("pending_password", "")

    if confirm == pending:
        TEACHER_PASSWORDS[uid] = pending
        VERIFIED_TEACHERS.add(uid)
        context.user_data.pop("pending_password", None)
        save_passwords()
        await update.message.reply_text(
            f"✅ Parol muvaffaqiyatli o'rnatildi!\n"
            f"Keyingi safar shu parol bilan kirasiz.\n\n"
            f"Xush kelibsiz, O'qituvchi! 👨‍🏫"
        )
        return await show_teacher_menu(update.message, context)
    else:
        await update.message.reply_text("❌ Parollar mos kelmadi.\nYangi parolni kiriting:")
        return SET_NEW_PASSWORD

async def change_password_old(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    entered = update.message.text.strip()
    correct = TEACHER_PASSWORDS.get(uid, ADMIN_PASSWORD)

    if entered == correct:
        await update.message.reply_text("✅ To'g'ri. Yangi parolni kiriting (kamida 4 belgi):")
        return CHANGE_PASSWORD_NEW
    else:
        await update.message.reply_text("❌ Eski parol noto'g'ri. Qayta urinib ko'ring:")
        return CHANGE_PASSWORD_OLD

async def change_password_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pwd = update.message.text.strip()
    if len(pwd) < 4:
        await update.message.reply_text("⚠️ Parol kamida 4 ta belgi bo'lishi kerak. Qayta kiriting:")
        return CHANGE_PASSWORD_NEW
    context.user_data["pending_password"] = pwd
    await update.message.reply_text("🔁 Yangi parolni tasdiqlang:")
    return CHANGE_PASSWORD_CNF

async def change_password_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    confirm = update.message.text.strip()
    pending = context.user_data.get("pending_password", "")

    if confirm == pending:
        TEACHER_PASSWORDS[uid] = pending
        context.user_data.pop("pending_password", None)
        save_passwords()
        await update.message.reply_text("✅ Parol muvaffaqiyatli o'zgartirildi!")
        return await show_teacher_menu(update.message, context)
    else:
        await update.message.reply_text("❌ Parollar mos kelmadi. Yangi parolni qayta kiriting:")
        return CHANGE_PASSWORD_NEW

async def show_teacher_menu(message, context):
    now = datetime.datetime.now().strftime("%H:%M")
    keyboard = []

    if TESTS:
        for tid, t in TESTS.items():
            st = t.get("start_time")
            et = t.get("end_time")
            time_tag = f" ⏰{st}-{et}" if st and et else ""
            active = " 🟢" if (st and et and st <= now <= et) else ""
            keyboard.append(
                [InlineKeyboardButton(f"[{tid}] {t['name']}{time_tag}{active}", callback_data=f"t_manage_{tid}")]
            )
    else:
        keyboard.append([InlineKeyboardButton("(hali test yo'q)", callback_data="t_none")])

    schedule_count = len(SCHEDULE)
    sched_btn = f"📅 Dars jadvali ({schedule_count})"

    keyboard.extend([
        [InlineKeyboardButton("➕ Yangi test qo'shish",    callback_data="t_add_test")],
        [InlineKeyboardButton("🗑 Testni o'chirish",       callback_data="t_del_test")],
        [InlineKeyboardButton(sched_btn,                   callback_data="t_schedule")],
        [InlineKeyboardButton("🔑 Parolni o'zgartirish",  callback_data="t_change_pwd")],
    ])
    await message.reply_text(
        f"👨‍🏫 *O'qituvchi paneli*\n\n"
        f"Test ustiga bosib boshqaring:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return TEACHER_MENU

async def teacher_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass

    if query.data == "t_add_test":
        await query.message.reply_text(
            "📝 Test nomini yozing:\n_(masalan: Algebra \u2014 1-variant)_",
            parse_mode="Markdown"
        )
        return TEACHER_TEST_NAME

    elif query.data == "t_del_test":
        if not TESTS:
            await query.message.reply_text("❗ O'chirish uchun test yo'q.")
            return TEACHER_MENU
        keyboard = [
            [InlineKeyboardButton(f"🗑 [{tid}] {t['name']}", callback_data=f"del_{tid}")]
            for tid, t in TESTS.items()
        ]
        keyboard.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="t_back")])
        await query.message.reply_text(
            "Qaysi testni o'chirmoqchisiz?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return TEACHER_MENU

    elif query.data.startswith("del_"):
        tid = query.data[4:]
        name = TESTS.pop(tid, {}).get("name", "?")
        save_tests()
        await query.message.reply_text(f"✅ *{name}* o'chirildi.", parse_mode="Markdown")
        return await show_teacher_menu(query.message, context)

    elif query.data == "t_schedule":
        return await show_teacher_schedule_menu(query.message, context)

    elif query.data == "t_change_pwd":
        await query.message.reply_text("🔑 Eski parolni kiriting:")
        return CHANGE_PASSWORD_OLD

    elif query.data == "t_back":
        return await show_teacher_menu(query.message, context)

    elif query.data == "t_none":
        await query.answer()
        return TEACHER_MENU

    elif query.data.startswith("t_manage_"):
        tid = query.data[9:]
        test = TESTS.get(tid)
        if not test:
            await query.message.reply_text("❗ Test topilmadi.")
            return TEACHER_MENU

        st = test.get("start_time")
        et = test.get("end_time")
        time_info = f"⏰ {st} - {et}" if st and et else "⏰ Vaqt cheklovi yo'q"

        keyboard = [
            [InlineKeyboardButton("🔄 Qayta ishga tushirish", callback_data=f"t_restart_{tid}")],
            [InlineKeyboardButton("⏰ Vaqt belgilash", callback_data=f"t_settime_{tid}")],
            [InlineKeyboardButton("🗑 O'chirish", callback_data=f"del_{tid}")],
            [InlineKeyboardButton("⬅️ Orqaga", callback_data="t_back")],
        ]
        await query.message.reply_text(
            f"📋 *{test['name']}*\n"
            f"📌 Kod: `{test['code']}`\n"
            f"📋 Savollar: {len(test['answers'])} ta\n"
            f"{time_info}\n\n"
            f"Nima qilmoqchisiz?",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return TEACHER_MENU

    elif query.data.startswith("t_restart_"):
        tid = query.data[10:]
        if tid in TESTS:
            TESTS[tid]["start_time"] = None
            TESTS[tid]["end_time"] = None
            save_tests()
            await query.message.reply_text(f"✅ *{TESTS[tid]['name']}* qayta ishga tushirildi!", parse_mode="Markdown")
        return await show_teacher_menu(query.message, context)

    elif query.data.startswith("t_settime_"):
        tid = query.data[10:]
        context.user_data["edit_test_id"] = tid
        await query.message.reply_text(
            "⏰ Test *boshlanish vaqtini* kiriting (HH:MM):\n\n"
            "Vaqt cheklovini olib tashlash uchun `-` yozing.",
            parse_mode="Markdown"
        )
        return TEACHER_TEST_START_TIME

# ============================================================
# TEACHER SCHEDULE
# ============================================================
async def show_teacher_schedule_menu(message, context):
    today = get_now_weekday()
    if not SCHEDULE:
        text = "📅 *Dars jadvali*\n\n(Hali dars qo'shilmagan)"
    else:
        lines = []
        for day in WEEKDAYS:
            day_lessons = {lid: l for lid, l in SCHEDULE.items() if l.get("day") == day}
            if day_lessons:
                lines.append(f"*{day}:*")
                for lid, l in day_lessons.items():
                    students = l.get("students", {})
                    st_count = len(students)
                    tag = " 🔔" if day == today and is_time_between(l["start_time"], l["end_time"]) else ""
                    lines.append(f"  \u2022 {l['name']} ({l['start_time']}-{l['end_time']}) - {st_count} ta talaba{tag}")
                lines.append("")
        text = "📅 *Dars jadvali*\n\n" + "\n".join(lines).strip()

    keyboard = [
        [InlineKeyboardButton("➕ Dars qo'shish",             callback_data="ts_add")],
        [InlineKeyboardButton("👤 Talabalarni boshqarish",    callback_data="ts_manage")],
        [InlineKeyboardButton("🗑 Darsni o'chirish",          callback_data="ts_delete")],
        [InlineKeyboardButton("⬅️ Orqaga",                   callback_data="ts_back")],
    ]
    await message.reply_text(text or "📅 Jadval bo'sh", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    return TEACHER_SCHEDULE_MENU

async def teacher_schedule_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass

    if query.data == "ts_add":
        await query.message.reply_text(
            "📝 *Dars nomini* yozing (masalan: Matematika):",
            parse_mode="Markdown"
        )
        return TEACHER_SCHEDULE_NAME

    elif query.data == "ts_manage":
        if not SCHEDULE:
            await query.message.reply_text("❗ Hali dars yo'q. Avval dars qo'shing.")
            return TEACHER_SCHEDULE_MENU
        keyboard = [
            [InlineKeyboardButton(f"{l['name']} ({l['start_time']}-{l['end_time']})", callback_data=f"tsm_{lid}")]
            for lid, l in SCHEDULE.items()
        ]
        keyboard.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="ts_back")])
        await query.message.reply_text(
            "Qaysi darsdagi talabalarni boshqarmoqchisiz?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return TEACHER_SCHEDULE_SELECT

    elif query.data.startswith("tsm_"):
        lid = query.data[4:]
        lesson = SCHEDULE.get(lid)
        if not lesson:
            await query.message.reply_text("❗ Dars topilmadi.")
            return TEACHER_SCHEDULE_MENU
        context.user_data["sched_select_id"] = lid
        students = lesson.get("students", {})
        if not students:
            s_text = "  (talaba yo'q)"
        else:
            s_lines = []
            for uid_str, info in students.items():
                s_lines.append(f"  \u2022 {info['name']} (\u231a{info.get('joined_at', '?')})")
            s_text = "\n".join(s_lines)
        await query.message.reply_text(
            f"📚 *{lesson['name']}* ({lesson['start_time']}-{lesson['end_time']})\n"
            f"👥 *Talabalar:*\n{s_text}\n\n"
            f"Talabani olib tashlash uchun uning nomini yozing:",
            parse_mode="Markdown"
        )
        return TEACHER_SCHEDULE_REMOVE

    elif query.data == "ts_delete":
        if not SCHEDULE:
            await query.message.reply_text("❗ Hali dars yo'q.")
            return TEACHER_SCHEDULE_MENU
        keyboard = [
            [InlineKeyboardButton(f"🗑 {l['name']} ({l['start_time']}-{l['end_time']})", callback_data=f"tsd_{lid}")]
            for lid, l in SCHEDULE.items()
        ]
        keyboard.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="ts_back")])
        await query.message.reply_text(
            "Qaysi darsni o'chirmoqchisiz?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return TEACHER_SCHEDULE_DELETE

    elif query.data.startswith("tsd_"):
        lid = query.data[4:]
        name = SCHEDULE.pop(lid, {}).get("name", "?")
        save_schedule()
        await query.message.reply_text(f"✅ *{name}* o'chirildi.", parse_mode="Markdown")
        return await show_teacher_schedule_menu(query.message, context)

    elif query.data == "ts_back":
        return await show_teacher_menu(query.message, context)

async def teacher_schedule_get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("⚠️ Iltimos, dars nomini yozing:")
        return TEACHER_SCHEDULE_NAME
    context.user_data["new_sched_name"] = name

    keyboard = [
        [InlineKeyboardButton(day, callback_data=f"tsday_{i}")]
        for i, day in enumerate(WEEKDAYS)
    ]
    await update.message.reply_text(
        "📅 *Dars kunini* tanlang:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return TEACHER_SCHEDULE_DAY

async def teacher_schedule_get_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass

    day_idx = int(query.data.replace("tsday_", ""))
    context.user_data["new_sched_day"] = WEEKDAYS[day_idx]
    await query.message.reply_text(
        f"Kun: {WEEKDAYS[day_idx]}\n\n"
        "⏰ *Boshlanish vaqtini* kiriting (HH:MM):",
        parse_mode="Markdown"
    )
    return TEACHER_SCHEDULE_START

async def teacher_schedule_get_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    match = re.match(r'^(\d{1,2})[:;](\d{2})$', text)
    if not match:
        await update.message.reply_text("⚠️ HH:MM formatida yozing (masalan: 08:00):")
        return TEACHER_SCHEDULE_START
    h, m = int(match.group(1)), int(match.group(2))
    if h < 0 or h > 23 or m < 0 or m > 59:
        await update.message.reply_text("⚠️ Soat 0-23, minut 0-59 oralig'ida bo'lsin:")
        return TEACHER_SCHEDULE_START
    context.user_data["new_sched_start"] = f"{h:02d}:{m:02d}"
    await update.message.reply_text(
        f"✅ Boshlanish: {context.user_data['new_sched_start']}\n"
        "⏰ *Tugash vaqtini* kiriting (HH:MM):",
        parse_mode="Markdown"
    )
    return TEACHER_SCHEDULE_END

async def teacher_schedule_get_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    match = re.match(r'^(\d{1,2})[:;](\d{2})$', text)
    if not match:
        await update.message.reply_text("⚠️ HH:MM formatida yozing (masalan: 09:30):")
        return TEACHER_SCHEDULE_END
    h, m = int(match.group(1)), int(match.group(2))
    if h < 0 or h > 23 or m < 0 or m > 59:
        await update.message.reply_text("⚠️ Soat 0-23, minut 0-59 oralig'ida bo'lsin:")
        return TEACHER_SCHEDULE_END
    end_time = f"{h:02d}:{m:02d}"
    start_time = context.user_data["new_sched_start"]
    if end_time <= start_time:
        await update.message.reply_text("⚠️ Tugash vaqti boshlanishdan keyin bo'lishi kerak:")
        return TEACHER_SCHEDULE_END

    lesson_id = f"dars{len(SCHEDULE) + 1}"
    name = context.user_data["new_sched_name"]
    day = context.user_data["new_sched_day"]
    teacher_name = update.message.from_user.first_name or "O'qituvchi"

    SCHEDULE[lesson_id] = {
        "name": name,
        "day": day,
        "start_time": start_time,
        "end_time": end_time,
        "teacher_id": update.message.from_user.id,
        "teacher_name": teacher_name,
        "students": {},
    }
    save_schedule()

    context.user_data.pop("new_sched_name", None)
    context.user_data.pop("new_sched_day", None)
    context.user_data.pop("new_sched_start", None)
    context.user_data.pop("new_sched_end", None)

    await update.message.reply_text(
        f"✅ *{name}* qo'shildi!\n"
        f"📅 {day} | {start_time} - {end_time}",
        parse_mode="Markdown"
    )
    return await show_teacher_schedule_menu(update.message, context)

async def teacher_schedule_remove_student(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lid = context.user_data.get("sched_select_id")
    if not lid or lid not in SCHEDULE:
        await update.message.reply_text("❗ Dars topilmadi.")
        return TEACHER_SCHEDULE_MENU
    lesson = SCHEDULE[lid]
    student_name_to_remove = update.message.text.strip().lower()
    students = lesson.get("students", {})

    found = None
    for uid_str, info in list(students.items()):
        if info["name"].lower() == student_name_to_remove:
            found = uid_str
            break

    if found:
        del students[found]
        save_schedule()
        await update.message.reply_text(f"✅ Talaba o'chirildi.")
    else:
        await update.message.reply_text(
            "❌ Bunday talaba topilmadi.\n"
            "Qayta urinib ko'ring yoki /start bosing."
        )

    context.user_data.pop("sched_select_id", None)
    return await show_teacher_schedule_menu(update.message, context)

# ============================================================
# TEACHER TEST FLOW
# ============================================================
async def get_test_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_test_name"] = update.message.text.strip()
    context.user_data["new_creator"] = update.message.from_user.first_name or "Noma'lum"
    await update.message.reply_text(
        "⏰ Test *boshlanish vaqtini* kiriting.\n\n"
        "Format: `HH:MM` (masalan: `08:00`)\n\n"
        "Agar vaqt cheklovi kerak bo'lmasa, `-` yozing.",
        parse_mode="Markdown"
    )
    return TEACHER_TEST_START_TIME

async def get_start_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    edit_id = context.user_data.get("edit_test_id")

    if text in ("-", "\u2014", "yo'q", "no", ""):
        if edit_id and edit_id in TESTS:
            TESTS[edit_id]["start_time"] = None
            TESTS[edit_id]["end_time"] = None
            save_tests()
            context.user_data.pop("edit_test_id", None)
            await update.message.reply_text(f"✅ *{TESTS[edit_id]['name']}* vaqt cheklovi olib tashlandi!", parse_mode="Markdown")
            return await show_teacher_menu(update.message, context)
        context.user_data["new_start_time"] = None
        context.user_data["new_end_time"] = None
        await update.message.reply_text(
            "✏️ Endi *test javoblarini* yuboring.\n\n"
            "📌 *Format:* `KOD*javob1,javob2,javob3,...`\n\n"
            "Misol:\n"
            "`1*a,b,c,d,a,b,c,d`\n\n"
            "Ball formati (ixtiyoriy, alohida qatorda):\n"
            "`BALLLAR: 20,10,20,10,...`\n\n"
            "Ball ko'rsatilmasa, har bir to'g'ri javob \u2014 10 ball.",
            parse_mode="Markdown"
        )
        return TEACHER_ANSWERS

    time_match = re.match(r'^(\d{1,2})[:;](\d{2})$', text)
    if not time_match:
        await update.message.reply_text(
            "⚠️ Noto'g'ri format. Iltimos `HH:MM` shaklida yozing (masalan: 08:00):"
        )
        return TEACHER_TEST_START_TIME

    hour, minute = int(time_match.group(1)), int(time_match.group(2))
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        await update.message.reply_text("⚠️ Vaqt noto'g'ri. Soat 0-23, minut 0-59 oralig'ida bo'lishi kerak:")
        return TEACHER_TEST_START_TIME

    context.user_data["new_start_time"] = f"{hour:02d}:{minute:02d}"
    await update.message.reply_text(
        f"✅ Boshlanish vaqti: {context.user_data['new_start_time']}\n"
        "⏰ Test *tugash vaqtini* kiriting (masalan: 11:30):",
        parse_mode="Markdown"
    )
    return TEACHER_TEST_END_TIME

async def get_end_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    start_time = context.user_data.get("new_start_time")

    time_match = re.match(r'^(\d{1,2})[:;](\d{2})$', text)
    if not time_match:
        await update.message.reply_text(
            "⚠️ Noto'g'ri format. Iltimos `HH:MM` shaklida yozing (masalan: 11:30):"
        )
        return TEACHER_TEST_END_TIME

    hour, minute = int(time_match.group(1)), int(time_match.group(2))
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        await update.message.reply_text("⚠️ Vaqt noto'g'ri. Soat 0-23, minut 0-59 oralig'ida bo'lishi kerak:")
        return TEACHER_TEST_END_TIME

    end_time = f"{hour:02d}:{minute:02d}"
    if end_time <= start_time:
        await update.message.reply_text(
            "⚠️ Tugash vaqti boshlanish vaqtidan keyin bo'lishi kerak. Qayta kiriting:"
        )
        return TEACHER_TEST_END_TIME

    context.user_data["new_end_time"] = end_time

    edit_id = context.user_data.get("edit_test_id")
    if edit_id and edit_id in TESTS:
        TESTS[edit_id]["start_time"] = context.user_data["new_start_time"]
        TESTS[edit_id]["end_time"] = end_time
        save_tests()
        context.user_data.pop("edit_test_id", None)
        context.user_data.pop("new_start_time", None)
        context.user_data.pop("new_end_time", None)
        await update.message.reply_text(f"✅ *{TESTS[edit_id]['name']}* vaqti yangilandi!", parse_mode="Markdown")
        return await show_teacher_menu(update.message, context)

    await update.message.reply_text(
        f"✅ Vaqt oralig'i: {start_time} - {end_time}\n\n"
        "✏️ Endi *test javoblarini* yuboring.\n\n"
        "📌 *Format:* `KOD*javob1,javob2,javob3,...`\n\n"
        "Misol:\n"
        "`1*a,b,c,d,a,b,c,d`\n\n"
        "Ball formati (ixtiyoriy, alohida qatorda):\n"
        "`BALLLAR: 20,10,20,10,...`\n\n"
        "Ball ko'rsatilmasa, har bir to'g'ri javob \u2014 10 ball.",
        parse_mode="Markdown"
    )
    return TEACHER_ANSWERS

async def get_answers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    custom_balls = None
    lines = text.split('\n')
    answers_line = lines[0].strip()
    for line in lines[1:]:
        if line.strip().upper().startswith("BALL"):
            ball_part = re.sub(r'^[Bb][Aa][Ll][Ll][Ll][Aa][Rr]?[:\s]*', '', line.strip())
            custom_balls = [int(b.strip()) for b in ball_part.split(',') if b.strip().isdigit()]

    code, answers = parse_answers_string(answers_line)

    if not answers:
        await update.message.reply_text(
            "⚠️ Javoblar topilmadi. Iltimos qayta yuboring.\nFormat: `KOD*javob1,javob2,...`",
            parse_mode="Markdown"
        )
        return TEACHER_ANSWERS

    n = len(answers)
    balls = custom_balls if (custom_balls and len(custom_balls) == n) else [10] * n

    test_counter[0] += 1
    tid = code if code else f"test{test_counter[0]}"
    if tid in TESTS:
        tid = f"{tid}_{test_counter[0]}"

    name = context.user_data.get("new_test_name", f"Test {test_counter[0]}")
    creator = context.user_data.get("new_creator", "Noma'lum")
    start_time = context.user_data.get("new_start_time")
    end_time = context.user_data.get("new_end_time")

    TESTS[tid] = {
        "name": name,
        "creator": creator,
        "answers": answers,
        "balls": balls,
        "code": code or tid,
        "start_time": start_time,
        "end_time": end_time,
    }
    save_tests()

    max_ball = sum(balls)
    preview = ", ".join(answers)
    time_info = f"⏰ {start_time} - {end_time}\n" if start_time and end_time else ""

    await update.message.reply_text(
        f"🎉 *{name}* saqlandi!\n\n"
        f"{time_info}"
        f"📌 Test kodi: `{tid}`\n"
        f"📋 Savollar soni: {n} ta\n"
        f"💯 Maksimal ball: {max_ball}\n"
        f"✅ Javoblar: `{preview}`",
        parse_mode="Markdown"
    )
    return await show_teacher_menu(update.message, context)

# ============================================================
# STUDENT MENU
# ============================================================
async def show_student_menu(message, context):
    keyboard = []
    now = datetime.datetime.now().strftime("%H:%M")

    if TESTS:
        for tid, t in TESTS.items():
            st = t.get("start_time")
            et = t.get("end_time")
            if st and et:
                if now < st or now > et:
                    continue
            keyboard.append(
                [InlineKeyboardButton(f"[{tid}] {t['name']}", callback_data=f"s_test_{tid}")]
            )

    today = get_now_weekday()
    today_lessons = {lid: l for lid, l in SCHEDULE.items() if l.get("day") == today}
    if today_lessons:
        keyboard.append([InlineKeyboardButton("📅 Darslar", callback_data="ss_view")])

    keyboard.append([InlineKeyboardButton("🔄 Qaytadan /start", callback_data="s_restart")])

    await message.reply_text(
        "📚 *O'quvchi paneli*\n\n"
        "Test topshirish yoki darslarga yozilish uchun pastdagi tugmalardan foydalaning:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return STUDENT_MENU

# ============================================================
# STUDENT TEST FLOW
# ============================================================
async def student_test_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass

    tid = query.data[7:]
    if tid not in TESTS:
        await query.message.reply_text("❗ Bu test topilmadi.")
        return await show_student_menu(query.message, context)

    test = TESTS[tid]

    start_time = test.get("start_time")
    end_time = test.get("end_time")
    if start_time and end_time:
        now = datetime.datetime.now().strftime("%H:%M")
        if now < start_time:
            await query.message.reply_text(
                f"⏳ Bu test hali boshlanmadi. Boshlanish vaqti: {start_time}"
            )
            return await show_student_menu(query.message, context)
        if now > end_time:
            await query.message.reply_text(
                f"⌛ Bu test tugagan. Tugash vaqti: {end_time}"
            )
            return await show_student_menu(query.message, context)

    context.user_data["test_id"] = tid
    context.user_data["student_name"] = query.from_user.first_name or "O'quvchi"

    n = len(test["answers"])
    max_ball = sum(test["balls"])

    await query.message.reply_text(
        f"✅ *{test['name']}* tanlandi!\n\n"
        f"📌 Test kodi: `{test['code']}`\n"
        f"📋 Savollar soni: {n} ta\n"
        f"💯 Maksimal ball: {max_ball}\n\n"
        f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        f"📝 *Javoblarni yuboring:*\n\n"
        f"Format:\n"
        f"`KOD*javob1,javob2,javob3,...`\n\n"
        f"Misol:\n"
        f"`{test['code']}*a,b,c,d,...`\n\n"
        f"Barcha {n} ta javobni vergul bilan yozing 👇",
        parse_mode="Markdown"
    )
    return WAITING_ANSWERS

async def check_answers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "test_id" not in context.user_data:
        await update.message.reply_text("❗ Avval /start bosing va test tanlang.")
        return ConversationHandler.END

    test_id = context.user_data["test_id"]
    if test_id not in TESTS:
        await update.message.reply_text("❗ Test topilmadi.")
        return ConversationHandler.END

    test = TESTS[test_id]
    student_name = context.user_data.get("student_name", "O'quvchi")
    text = update.message.text.strip()

    code, student_answers = parse_answers_string(text)

    if code and code != test["code"]:
        await update.message.reply_text(
            f"⚠️ Test kodi mos kelmadi!\n"
            f"Siz yubordingiz: `{code}`\n"
            f"Kerakli kod: `{test['code']}`\n\n"
            f"Iltimos, to'g'ri test javoblarini yuboring.",
            parse_mode="Markdown"
        )
        return WAITING_ANSWERS

    n = len(test["answers"])
    if len(student_answers) < n:
        await update.message.reply_text(
            f"⚠️ {n} ta savol bor, lekin {len(student_answers)} ta javob yubordingiz.\n"
            f"Iltimos, barcha {n} ta javobni yuboring."
        )
        return WAITING_ANSWERS

    results = calc_score(test["answers"], student_answers, test["balls"])
    total_ball = sum(r["ball_earned"] for r in results)
    max_ball = sum(r["max_ball"] for r in results)
    percentage = (total_ball / max_ball * 100) if max_ball > 0 else 0
    creator = test.get("creator", "Noma'lum")

    result_lines = []
    for r in results:
        mark = "✅" if r["is_correct"] else "❌"
        result_lines.append(f"{r['num']}. {r['correct'].upper()} {mark} {r['ball_earned']} ball")
    result_text = "\n".join(result_lines)

    msg = (
        f"*{student_name} ning natijasi*\n"
        f"📌 Test kodi: {test['code']}\n"
        f"📋 Savollar soni: {n} ta\n"
        f"👤 Yaratuvchi: {creator}\n\n"
        f"Natijalari:\n"
        f"{result_text}\n\n"
        f"📊 Jami: {total_ball} / {max_ball} ball\n"
        f"☑️ Natija: {percentage:.1f}%"
    )

    await update.message.reply_text(msg, parse_mode="Markdown")

    context.user_data.pop("test_id", None)
    context.user_data.pop("student_name", None)

    keyboard = [[InlineKeyboardButton("🔄 Boshqa test topshirish", callback_data="s_restart")]]
    await update.message.reply_text(
        "Boshqa test topshirmoqchimisiz?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return STUDENT_MENU

async def student_restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass
    context.user_data.pop("test_id", None)
    context.user_data.pop("student_name", None)
    context.user_data["role"] = "student"
    return await show_student_menu(query.message, context)

# ============================================================
# STUDENT SCHEDULE
# ============================================================
async def student_schedule_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass

    today = get_now_weekday()
    now = time_now_str()
    uid = str(query.from_user.id)

    today_lessons = {lid: l for lid, l in SCHEDULE.items() if l.get("day") == today}

    if not today_lessons:
        await query.message.reply_text(
            f"📅 Bugun ({today}) dars yo'q.\n"
            f"Dam oling yoki test topshiring! 😊"
        )
        return await show_student_menu(query.message, context)

    lines = [f"📅 *Bugun ({today})*"]
    for lid, l in today_lessons.items():
        students = l.get("students", {})
        is_joined = uid in students
        status = "✅ Yozilgansiz" if is_joined else "⬜ Yozilishingiz mumkin"
        active = " 🟢" if is_time_between(l["start_time"], l["end_time"], now) else ""
        lines.append(f"\n\u2022 *{l['name']}*{active}")
        lines.append(f"  \u23f0 {l['start_time']} - {l['end_time']}")
        lines.append(f"  {status}")
    text = "\n".join(lines)

    keyboard = []
    for lid, l in today_lessons.items():
        students = l.get("students", {})
        is_joined = uid in students
        if is_joined:
            keyboard.append([InlineKeyboardButton(f"❌ {l['name']} - Chiqish", callback_data=f"ss_leave_{lid}")])
        else:
            keyboard.append([InlineKeyboardButton(f"✅ {l['name']} - Yozilish", callback_data=f"ss_join_{lid}")])
    keyboard.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="ss_back")])

    await query.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    return STUDENT_SCHEDULE_VIEW

async def student_schedule_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass

    lid = query.data.replace("ss_join_", "")
    lesson = SCHEDULE.get(lid)
    if not lesson:
        await query.message.reply_text("❗ Dars topilmadi.")
        return await show_student_menu(query.message, context)

    uid = str(query.from_user.id)
    name = query.from_user.first_name or "O'quvchi"

    if uid in lesson.get("students", {}):
        await query.message.reply_text("ℹ️ Siz allaqachon yozilgansiz.")
    else:
        lesson.setdefault("students", {})[uid] = {
            "name": name,
            "joined_at": time_now_str()
        }
        save_schedule()
        await query.message.reply_text(f"✅ *{lesson['name']}* darsiga yozildingiz!", parse_mode="Markdown")

    return await show_student_menu(query.message, context)

async def student_schedule_leave(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass

    lid = query.data.replace("ss_leave_", "")
    lesson = SCHEDULE.get(lid)
    if not lesson:
        await query.message.reply_text("❗ Dars topilmadi.")
        return await show_student_menu(query.message, context)

    uid = str(query.from_user.id)
    if uid in lesson.get("students", {}):
        del lesson["students"][uid]
        save_schedule()
        await query.message.reply_text(f"✅ *{lesson['name']}* darsidan chiqdingiz.", parse_mode="Markdown")
    else:
        await query.message.reply_text("ℹ️ Siz bu darsga yozilmagansiz.")

    return await show_student_menu(query.message, context)

async def student_schedule_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass
    return await show_student_menu(query.message, context)

# ============================================================
# HELP
# ============================================================
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Bot haqida:*\n\n"
        "👨‍🏫 *O'qituvchi uchun:*\n"
        "1. /start \u2192 O'qituvchi tanla\n"
        "2. Parol kiriting\n"
        "3. Test nomini yozing\n"
        "4. Javoblarni yuboring: `KOD*javob1,javob2,...`\n"
        "5. Dars jadvalini boshqaring (qo'shish, o'chirish, talabalarni olib tashlash)\n\n"
        "👨‍🎓 *O'quvchi uchun:*\n"
        "1. /start \u2192 O'quvchi tanla\n"
        "2. Test tanlang va javob yuboring\n"
        "3. Darslarga yozilishingiz mumkin\n"
        "4. Bot foiz va ball bilan tekshiradi! 📊",
        parse_mode="Markdown"
    )

# ============================================================
# MAIN
# ============================================================
def main():
    load_data()
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
        ],
        states={
            CHOOSING_ROLE: [
                CallbackQueryHandler(role_selected, pattern="^role_"),
            ],
            ENTER_PASSWORD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, check_password),
            ],
            SET_NEW_PASSWORD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, set_new_password),
            ],
            CONFIRM_PASSWORD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_new_password),
            ],
            CHANGE_PASSWORD_OLD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, change_password_old),
            ],
            CHANGE_PASSWORD_NEW: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, change_password_new),
            ],
            CHANGE_PASSWORD_CNF: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, change_password_confirm),
            ],
            TEACHER_MENU: [
                CallbackQueryHandler(teacher_menu_callback, pattern="^(t_|del_)"),
            ],
            TEACHER_TEST_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_test_name),
            ],
            TEACHER_ANSWERS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_answers),
            ],
            TEACHER_TEST_START_TIME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_start_time),
            ],
            TEACHER_TEST_END_TIME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_end_time),
            ],
            STUDENT_MENU: [
                CallbackQueryHandler(student_test_selected, pattern="^s_test_"),
                CallbackQueryHandler(student_schedule_view, pattern="^ss_view$"),
                CallbackQueryHandler(student_restart, pattern="^s_restart$"),
            ],
            WAITING_ANSWERS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, check_answers),
                CallbackQueryHandler(student_restart, pattern="^s_restart$"),
            ],
            TEACHER_SCHEDULE_MENU: [
                CallbackQueryHandler(teacher_schedule_callback, pattern="^ts_"),
            ],
            TEACHER_SCHEDULE_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, teacher_schedule_get_name),
            ],
            TEACHER_SCHEDULE_DAY: [
                CallbackQueryHandler(teacher_schedule_get_day, pattern="^tsday_"),
            ],
            TEACHER_SCHEDULE_START: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, teacher_schedule_get_start),
            ],
            TEACHER_SCHEDULE_END: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, teacher_schedule_get_end),
            ],
            TEACHER_SCHEDULE_SELECT: [
                CallbackQueryHandler(teacher_schedule_callback, pattern="^tsm_"),
            ],
            TEACHER_SCHEDULE_REMOVE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, teacher_schedule_remove_student),
            ],
            TEACHER_SCHEDULE_DELETE: [
                CallbackQueryHandler(teacher_schedule_callback, pattern="^tsd_"),
            ],
            STUDENT_SCHEDULE_VIEW: [
                CallbackQueryHandler(student_schedule_join, pattern="^ss_join_"),
                CallbackQueryHandler(student_schedule_leave, pattern="^ss_leave_"),
                CallbackQueryHandler(student_schedule_back, pattern="^ss_back$"),
            ],
            STUDENT_SCHEDULE_JOIN: [
                CallbackQueryHandler(student_schedule_join, pattern="^ss_join_"),
            ],
        },
        fallbacks=[
            CommandHandler("start", start),
        ],
        per_user=True,
        per_chat=True,
        per_message=False,
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("help", help_cmd))

    logger.info("Bot ishga tushdi! ✅")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
