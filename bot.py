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

# Розклад на вівторок (з учителями)
TUESDAY_SCHEDULE = {
    "1": {"time": "08:30 - 09:15", "name": "Алгебра", "teacher": "Оксана Миколаївна"},
    "2": {"time": "09:25 - 10:10", "name": "Українська мова", "teacher": "Ольга Степанівна"},
    "3": {"time": "10:25 - 11:10", "name": "Алгебра", "teacher": "Оксана Миколаївна"},
    "4": {"time": "11:30 - 12:15", "name": "Всесвітня історія", "teacher": "Іванна Богданівна"},
    "5": {"time": "12:35 - 13:20", "name": "Інформатика", "teacher": "Оксана Миколаївна"},
    "6": {"time": "13:30 - 14:15", "name": "Технології", "teacher": "Іванна Петрівна"},
    "7": {"time": "14:25 - 15:10", "name": "Біологія", "teacher": "Надія Григорівна"},
    "8": {"time": "15:20 - 16:05", "name": "Мистецтво", "teacher": "Ірина Василівна"}
}

# Розклад на середу (з учителями)
WEDNESDAY_SCHEDULE = {
    "1": {"time": "08:30 - 09:15", "name": "Англійська мова", "teacher": "Галина Зиновіївна"},
    "2": {"time": "09:25 - 10:10", "name": "Українська мова", "teacher": "Ольга Степанівна"},
    "3": {"time": "10:25 - 11:10", "name": "Фізика", "teacher": "Ірина Володимирівна"},
    "4": {"time": "11:30 - 12:15", "name": "Вікно / Самостійна", "teacher": "-"},
    "5": {"time": "12:35 - 13:20", "name": "Польська мова", "teacher": "Людмила Петрівна"},
    "6": {"time": "13:30 - 14:15", "name": "Геометрія", "teacher": "Оксана Миколаївна"},
    "7": {"time": "14:25 - 15:10", "name": "Українська література", "teacher": "Наталія Вікторівна"}
}

# Розклад на четвер (з учителями)
THURSDAY_SCHEDULE = {
    "1": {"time": "08:30 - 09:15", "name": "Інтегрований курс \"Здоров'я, безпека та добробут\"", "teacher": "Надія Григорівна"},
    "2": {"time": "09:25 - 10:10", "name": "Вікно / Самостійна", "teacher": "-"},
    "3": {"time": "10:25 - 11:10", "name": "Англійська мова", "teacher": "Галина Зиновіївна"},
    "4": {"time": "11:30 - 12:15", "name": "Алгебра", "teacher": "Оксана Миколаївна"},
    "5": {"time": "12:35 - 13:20", "name": "Історія України", "teacher": "Іванна Богданівна"},
    "6": {"time": "13:30 - 14:15", "name": "Інформатика", "teacher": "Оксана Миколаївна"},
    "7": {"time": "14:25 - 15:10", "name": "Геометрія", "teacher": "Оксана Миколаївна"}
}

# Розклад на п'ятницю (з учителями)
FRIDAY_SCHEDULE = {
    "1": {"time": "08:30 - 09:15", "name": "Хімія", "teacher": "Володимир Леонідович"},
    "2": {"time": "09:25 - 10:10", "name": "Українська мова", "teacher": "Ольга Степанівна"},
    "3": {"time": "10:25 - 11:10", "name": "Біологія", "teacher": "Надія Григорівна"},
    "4": {"time": "11:30 - 12:15", "name": "Польська мова", "teacher": "Людмила Петрівна"},
    "5": {"time": "12:35 - 13:20", "name": "Вікно / Самостійна", "teacher": "-"},
    "6": {"time": "13:30 - 14:15", "name": "Географія", "teacher": "Тетяна Федорівна"},
    "7": {"time": "14:25 - 15:10", "name": "Українська література", "teacher": "Наталія Вікторівна"}
}

# Головне меню
def get_main_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="📅 Подивитися розклад", callback_data="show_schedule_menu")
    builder.button(text="📝 Нотатки", callback_data="show_notes")
    
    notif_text = "🔕 Вимкнути сповіщення" if NOTIFICATIONS_ENABLED else "🔔 Увімкнути сповіщення"
    builder.button(text=notif_text, callback_data="toggle_notifications")
    
    builder.adjust(1, 2)
    return builder.as_markup()

# Меню вибору днів тижня
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

@dp.callback_query(F.data == "show_notes")
async def process_notes(callback: CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад у меню", callback_data="back_to_main")
    
    await callback.message.edit_text(
        "📝 **Ваші нотатки:**\n\nТут поки що порожньо. Скоро сюди можна буде додавати домашні завдання чи важливі записи!",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data == "show_schedule_menu")
async def process_schedule_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        "Обери день тижня:",
        reply_markup=get_days_keyboard()
    )
    await callback.answer()

