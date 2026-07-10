import logging
import json
import os
from datetime import datetime, date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler,
    filters, ContextTypes,
)

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = "8850297429:AAG3lbtnAfVi0lbidt_oLHjdsRo7TMsoazM"
COLLECTING_TASKS = 1
SETTING_REMINDER = 2
DATA_FILE = "user_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_user_data(user_id):
    all_data = load_data()
    uid = str(user_id)
    if uid not in all_data:
        all_data[uid] = {"tasks": [], "history": {}, "reminder_hour": None, "weekly_stats": {}}
        save_data(all_data)
    return all_data[uid]

def save_user_data(user_id, user_data):
    all_data = load_data()
    all_data[str(user_id)] = user_data
    save_data(all_data)

PRIORITY_EMOJI = {"high": "🔴", "medium": "🟡", "low": "🟢"}
PRIORITY_LABEL = {"high": "مهم", "medium": "معمولی", "low": "کم‌اهمیت"}

def build_task_list_message(tasks):
    if not tasks:
        return "📋 هیچ کاری ثبت نشده است."
    done = [t for t in tasks if t["done"]]
    pending = [t for t in tasks if not t["done"]]
    lines = ["📊 *وضعیت کارهای امروز*\n"]
    if pending:
        lines.append("⏳ *کارهای باقی‌مانده:*")
        for t in tasks:
            if not t["done"]:
                p = PRIORITY_EMOJI.get(t.get("priority", "medium"), "🟡")
                lines.append(f"  {p} {t['name']}")
        lines.append("")
    if done:
        lines.append("✅ *کارهای انجام‌شده:*")
        for t in done:
            p = PRIORITY_EMOJI.get(t.get("priority", "medium"), "🟡")
            lines.append(f"  ✔️ {p} ~{t['name']}~")
        lines.append("")
    total = len(tasks)
    done_count = len(done)
    percent = int((done_count / total) * 100) if total > 0 else 0
    bar_filled = int(percent / 10)
    bar = "🟩" * bar_filled + "⬜" * (10 - bar_filled)
    lines.append(f"📈 پیشرفت: {bar}")
    lines.append(f"*{done_count} از {total} کار انجام شده ({percent}%)*")
    if done_count == total and total > 0:
        lines.append("\n🎉 *آفرین! همه کارها انجام شد!*")
    return "\n".join(lines)

def build_task_keyboard(tasks):
    keyboard = []
    for i, task in enumerate(tasks):
        if not task["done"]:
            p = PRIORITY_EMOJI.get(task.get("priority", "medium"), "🟡")
            keyboard.append([InlineKeyboardButton(f"✅ {p} {task['name']}", callback_data=f"done_{i}")])
    keyboard.append([
        InlineKeyboardButton("🔄 شروع مجدد", callback_data="restart"),
        InlineKeyboardButton("📋 وضعیت", callback_data="status"),
    ])
    keyboard.append([
        InlineKeyboardButton("📅 تاریخچه", callback_data="history"),
        InlineKeyboardButton("📊 آمار هفتگی", callback_data="weekly"),
    ])
    return InlineKeyboardMarkup(keyboard)

def build_priority_keyboard(task_index):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔴 مهم", callback_data=f"priority_{task_index}_high")],
        [InlineKeyboardButton("🟡 معمولی", callback_data=f"priority_{task_index}_medium")],
        [InlineKeyboardButton("🟢 کم‌اهمیت", callback_data=f"priority_{task_index}_low")],
    ])

def save_today_to_history(user_id):
    user_data = get_user_data(user_id)
    today = date.today().isoformat()
    tasks = user_data["tasks"]
    if not tasks:
        return
    total = len(tasks)
    done = len([t for t in tasks if t["done"]])
    percent = int((done / total) * 100) if total > 0 else 0
    user_data["history"][today] = {"total": total, "done": done, "percent": percent, "tasks": tasks.copy()}
    week = date.today().isocalendar()[1]
    year = date.today().year
    week_key = f"{year}-W{week}"
    if week_key not in user_data["weekly_stats"]:
        user_data["weekly_stats"][week_key] = {"total_tasks": 0, "done_tasks": 0, "days": 0}
    user_data["weekly_stats"][week_key]["total_tasks"] += total
    user_data["weekly_stats"][week_key]["done_tasks"] += done
    user_data["weekly_stats"][week_key]["days"] += 1
    save_user_data(user_id, user_data)

