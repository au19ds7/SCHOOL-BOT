import asyncio
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Токен твого бота
TOKEN = "8952184969:AAHS21Naqs1Hmtvpvi7Eh-oNcclRZFCMj9Q"

# ID твого чату (або групи), куди бот має слати сповіщення
CHAT_ID = None 

# Змінна для керування статусом сповіщень (увімкнено за замовчуванням)
NOTIFICATIONS_ENABLED = True

bot = Bot(token=TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler(timezone="Europe/Kiev")

# Словники та бази даних в пам'яті
reminders_list = []      # Список активних та виконаних нагадувань
user_creation_step = {}  # Тимчасове збереження кроків створення нагадування

# Функція для визначення поточного тижня (1 або 2) за номером тижня року
def get_current_week():
    week_number = datetime.now().isocalendar()[1]
    return 1 if week_number % 2 != 0 else 2

# НОВИЙ РОЗКЛАД УРОКІВ (Формат: [Урок 1 тижня, Урок 2 тижня])
# Якщо предмет один, обидва значення однакові.

MONDAY_SCHEDULE = {
    "1": {"time": "08:30 - 09:15", "name": ["Англ. мова", "Англ. мова"]},
    "2": {"time": "09:25 - 10:10", "name": ["Хімія", "Хімія"]},
    "3": {"time": "10:25 - 11:10", "name": ["Укр. мова", "Укр. мова"]},
    "4": {"time": "11:30 - 12:15", "name": ["Ф-ра", "Ф-ра"]},
    "5": {"time": "12:35 - 13:20", "name": ["Фізика", "Фізика"]},
    "6": {"time": "13:30 - 14:15", "name": ["Зарубіжна", "Зарубіжна"]},
    "7": {"time": "14:25 - 15:10", "name": ["Фізика 2х", "Фізика 2х"]}
}

TUESDAY_SCHEDULE = {
    "1": {"time": "08:30 - 09:15", "name": ["Англ.", "Матем. ат."]},
    "2": {"time": "09:25 - 10:10", "name": ["Укр. мова", "Укр. мова"]},
    "3": {"time": "10:25 - 11:10", "name": ["Матем. а.", "Матем. а."]},
    "4": {"time": "11:30 - 12:15", "name": ["Історія", "Історія"]},
    "5": {"time": "12:35 - 13:20", "name": ["Інфор.", "Інфор."]},
    "6": {"time": "13:30 - 14:15", "name": ["Технології", "Технології"]},
    "7": {"time": "14:25 - 15:10", "name": ["Біологія", "Біологія"]},
    "8": {"time": "15:20 - 16:05", "name": ["Мист.", "Мист."]}
}

WEDNESDAY_SCHEDULE = {
    "1": {"time": "08:30 - 09:15", "name": ["Англ. мова", "Англ. мова"]},
    "2": {"time": "09:25 - 10:10", "name": ["Укр. мова", "Польська"]},
    "3": {"time": "10:25 - 11:10", "name": ["Фізика", "Фізика"]},
    "4": {"time": "11:30 - 12:15", "name": ["Ф-ра", "Ф-ра"]},
    "5": {"time": "12:35 - 13:20", "name": ["Укр. мова", "Польська"]},
    "6": {"time": "13:30 - 14:15", "name": ["Матем. геом.", "Матем. геом."]},
    "7": {"time": "14:25 - 15:10", "name": ["Укр. літ.", "Укр. літ."]}
}

THURSDAY_SCHEDULE = {
    "1": {"time": "08:30 - 09:15", "name": ["ЗБД / ПРГ", "ЗБД / ПРГ"]},
    "2": {"time": "09:25 - 10:10", "name": ["Ф-ра", "Ф-ра"]},
    "3": {"time": "10:25 - 11:10", "name": ["Англ. мова", "Англ. мова"]},
    "4": {"time": "11:30 - 12:15", "name": ["Математика а.", "Математика а."]},
    "5": {"time": "12:35 - 13:20", "name": ["Історія", "Історія"]},
    "6": {"time": "13:30 - 14:15", "name": ["Інфор. / Історія", "Інфор. / Історія"]},
    "7": {"time": "14:25 - 15:10", "name": ["Матем. ат.", "Матем. ат."]}
}

FRIDAY_SCHEDULE = {
    "1": {"time": "08:30 - 09:15", "name": ["Хімія", "Хімія"]},
    "2": {"time": "09:25 - 10:10", "name": ["Укр. мова", "Польська"]},
    "3": {"time": "10:25 - 11:10", "name": ["Біологія", "Біологія"]},
    "4": {"time": "11:30 - 12:15", "name": ["Укр. мова", "Польська"]},
    "5": {"time": "12:35 - 13:20", "name": ["Історія", "Історія"]},
    "6": {"time": "13:30 - 14:15", "name": ["Географія", "Географія"]},
    "7": {"time": "14:25 - 15:10", "name": ["Укр. літ.", "Укр. літ."]}
}

# Головне меню
def get_main_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="📅 Подивитися розклад", callback_data="show_schedule_menu")
    builder.button(text="⏰ Нагадування", callback_data="show_reminders")
    
    notif_text = "🔕 Вимкнути сповіщення" if NOTIFICATIONS_ENABLED else "🔔 Увімкнути сповіщення"
    builder.button(text=notif_text, callback_data="toggle_notifications")
    
    builder.adjust(1, 2)
    return builder.as_markup()