async def show_schedule_text(callback: CallbackQuery, schedule_dict: dict, day_name: str):
    text = f"📅 **Розклад на {day_name}:**\n\n"
    for num, lesson in schedule_dict.items():
        if lesson['teacher'] != "-":
            text += f"🔹 **{num}. {lesson['name']}** ({lesson['time']})\n   👤 _{lesson['teacher']}_\n\n"
        else:
            text += f"🔹 **{num}. {lesson['name']}** ({lesson['time']})\n\n"
    
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад до днів", callback_data="show_schedule_menu")
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer()

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

@dp.callback_query(F.data == "day_monday")
async def process_other_days(callback: CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад до днів", callback_data="show_schedule_menu")
    
    await callback.message.edit_text(
        "Цей день поки що не додано в розклад.",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

# Сповіщення про початок конкретного уроку
async def send_lesson_start_notification(day_schedule: dict, lesson_number: str):
    if not CHAT_ID or not NOTIFICATIONS_ENABLED:
        return
    
    lesson = day_schedule.get(lesson_number)
    if lesson and lesson['name'] != "Вікно / Самостійна":
        text = (
            f"🔔 **Урок {lesson_number}: {lesson['name']} почався!**\n\n"
            f"⏰ Час: {lesson['time']}\n"
            f"👤 Вчитель: {lesson['teacher']}"
        )
        await bot.send_message(CHAT_ID, text, parse_mode="Markdown")

# Сповіщення про кінець уроку
async def send_lesson_end_notification(day_schedule: dict, lesson_number: str):
    if not CHAT_ID or not NOTIFICATIONS_ENABLED:
        return
    
    lesson = day_schedule.get(lesson_number)
    if lesson and lesson['name'] != "Вікно / Самостійна":
        text = (
            f"🔕 **Урок {lesson_number}: {lesson['name']} закінчився!**"
        )
        await bot.send_message(CHAT_ID, text, parse_mode="Markdown")

# Налаштування розкладу подій
def setup_scheduler():
    tue_schedule_data = [
        ('8', '30', '9', '15', '1'),
        ('9', '25', '10', '10', '2'),
        ('10', '25', '11', '10', '3'),
        ('11', '30', '12', '15', '4'),
        ('12', '35', '13', '20', '5'),
        ('13', '30', '14', '15', '6'),
        ('14', '25', '15', '10', '7'),
        ('15', '20', '16', '05', '8')
    ]
    for start_h, start_m, end_h, end_m, num in tue_schedule_data:
        scheduler.add_job(send_lesson_start_notification, 'cron', day_of_week='tue', hour=start_h, minute=start_m, args=[TUESDAY_SCHEDULE, num])
        scheduler.add_job(send_lesson_end_notification, 'cron', day_of_week='tue', hour=end_h, minute=end_m, args=[TUESDAY_SCHEDULE, num])

    wed_schedule_data = [
        ('8', '30', '9', '15', '1'),
        ('9', '25', '10', '10', '2'),
        ('10', '25', '11', '10', '3'),
        ('11', '30', '12', '15', '4'),
        ('12', '35', '13', '20', '5'),
        ('13', '30', '14', '15', '6'),
        ('14', '25', '15', '10', '7')
    ]
    for start_h, start_m, end_h, end_m, num in wed_schedule_data:
        scheduler.add_job(send_lesson_start_notification, 'cron', day_of_week='wed', hour=start_h, minute=start_m, args=[WEDNESDAY_SCHEDULE, num])
        scheduler.add_job(send_lesson_end_notification, 'cron', day_of_week='wed', hour=end_h, minute=end_m, args=[WEDNESDAY_SCHEDULE, num])

    thu_schedule_data = [
        ('8', '30', '9', '15', '1'),
        ('9', '25', '10', '10', '2'),
        ('10', '25', '11', '10', '3'),
        ('11', '30', '12', '15', '4'),
        ('12', '35', '13', '20', '5'),
        ('13', '30', '14', '15', '6'),
        ('14', '25', '15', '10', '7')
    ]
    for start_h, start_m, end_h, end_m, num in thu_schedule_data:
        scheduler.add_job(send_lesson_start_notification, 'cron', day_of_week='thu', hour=start_h, minute=start_m, args=[THURSDAY_SCHEDULE, num])
        scheduler.add_job(send_lesson_end_notification, 'cron', day_of_week='thu', hour=end_h, minute=end_m, args=[THURSDAY_SCHEDULE, num])

    fri_schedule_data = [
        ('8', '30', '9', '15', '1'),
        ('9', '25', '10', '10', '2'),
        ('10', '25', '11', '10', '3'),
        ('11', '30', '12', '15', '4'),
        ('12', '35', '13', '20', '5'),
        ('13', '30', '14', '15', '6'),
        ('14', '25', '15', '10', '7')
    ]
    for start_h, start_m, end_h, end_m, num in fri_schedule_data:
        scheduler.add_job(send_lesson_start_notification, 'cron', day_of_week='fri', hour=start_h, minute=start_m, args=[FRIDAY_SCHEDULE, num])
        scheduler.add_job(send_lesson_end_notification, 'cron', day_of_week='fri', hour=end_h, minute=end_m, args=[FRIDAY_SCHEDULE, num])

async def main():
    logging.basicConfig(level=logging.INFO)
    setup_scheduler()
    scheduler.start()
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