async def start(update, context):
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    if user_data["tasks"]:
        save_today_to_history(user_id)
    user_data["tasks"] = []
    save_user_data(user_id, user_data)
    await update.message.reply_text(
        "👋 سلام! خوش اومدی به ربات مدیریت کارهای روزانه!\n\n"
        "📝 *کارهایی که امروز میخوای انجام بدی رو بنویس.*\n"
        "هر کار رو در یک پیام جداگانه بفرست.\n\n"
        "⬇️ وقتی همه کارها رو نوشتی، /done بزن.",
        parse_mode="Markdown"
    )
    return COLLECTING_TASKS

async def collect_task(update, context):
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    task_name = update.message.text.strip()
    if task_name:
        task_index = len(user_data["tasks"])
        user_data["tasks"].append({"name": task_name, "done": False, "priority": "medium"})
        save_user_data(user_id, user_data)
        await update.message.reply_text(
            f"✅ کار ثبت شد: *{task_name}*\n\nاولویتش رو انتخاب کن:",
            parse_mode="Markdown",
            reply_markup=build_priority_keyboard(task_index)
        )
    return COLLECTING_TASKS

async def finish_collecting(update, context):
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    if not user_data["tasks"]:
        await update.message.reply_text("⚠️ هنوز هیچ کاری وارد نکردی!\nلطفاً حداقل یک کار بنویس.")
        return COLLECTING_TASKS
    message = build_task_list_message(user_data["tasks"])
    keyboard = build_task_keyboard(user_data["tasks"])
    await update.message.reply_text(
        f"🚀 *شروع کار!*\n\n{message}\n\n👇 کارهایی که انجام دادی رو بزن:",
        parse_mode="Markdown",
        reply_markup=keyboard
    )
    return ConversationHandler.END

async def button_callback(update, context):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user_data = get_user_data(user_id)

    if query.data.startswith("priority_"):
        parts = query.data.split("_")
        task_index = int(parts[1])
        priority = parts[2]
        if 0 <= task_index < len(user_data["tasks"]):
            user_data["tasks"][task_index]["priority"] = priority
            save_user_data(user_id, user_data)
            await query.edit_message_text(
                f"{PRIORITY_EMOJI[priority]} کار *{user_data['tasks'][task_index]['name']}* با اولویت *{PRIORITY_LABEL[priority]}* ثبت شد!\n\n📝 کار بعدی رو بنویس یا /done بزن.",
                parse_mode="Markdown"
            )

    elif query.data.startswith("done_"):
        task_index = int(query.data.split("_")[1])
        if 0 <= task_index < len(user_data["tasks"]):
            task_name = user_data["tasks"][task_index]["name"]
            user_data["tasks"][task_index]["done"] = True
            save_user_data(user_id, user_data)
            message = build_task_list_message(user_data["tasks"])
            pending = [t for t in user_data["tasks"] if not t["done"]]
            keyboard = build_task_keyboard(user_data["tasks"])
            await query.edit_message_text(
                f"✅ *\"{task_name}\"* انجام شد! 💪\n\n{message}" + ("\n\n👇 کارهای بعدی رو تیک بزن:" if pending else ""),
                parse_mode="Markdown",
                reply_markup=keyboard if pending else InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔄 شروع روز جدید", callback_data="restart"),
                    InlineKeyboardButton("📊 آمار هفتگی", callback_data="weekly"),
                ]])
            )

    elif query.data == "status":
        await query.edit_message_text(build_task_list_message(user_data["tasks"]), parse_mode="Markdown", reply_markup=build_task_keyboard(user_data["tasks"]))

    elif query.data == "history":
        history = user_data.get("history", {})
        if not history:
            await query.edit_message_text("📅 هنوز تاریخچه‌ای ثبت نشده.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data="status")]]))
            return
        lines = ["📅 *تاریخچه ۷ روز اخیر:*\n"]
        for day in sorted(history.keys(), reverse=True)[:7]:
            h = history[day]
            bar = "🟩" * int(h["percent"] / 10) + "⬜" * (10 - int(h["percent"] / 10))
            lines.append(f"📆 {day}\n  {bar} {h['percent']}%\n  ✅ {h['done']} از {h['total']} کار\n")
        await query.edit_message_text("\n".join(lines), parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data="status")]]))

    elif query.data == "weekly":
        weekly = user_data.get("weekly_stats", {})
        if not weekly:
            await query.edit_message_text("📊 هنوز آمار هفتگی ثبت نشده.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data="status")]]))
            return
        lines = ["📊 *آمار هفتگی:*\n"]
        for week_key in sorted(weekly.keys(), reverse=True)[:4]:
            w = weekly[week_key]
            percent = int((w["done_tasks"] / w["total_tasks"]) * 100) if w["total_tasks"] > 0 else 0
            bar = "🟩" * int(percent / 10) + "⬜" * (10 - int(percent / 10))
            lines.append(f"🗓 هفته {week_key}\n  {bar} {percent}%\n  ✅ {w['done_tasks']} از {w['total_tasks']} کار در {w['days']} روز\n")
        await query.edit_message_text("\n".join(lines), parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data="status")]]))

    elif query.data == "restart":
        save_today_to_history(user_id)
        await query.edit_message_text("🔄 برای شروع روز جدید /start بزن.")