# Меню вибору днів тижня для розкладу
def get_days_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="Понеділок", callback_data="day_monday")
    builder.button(text="Вівторок", callback_data="day_tuesday")
    builder.button(text="Середа", callback_data="day_wednesday")
    builder.button(text="Четвер", callback_data="day_thursday")
    builder.button(text="П'ятниця", callback_data="day_friday")
    builder.button(text="⬅️ Назад у меню", callback_data="back_to_main")
    builder.adjust(2, 2, 1, 1)
    return builder.as_markup()

@dp.message(Command("start"))
async def cmd_start(message: Message):
    global CHAT_ID
    CHAT_ID = message.chat.id
    status = "увімкнені ✅" if NOTIFICATIONS_ENABLED else "вимкнені ❌"
    await message.answer(
        f"Привіт! Я твій шкільний бот-помічник.\nПоточні сповіщення: {status}",
        reply_markup=get_main_keyboard()
    )

@dp.callback_query(F.data == "back_to_main")
async def process_back_to_main(callback: CallbackQuery):
    status = "увімкнені ✅" if NOTIFICATIONS_ENABLED else "вимкнені ❌"
    await callback.message.edit_text(
        f"Головне меню:\nПоточні сповіщення: {status}",
        reply_markup=get_main_keyboard()
    )
    await callback.answer()

@dp.callback_query(F.data == "toggle_notifications")
async def process_toggle_notifications(callback: CallbackQuery):
    global NOTIFICATIONS_ENABLED
    NOTIFICATIONS_ENABLED = not NOTIFICATIONS_ENABLED
    status = "увімкнені ✅" if NOTIFICATIONS_ENABLED else "вимкнені ❌"
    
    await callback.message.edit_text(
        f"Головне меню:\nСповіщення тепер {status}",
        reply_markup=get_main_keyboard()
    )
    await callback.answer("Статус сповіщень змінено!")

# --- РОЗДІЛ НАГАДУВАНЬ ---

@dp.callback_query(F.data == "show_reminders")
async def process_reminders_menu(callback: CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Створити нагадування", callback_data="create_reminder")
    
    active_text = "📌 **Активні нагадування:**\n"
    active_items = [r for r in reminders_list if not r['done']]
    if not active_items:
        active_text += "_Немає активних нагадувань_\n"
    else:
        for item in active_items:
            active_text += f"• {item['text']} (📅 {item['day_name']} о {item['time']})\n"
            builder.button(text=f"✅ Виконати: {item['text'][:15]}...", callback_data=f"done_rem_{item['id']}")

    done_text = "\n📋 **Виконані нагадування:**\n"
    done_items = [r for r in reminders_list if r['done']]
    if not done_items:
        done_text += "_Поки що нічого не виконано_\n"
    else:
        for item in done_items:
            done_text += f"✔️ ~~{item['text']}~~\n"

    builder.button(text="⬅️ Назад у меню", callback_data="back_to_main")
    builder.adjust(1)
    
    await callback.message.edit_text(
        active_text + done_text,
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data == "create_reminder")
async def process_create_reminder(callback: CallbackQuery):
    user_creation_step[callback.from_user.id] = {"step": "waiting_text"}
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Скасувати", callback_data="show_reminders")
    
    await callback.message.edit_text(
        "✍️ **Напишіть, що ви хочете нагадати:**",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )
    await callback.answer()

def get_reminder_days_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="Понеділок", callback_data="rem_day_mon")
    builder.button(text="Вівторок", callback_data="rem_day_tue")
    builder.button(text="Середа", callback_data="rem_day_wed")
    builder.button(text="Четвер", callback_data="rem_day_thu")
    builder.button(text="П'ятниця", callback_data="rem_day_fri")
    builder.button(text="Субота", callback_data="rem_day_sat")
    builder.button(text="Неділя", callback_data="rem_day_sun")
    builder.button(text="❌ Скасувати", callback_data="show_reminders")
    builder.adjust(2, 2, 2, 1, 1)
    return builder.as_markup()

