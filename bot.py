import sqlite3
import logging
import asyncio
from datetime import datetime, timedelta

from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ChatMemberHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
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
import sqlite3
import logging
from datetime import datetime


TOKEN = os.getenv(
    "BOT_TOKEN",
    "8835839482:AAFQ0yWwNdZ7dHUzJKPernaOVo_HMUNL24g"
)


ADMINS = [
    929200380,
    395523040
]


DATABASE = "telegram_stats.db"


logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
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
            (
                chat.id,
                chat.title
            )
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
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            )
        )

        conn.commit()



# ============================================================
# ПЕРЕВІРКА БАЗИ
# ============================================================


def check_db():

    with sqlite3.connect(DATABASE) as conn:

        tables = conn.execute(
            """
            SELECT name 
            FROM sqlite_master
            WHERE type='table'
            """
        ).fetchall()


    print(
        "Таблиці SQLite:",
        tables
    )
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
        CREATE TABLE IF NOT EXISTS groups(
            group_id INTEGER PRIMARY KEY,
            title TEXT
        )
        """)


        conn.execute("""
        CREATE TABLE IF NOT EXISTS events(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER,
            user_id INTEGER,
            username TEXT,
            first_name TEXT,
            action TEXT,
            event_time TEXT
        )
        """)


        conn.execute("""
        CREATE TABLE IF NOT EXISTS last_broadcast(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL
        )
        """)


        conn.commit()


    print("✅ База данных готова")


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
    "/excel — експорт Excel\n"
    "/broadcast — розсилка\n"
    "/deletebroadcast — видалити останню розсилку\n"
    "/del — видалити переслане повідомлення"
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

        # Кількість учасників
        try:
            members = await context.bot.get_chat_member_count(group_id)
        except Exception:
            members = "Невідомо"

        # Приріст
        growth = total_join - total_leave

        if isinstance(growth, int):
            growth_text = f"+{growth}" if growth >= 0 else str(growth)
        else:
            growth_text = "Невідомо"

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

            f"👥 <b>Учасників:</b> {members}\n"
            f"📈 <b>Приріст:</b> {growth_text}\n\n"

            f"📊 <b>Загалом</b>\n"
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

async def save_group(update: Update):

    if update.effective_chat.type not in ("group", "supergroup"):
        return

    conn = sqlite3.connect("statistics.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS groups(
        chat_id INTEGER PRIMARY KEY,
        title TEXT
    )
    """)

    cursor.execute(
        """
        INSERT OR REPLACE INTO groups(chat_id,title)
        VALUES(?,?)
        """,
        (
            update.effective_chat.id,
            update.effective_chat.title
        )
    )

    conn.commit()
    conn.close()

    conn.execute("""
CREATE TABLE IF NOT EXISTS last_broadcast (
    group_id INTEGER PRIMARY KEY,
    message_id INTEGER
)
""")
# ============================================================
# СИСТЕМА РОЗСИЛКИ З ПІДТВЕРДЖЕННЯМ
# ============================================================

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

# Користувачі, які зараз створюють розсилку
broadcast_wait = {}

# Збережене повідомлення
broadcast_message = {}

# Повідомлення для ручного видалення
delete_message_cache = {}


# ============================================================
# КОМАНДА /broadcast
# ============================================================

async def broadcast(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not is_admin(update.effective_user.id):
        return

    broadcast_wait[update.effective_user.id] = True

    await update.message.reply_text(
        "📨 Надішліть повідомлення для розсилки.\n\n"
        "Можна відправити:\n"
        "• текст\n"
        "• фото\n"
        "• відео\n"
        "• GIF\n"
        "• документ\n\n"
        "Після цього бот покаже попередній перегляд."
    )


# ============================================================
# ОТРИМАННЯ ПОВІДОМЛЕННЯ
# ============================================================

async def receive_broadcast(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    user_id = update.effective_user.id

    if user_id not in broadcast_wait:
        return

    del broadcast_wait[user_id]

    broadcast_message[user_id] = (
        update.effective_chat.id,
        update.message.message_id,
    )

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ Відправити",
                    callback_data="broadcast_send",
                ),
                InlineKeyboardButton(
                    "❌ Скасувати",
                    callback_data="broadcast_cancel",
                ),
            ]
        ]
    )

    await update.message.reply_text(
        "👆 Попередній перегляд повідомлення вище.\n\n"
        "Підтвердити розсилку?",
        reply_markup=keyboard,
    )
    from telegram.ext import CallbackQueryHandler, MessageHandler, filters
