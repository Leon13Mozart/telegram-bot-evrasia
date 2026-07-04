import sqlite3
import logging
import asyncio
from datetime import datetime, timedelta

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from telegram import Update
from telegram.constants import ChatMemberStatus
from telegram.ext import (
    Application,
    ContextTypes,
    CommandHandler,
    ChatMemberHandler,
)

# ============================================================
# НАЛАШТУВАННЯ
# ============================================================

import os

DB_PATH = os.getenv("DB_PATH", "database.db")

TOKEN = os.getenv(
    "BOT_TOKEN",
)

# ID користувачів, які мають доступ до команд
ADMINS = [
    929200380,395523040
]

DATABASE = "telegram_stats.db"

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)

# ============================================================
# БАЗА ДАНИХ
# ============================================================

db = sqlite3.connect(
    DATABASE,
    check_same_thread=False
)

# ============================================================
# РОБОТА З БАЗОЮ ДАНИХ
# ============================================================

def register_group(chat):

    with sqlite3.connect(DATABASE) as conn:

        conn.execute(
            """
            INSERT OR IGNORE INTO groups(
                group_id,
                title
            )
            VALUES(?,?)
            """,
            (chat.id, chat.title),
        )

        conn.commit()


def save_event(chat, user, action):

    register_group(chat)

    username = user.username or ""

    with sqlite3.connect(DATABASE) as conn:

        conn.execute(
            """
            INSERT INTO events(
                group_id,
                user_id,
                username,
                first_name,
                action,
                event_time
            )
            VALUES(?,?,?,?,?,?)
            """,
            (
                chat.id,
                user.id,
                username,
                user.first_name,
                action,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )

        conn.commit()


# ============================================================
# ОТРИМАННЯ СТАТИСТИКИ
# ============================================================

def count_events(group_id, action=None, days=None):

    sql = """
    SELECT COUNT(*)
    FROM events
    WHERE group_id=?
    """

    params = [group_id]

    if action:
        sql += " AND action=?"
        params.append(action)

    if days is not None:

        date = (
            datetime.now() - timedelta(days=days)
        ).strftime("%Y-%m-%d %H:%M:%S")

        sql += " AND event_time>=?"
        params.append(date)

    with sqlite3.connect(DATABASE) as conn:

        result = conn.execute(sql, tuple(params)).fetchone()

        return result[0] if result else 0


def total_stats(group_id):

    joins = count_events(group_id, "join")
    leaves = count_events(group_id, "leave")

    return joins, leaves


def today_stats(group_id):

    today = datetime.now().replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    return count_events_from_date(group_id, today)


def week_stats(group_id):

    now = datetime.now()

    monday = now - timedelta(days=now.weekday())

    monday = monday.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    return count_events_from_date(group_id, monday)


def month_stats(group_id):

    now = datetime.now()

    first_day = now.replace(
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    return count_events_from_date(group_id, first_day)

def count_events_from_date(group_id, date):

    joins = 0
    leaves = 0

    sql = """
    SELECT action, COUNT(*)
    FROM events
    WHERE group_id=?
      AND event_time>=?
    GROUP BY action
    """

    with sqlite3.connect(DATABASE) as conn:

        rows = conn.execute(
            sql,
            (
                group_id,
                date.strftime("%Y-%m-%d %H:%M:%S"),
            ),
        ).fetchall()

    for action, count in rows:

        if action == "join":
            joins = count

        elif action == "leave":
            leaves = count

    return joins, leaves

# ============================================================
# СПИСОК ГРУП
# ============================================================

def get_groups():

    with sqlite3.connect(DATABASE) as conn:

        cursor = conn.execute(
            """
            SELECT group_id, title
            FROM groups
            ORDER BY title
            """
        )

        return cursor.fetchall()


# ============================================================
# ПЕРЕВІРКА АДМІНІСТРАТОРА
# ============================================================

def is_admin(user_id):

    return user_id in ADMINS
# ============================================================
# ОБРОБНИК ВХОДУ / ВИХОДУ УЧАСНИКІВ
# ============================================================

async def chat_member_update(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    result = update.chat_member

    old_status = result.old_chat_member.status
    new_status = result.new_chat_member.status

    chat = result.chat
    user = result.new_chat_member.user

    joined = (
        old_status in (
            ChatMemberStatus.LEFT,
            ChatMemberStatus.BANNED,
        )
        and new_status in (
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        )
    )

    left = (
        old_status in (
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        )
        and new_status in (
            ChatMemberStatus.LEFT,
            ChatMemberStatus.BANNED,
        )
    )

    if joined:

        save_event(
            chat,
            user,
            "join",
        )

        logging.info(
            f"{user.full_name} приєднався до {chat.title}"
        )

    elif left:

        save_event(
            chat,
            user,
            "leave",
        )

        logging.info(
            f"{user.full_name} покинув {chat.title}"
        )


def init_db():
    with sqlite3.connect(DATABASE) as conn:

        conn.execute("""
        CREATE TABLE IF NOT EXISTS groups (
            group_id INTEGER PRIMARY KEY,
            title TEXT
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER,
            user_id INTEGER,
            action TEXT,
            event_time TEXT
        )
        """)

        conn.commit()


# ============================================================
# /START
# ============================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not is_admin(update.effective_user.id):
        return

    text = (
        "📊 Бот статистики працює.\n\n"
        "Доступні команди:\n\n"
        "/groups — список груп\n"
        "/stats — статистика\n"
        "/addgroup — додати поточну групу\n"
        "/excel — вивід в таблицю"
    )

    await update.message.reply_text(text)


async def addgroup(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id not in ADMINS:
        return

    chat = update.effective_chat

    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text(
            "Цю команду можна використовувати лише в групі."
        )
        return

    register_group(chat)

    await update.message.reply_text(
        f"✅ Групу збережено\n\n"
        f"Назва: {chat.title}\n"
        f"ID: {chat.id}"
    )

async def excel(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id not in ADMINS:
        return

    groups = get_groups()

    if not groups:
        await update.message.reply_text("Немає збережених груп.")
        return

    now = datetime.now()

    months = {
        1: "Січень",
        2: "Лютий",
        3: "Березень",
        4: "Квітень",
        5: "Травень",
        6: "Червень",
        7: "Липень",
        8: "Серпень",
        9: "Вересень",
        10: "Жовтень",
        11: "Листопад",
        12: "Грудень",
    }

    month_name = months[now.month]

    week_start = (
        now - timedelta(days=now.weekday())
    ).strftime("%d.%m.%Y")

    week_end = now.strftime("%d.%m.%Y")

    month_start = now.replace(day=1).strftime("%d.%m.%Y")

    month_end = now.strftime("%d.%m.%Y")

    wb = Workbook()
    ws = wb.active
    ws.title = "Статистика"

    ws["A1"] = "📊 ЗВІТ ПО ГРУПАХ"
    ws["A2"] = f"Поточний тиждень: {week_start} — {week_end}"
    ws["A3"] = f"{month_name} {now.year}: {month_start} — {month_end}"
    ws["A4"] = f"Дата формування: {now.strftime('%d.%m.%Y %H:%M')}"

    ws["A1"].font = Font(bold=True, size=16)
    ws["A2"].font = Font(bold=True)
    ws["A3"].font = Font(bold=True)
    ws["A4"].font = Font(italic=True)

    headers = [
        "Група",
        "Тиждень (+)",
        "Тиждень (-)",
        "Місяць (+)",
        "Місяць (-)",
        "Загалом (+)",
        "Загалом (-)"
    ]

    header_row = 6

    for col, header in enumerate(headers, 1):

        cell = ws.cell(row=header_row, column=col)

        cell.value = header
        cell.font = Font(bold=True)
        cell.fill = PatternFill(
            fill_type="solid",
            start_color="4F81BD"
        )
        cell.alignment = Alignment(horizontal="center")

    row = 7

    total_week_join = 0
    total_week_leave = 0
    total_month_join = 0
    total_month_leave = 0
    total_join = 0
    total_leave = 0

    for group_id, title in groups:

        week_join, week_leave = week_stats(group_id)

        month_join, month_leave = month_stats(group_id)

        all_join = count_events(group_id, "join")
        all_leave = count_events(group_id, "leave")

        ws.cell(row=row, column=1).value = title
        ws.cell(row=row, column=2).value = week_join
        ws.cell(row=row, column=3).value = week_leave
        ws.cell(row=row, column=4).value = month_join
        ws.cell(row=row, column=5).value = month_leave
        ws.cell(row=row, column=6).value = all_join
        ws.cell(row=row, column=7).value = all_leave

        total_week_join += week_join
        total_week_leave += week_leave
        total_month_join += month_join
        total_month_leave += month_leave
        total_join += all_join
        total_leave += all_leave

        row += 1

    ws.cell(row=row, column=1).value = "РАЗОМ"
    ws.cell(row=row, column=1).font = Font(bold=True)

    ws.cell(row=row, column=2).value = total_week_join
    ws.cell(row=row, column=3).value = total_week_leave
    ws.cell(row=row, column=4).value = total_month_join
    ws.cell(row=row, column=5).value = total_month_leave
    ws.cell(row=row, column=6).value = total_join
    ws.cell(row=row, column=7).value = total_leave

    for column in ws.columns:

        length = max(len(str(cell.value or "")) for cell in column)

        ws.column_dimensions[
            get_column_letter(column[0].column)
        ].width = length + 4

    filename = f"Статистика_{now.strftime('%d-%m-%Y')}.xlsx"

    wb.save(filename)

    with open(filename, "rb") as file:

        await update.message.reply_document(
            document=file,
            filename=filename,
            caption="📊 Звіт по всіх групах"
        )
# ============================================================
# /GROUPS
# ============================================================

async def groups(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not is_admin(update.effective_user.id):
        return

    groups_list = get_groups()

    if not groups_list:

        await update.message.reply_text(
            "Бот ще не зберіг жодної групи."
        )

        return

    text = "📋 Список груп:\n\n"

    for group_id, title in groups_list:

        text += (
            f"🏷 {title}\n"
            f"`{group_id}`\n\n"
        )

    await update.message.reply_text(
        text,
        parse_mode="Markdown",
    )


# ============================================================
# /STATS
# ============================================================
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id not in ADMINS:
        return

    groups = get_groups()

    if not groups:
        await update.message.reply_text(
            "Немає збережених груп."
        )
        return

    now = datetime.now()

    today_date = now.strftime("%d.%m.%Y")

    week_start = (
        now - timedelta(days=now.weekday())
    ).strftime("%d.%m.%Y")

    week_end = now.strftime("%d.%m.%Y")

    month_start = now.replace(day=1).strftime("%d.%m.%Y")

    month_end = now.strftime("%d.%m.%Y")

    months = {
        1: "Січень",
        2: "Лютий",
        3: "Березень",
        4: "Квітень",
        5: "Травень",
        6: "Червень",
        7: "Липень",
        8: "Серпень",
        9: "Вересень",
        10: "Жовтень",
        11: "Листопад",
        12: "Грудень",
    }

    month_name = months[now.month]

    text = "📊 <b>Статистика груп</b>\n\n"

    for group_id, title in groups:

        today_join, today_leave = today_stats(group_id)

        week_join, week_leave = week_stats(group_id)

        month_join, month_leave = month_stats(group_id)

        total_join = count_events(group_id, "join")
        total_leave = count_events(group_id, "leave")

        text += (
            f"🍣 <b>{title}</b>\n\n"

            f"📅 <b>Сьогодні ({today_date})</b>\n"
            f"➕ Додалося: {today_join}\n"
            f"➖ Вийшло: {today_leave}\n\n"

            f"📅 <b>Поточний тиждень</b>\n"
            f"🗓 {week_start} — {week_end}\n"
            f"➕ Додалося: {week_join}\n"
            f"➖ Вийшло: {week_leave}\n\n"

            f"📅 <b>{month_name} {now.year}</b>\n"
            f"🗓 {month_start} — {month_end}\n"
            f"➕ Додалося: {month_join}\n"
            f"➖ Вийшло: {month_leave}\n\n"

            f"📈 <b>Загалом</b>\n"
            f"➕ Додалося: {total_join}\n"
            f"➖ Вийшло: {total_leave}\n\n"

            "────────────────────\n\n"
        )

    await update.message.reply_text(
        text,
        parse_mode="HTML",
    )
# ============================================================
# ДОДАТКОВА КОМАНДА
# ============================================================

async def ping(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not is_admin(update.effective_user.id):
        return

    await update.message.reply_text(
        "🏓 Pong\nБот працює."
    )


# ============================================================
# ОБРОБНИК ПОМИЛОК
# ============================================================

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):

    logging.error(
        "Помилка:",
        exc_info=context.error
    )
# ============================================================
# ЗАПУСК БОТА
# ============================================================

def main():

    # Створюємо таблиці бази даних
    init_db()

    app = Application.builder().token(TOKEN).build()

    # Команди бота
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("groups", groups))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("addgroup", addgroup))
    app.add_handler(CommandHandler("excel", excel))

    # Обробник входу та виходу учасників
    app.add_handler(
        ChatMemberHandler(
            chat_member_update,
            ChatMemberHandler.CHAT_MEMBER,
        )
    )

    async def run():

        await app.initialize()
        await app.start()

        # Видаляємо можливий webhook
        await app.bot.delete_webhook(
            drop_pending_updates=True
        )

        # Запускаємо отримання оновлень
        await app.updater.start_polling()

        print("БОТ УСПІШНО ЗАПУЩЕНИЙ")

        await asyncio.Event().wait()

    asyncio.run(run())


# ============================================================
# ТОЧКА ВХОДУ
# ============================================================

if __name__ == "__main__":

    try:
        main()

    except KeyboardInterrupt:

        logging.info("Бота зупинено користувачем.")

    finally:

        try:
            db.commit()
            db.close()

        except Exception:
            pass