@dp.callback_query(F.data.startswith("rem_day_"))
async def process_reminder_day_chosen(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in user_creation_step:
        await callback.message.edit_text("Помилка. Спробуйте знову.", reply_markup=get_main_keyboard())
        return
    
    day_code = callback.data.split("_")[2]
    days_map = {
        "mon": ("Понеділок", "mon"),
        "tue": ("Вівторок", "tue"),
        "wed": ("Середа", "wed"),
        "thu": ("Четвер", "thu"),
        "fri": ("П'ятниця", "fri"),
        "sat": ("Субота", "sat"),
        "sun": ("Неділя", "sun")
    }
    
    user_creation_step[user_id]["day_name"] = days_map[day_code][0]
    user_creation_step[user_id]["day_cron"] = days_map[day_code][1]
    user_creation_step[user_id]["step"] = "waiting_time"
    
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Скасувати", callback_data="show_reminders")

    await callback.message.edit_text(
        f"📅 День обрано: **{days_map[day_code][0]}**\n\n⏰ **Тепер напишіть годину у форматі Година:Хвилина (наприклад: 14:30 або 08:15):**",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("done_rem_"))
async def process_mark_done(callback: CallbackQuery):
    rem_id = int(callback.data.split("_")[2])
    for item in reminders_list:
        if item['id'] == rem_id:
            item['done'] = True
    await process_reminders_menu(callback)

@dp.message(F.text & ~F.text.startswith("/"))
async def handle_text_inputs(message: Message):
    user_id = message.from_user.id
    if user_id not in user_creation_step:
        return
    
    state = user_creation_step[user_id]
    
    if state["step"] == "waiting_text":
        state["text"] = message.text
        state["step"] = "waiting_day"
        
        await message.answer(
            "📌 **Коли нагадати?**\nОберіть день тижня:",
            reply_markup=get_reminder_days_keyboard(),
            parse_mode="Markdown"
        )
        
    elif state["step"] == "waiting_time":
        time_text = message.text.strip()
        try:
            hour_str, minute_str = time_text.split(":")
            hour = int(hour_str)
            minute = int(minute_str)
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError()
        except:
            await message.answer("❌ Неправильний формат часу. Введіть у форматі Година:Хвилина, наприклад `14:30`:", parse_mode="Markdown")
            return
        
        rem_id = len(reminders_list) + 1
        new_reminder = {
            "id": rem_id,
            "text": state["text"],
            "day_name": state["day_name"],
            "time": time_text,
            "done": False
        }
        reminders_list.append(new_reminder)
        
        scheduler.add_job(
            send_user_reminder,
            'cron',
            day_of_week=state["day_cron"],
            hour=hour,
            minute=minute,
            args=[rem_id]
        )
        
        del user_creation_step[user_id]
        
        builder = InlineKeyboardBuilder()
        builder.button(text="⏰ До нагадувань", callback_data="show_reminders")
        builder.button(text="🏠 Головне меню", callback_data="back_to_main")
        builder.adjust(1)
        
        await message.answer(
            f"✅ **Нагадування успішно створено!**\n\n📌 Що: {new_reminder['text']}\n📅 Коли: {new_reminder['day_name']} о {time_text}",
            reply_markup=builder,
            parse_mode="Markdown"
        )

async def send_user_reminder(rem_id: int):
    if not CHAT_ID or not NOTIFICATIONS_ENABLED:
        return
    
    for item in reminders_list:
        if item['id'] == rem_id and not item['done']:
            text = f"⏰ **Нагадування!**\n\n{item['text']}"
            await bot.send_message(CHAT_ID, text, parse_mode="Markdown")

# --- РОЗКЛАД УРОКІВ ---

@dp.callback_query(F.data == "show_schedule_menu")
async def process_schedule_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        "Обери день тижня:",
        reply_markup=get_days_keyboard()
    )
    await callback.answer()

async def show_schedule_text(callback: CallbackQuery, schedule_dict: dict, day_name: str):
    current_week = get_current_week()
    text = f"📅 **Розклад на {day_name}** (Зараз іде **{current_week}-й тиждень**):\n\n"
    
    for num, lesson in schedule_dict.items():
        # Вибираємо предмет залежно від тижня (індекс 0 для 1-го тижня, індекс 1 для 2-го)
        lesson_name = lesson['name'][0] if current_week == 1 else lesson['name'][1]
        text += f"🔹 **{num}. {lesson_name}** ({lesson['time']})\n\n"
    
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад до днів", callback_data="show_schedule_menu")
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "day_monday")
async def process_monday(callback: CallbackQuery):
    await show_schedule_text(callback, MONDAY_SCHEDULE, "понеділок")

@dp.callback_query(F.data == "day_tuesday")
async def process_tuesday(callback: CallbackQuery):
    await show_schedule_text(callback, TUESDAY_SCHEDULE, "вівторок")

@dp.callback_query(F.data == "day_wednesday")
async def process_wednesday(callback: CallbackQuery):
    await show_schedule_text(callback, WEDNESDAY_SCHEDULE, "середу")

@dp.callback_query(F.data == "day_thursday")
async def process_thursday(callback: CallbackQuery):
    await show_schedule_text(callback, THURSDAY_SCHEDULE, "четвер")

@dp.callback_query(F.data == "day_friday")
async def process_friday(callback: CallbackQuery):
    await show_schedule_text(callback, FRIDAY_SCHEDULE, "п'ятницю")

@dp.callback_query(F.data == "day_sat")
async def process_saturday(callback: CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад до днів", callback_data="show_schedule_menu")
    await callback.message.edit_text("📅 **Субота:** Вихідний день! 🏖️", reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer()

async def main():
    logging.basicConfig(level=logging.INFO)
    scheduler.start()
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