# ============================================================
# КНОПКИ ПІДТВЕРДЖЕННЯ РОЗСИЛКИ
# ============================================================

async def broadcast_buttons(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    # ----------------------------
    # Скасування
    # ----------------------------

    if query.data == "broadcast_cancel":

        if user_id in broadcast_message:
            del broadcast_message[user_id]

        await query.edit_message_text(
            "❌ Розсилку скасовано."
        )

        return

    # ----------------------------
    # Відправка
    # ----------------------------

    if query.data != "broadcast_send":
        return

    if user_id not in broadcast_message:

        await query.edit_message_text(
            "❌ Повідомлення не знайдено."
        )

        return

    from_chat_id, message_id = broadcast_message[user_id]

    groups = get_groups()

    sent = 0
    failed = 0

        # ----------------------------
    # Відправка
    # ----------------------------

    if query.data != "broadcast_send":
        return


    if user_id not in broadcast_message:

        await query.edit_message_text(
            "❌ Повідомлення не знайдено."
        )

        return


    from_chat_id, message_id = broadcast_message[user_id]


    groups = get_groups()

    sent = 0
    failed = 0


    for group_id, title in groups:

        try:

            msg = await context.bot.copy_message(
                chat_id=group_id,
                from_chat_id=from_chat_id,
                message_id=message_id,
            )


            # Зберігаємо ID відправленого повідомлення
            with sqlite3.connect(DATABASE) as conn:

                conn.execute(
                    """
                    INSERT INTO last_broadcast(
                        group_id,
                        message_id
                    )
                    VALUES (?,?)
                    """,
                    (
                        group_id,
                        msg.message_id
                    )
                )

                conn.commit()


            sent += 1


        except Exception as e:

            print(
                f"{title}: {e}"
            )

            failed += 1



    # Видаляємо тимчасове повідомлення
    del broadcast_message[user_id]


    await query.edit_message_text(
        f"""
✅ Розсилку завершено

📨 Надіслано: {sent}
❌ Помилок: {failed}
📂 Всього груп: {len(groups)}
"""
    )

# ============================================================
# УДАЛЕНИЕ ПО CHAT_ID И MESSAGE_ID
# ============================================================

async def delete_by_id(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not is_admin(update.effective_user.id):
        return


    if len(context.args) != 2:

        await update.message.reply_text(
            "❌ Формат:\n"
            "/delete_id CHAT_ID MESSAGE_ID\n\n"
            "Пример:\n"
            "/delete_id -1001234567890 456"
        )

        return


    try:

        chat_id = int(context.args[0])
        message_id = int(context.args[1])


        await context.bot.delete_message(
            chat_id=chat_id,
            message_id=message_id
        )


        await update.message.reply_text(
            "🗑 Сообщение удалено."
        )


    except Exception as e:

        print(
            "Ошибка удаления:",
            e
        )


        await update.message.reply_text(
            f"❌ Ошибка:\n{e}"
        )
# ============================================================
# ВИДАЛЕННЯ ОСТАННЬОЇ РОЗСИЛКИ
# ============================================================

async def deletebroadcast(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not is_admin(update.effective_user.id):
        return

    with sqlite3.connect(DATABASE) as conn:

        rows = conn.execute(
            """
            SELECT group_id, message_id
            FROM last_broadcast
            """
        ).fetchall()

    if not rows:

        await update.message.reply_text(
            "Немає повідомлень для видалення."
        )

        return

    deleted = 0
    failed = 0

    for group_id, message_id in rows:

        try:

            await context.bot.delete_message(
                chat_id=group_id,
                message_id=message_id
            )

            deleted += 1

        except Exception as e:

            print(e)

            failed += 1

    with sqlite3.connect(DATABASE) as conn:
        conn.execute("DELETE FROM last_broadcast")
        conn.commit()

    await update.message.reply_text(
        f"""
🗑 Розсилку видалено

✅ Видалено: {deleted}
❌ Помилок: {failed}
"""
    )
# ============================================================
# ОБРОБНИК ПОМИЛОК
# ============================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):
    logging.error(
        "Помилка:",
        exc_info=context.error
    )

# ============================================================
# УДАЛЕНИЕ ПЕРЕСЛАННОГО СООБЩЕНИЯ
# ============================================================

async def delete_forwarded_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    user_id = update.effective_user.id


    if not is_admin(user_id):
        return


    if user_id not in delete_message_cache:

        await update.message.reply_text(
            "❌ Сначала перешли сообщение."
        )

        return


    chat_id, message_id = delete_message_cache[user_id]


    try:

        await context.bot.delete_message(
            chat_id=chat_id,
            message_id=message_id
        )


        await update.message.reply_text(
            "🗑 Сообщение удалено."
        )


        del delete_message_cache[user_id]


    except Exception as e:

        print(e)

        await update.message.reply_text(
            f"❌ Ошибка удаления:\n{e}"
        )

# ============================================================
# ЗАПУСК БОТА
# ============================================================

def main():

    # Создаем таблицы
    init_db()

    # Проверяем базу
    check_db()


    app = (
        Application.builder()
        .token(TOKEN)
        .build()
    )


    app.add_error_handler(
        error_handler
    )


    # ========================================================
    # Команди
    # ========================================================

    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    app.add_handler(
        CommandHandler(
            "groups",
            groups
        )
    )

    app.add_handler(
        CommandHandler(
            "stats",
            stats
        )
    )

    app.add_handler(
        CommandHandler(
            "addgroup",
            addgroup
        )
    )

    app.add_handler(
        CommandHandler(
            "excel",
            excel
        )
    )

    app.add_handler(
        CommandHandler(
            "broadcast",
            broadcast
        )
    )

    app.add_handler(
        CommandHandler(
            "deletebroadcast",
            deletebroadcast
        )
    )

    app.add_handler(
    CommandHandler(
        "delete_id",
        delete_by_id
    )
)


    # ========================================================
    # Получение сообщения для рассылки
    # ========================================================


    app.add_handler(
        MessageHandler(
            ~filters.COMMAND & ~filters.FORWARDED,
            receive_broadcast
        )
    )


    # ========================================================
    # Кнопки подтверждения рассылки
    # ========================================================

    app.add_handler(
        CallbackQueryHandler(
            broadcast_buttons
        )
    )


    # ========================================================
    # Вход / выход участников
    # ========================================================

    app.add_handler(
        ChatMemberHandler(
            chat_member_update,
            ChatMemberHandler.CHAT_MEMBER
        )
    )


    print(
        "🤖 БОТ УСПІШНО ЗАПУЩЕНИЙ"
    )


    # Запуск
    app.run_polling(
        drop_pending_updates=True
    )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    main()

    # ========================================================
    # Отримання тексту для розсилки
    # ========================================================

    MessageHandler(
    filters.FORWARDED & ~filters.COMMAND,
    save_delete_message,
)
    MessageHandler(
    ~filters.COMMAND & ~filters.FORWARDED,
    receive_broadcast,
)

    # ========================================================
    # Кнопки підтвердження
    # ========================================================

    app.add_handler(
        CallbackQueryHandler(
            broadcast_buttons
        )
    )


    # ========================================================
    # Вхід / вихід учасників
    # ========================================================

    app.add_handler(
        ChatMemberHandler(
            chat_member_update,
            ChatMemberHandler.CHAT_MEMBER
        )
    )


    print("БОТ УСПІШНО ЗАПУЩЕНИЙ")


    # Запуск
    app.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()

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