async def reminder_command(update, context):
    await update.message.reply_text(
        "⏰ *تنظیم یادآوری روزانه*\n\nساعت مورد نظر رو بنویس.\nمثال: `20` (برای ساعت ۸ شب)\n\nبرای لغو /cancel بزن.",
        parse_mode="Markdown"
    )
    return SETTING_REMINDER

async def set_reminder(update, context):
    user_id = update.effective_user.id
    try:
        hour = int(update.message.text.strip())
        if not 0 <= hour <= 23:
            raise ValueError
        user_data = get_user_data(user_id)
        user_data["reminder_hour"] = hour
        save_user_data(user_id, user_data)
        context.job_queue.run_daily(
            send_reminder,
            time=datetime.now().replace(hour=hour, minute=0, second=0).time(),
            chat_id=update.effective_chat.id,
            name=f"reminder_{user_id}",
            data=user_id
        )
        await update.message.reply_text(f"✅ یادآوری روزانه ساعت *{hour}:00* تنظیم شد! ⏰", parse_mode="Markdown")
    except ValueError:
        await update.message.reply_text("⚠️ عدد بین ۰ تا ۲۳ وارد کن.")
        return SETTING_REMINDER
    return ConversationHandler.END

async def send_reminder(context):
    user_id = context.job.data
    user_data = get_user_data(user_id)
    pending = [t for t in user_data.get("tasks", []) if not t["done"]]
    if pending:
        lines = ["⏰ *یادآوری روزانه!*\n", f"هنوز {len(pending)} کار باقی مونده:\n"]
        for t in pending:
            lines.append(f"  {PRIORITY_EMOJI.get(t.get('priority', 'medium'), '🟡')} {t['name']}")
        lines.append("\n💪 بریم انجامشون بدیم!")
        await context.bot.send_message(chat_id=context.job.chat_id, text="\n".join(lines), parse_mode="Markdown")

async def status_command(update, context):
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    if not user_data["tasks"]:
        await update.message.reply_text("📋 هنوز کاری ثبت نشده.\n/start بزن تا شروع کنیم!")
        return
    await update.message.reply_text(build_task_list_message(user_data["tasks"]), parse_mode="Markdown", reply_markup=build_task_keyboard(user_data["tasks"]))

async def cancel(update, context):
    await update.message.reply_text("❌ لغو شد.")
    return ConversationHandler.END

async def help_command(update, context):
    await update.message.reply_text(
        "📖 *راهنمای ربات*\n\n"
        "🟢 /start — شروع و وارد کردن کارهای امروز\n"
        "✅ /done — اتمام وارد کردن کارها\n"
        "📋 /status — نمایش وضعیت کارها\n"
        "⏰ /reminder — تنظیم یادآوری روزانه\n"
        "❓ /help — این راهنما\n\n"
        "🔴 مهم | 🟡 معمولی | 🟢 کم‌اهمیت",
        parse_mode="Markdown"
    )

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    task_conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={COLLECTING_TASKS: [
            CommandHandler("done", finish_collecting),
            MessageHandler(filters.TEXT & ~filters.COMMAND, collect_task),
        ]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    reminder_conv = ConversationHandler(
        entry_points=[CommandHandler("reminder", reminder_command)],
        states={SETTING_REMINDER: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, set_reminder),
        ]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(task_conv)
    app.add_handler(reminder_conv)
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("help", help_command))
    logger.info("ربات در حال اجرا است...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
