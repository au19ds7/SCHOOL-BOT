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

bot = Bot(token=TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler(timezone="Europe/Kiev")

# Розклад на вівторок (з точним часом дзвінків)
TUESDAY_SCHEDULE = {
    "1": {"time": "08:30 - 09:15", "name": "Алгебра", "room": "Кабінет основ здоров'я [5]"},
    "2": {"time": "09:25 - 10:10", "name": "Українська мова", "room": "Кабінет укр. мови [54]"},
    "3": {"time": "10:25 - 11:10", "name": "Алгебра", "room": "Кабінет основ здоров'я [5]"},
    "4": {"time": "11:30 - 12:15", "name": "Всесвітня історія", "room": "Архів школи [59]"},
    "5": {"time": "12:35 - 13:20", "name": "Інформатика", "room": "Кабінет інформатики [33]"},
    "6": {"time": "13:30 - 14:15", "name": "Технології", "room": "Майстерня по обробці дерева і металу [2]"},
    "7": {"time": "14:25 - 15:10", "name": "Біологія", "room": "Кабінет біології [7]"},
    "8": {"time": "15:20 - 16:05", "name": "Мистецтво", "room": "Архів школи [59]"}
}

# Розклад на середу
WEDNESDAY_SCHEDULE = {
    "1": {"time": "08:30 - 09:15", "name": "Англійська мова", "room": "Класна кімната 9-А [67]"},
    "2": {"time": "09:25 - 10:10", "name": "Українська мова", "room": "Кабінет укр. мови [54]"},
    "3": {"time": "10:25 - 11:10", "name": "Фізика", "room": "Архів школи [59]"},
    "4": {"time": "11:30 - 12:15", "name": "Вікно / Самостійна", "room": "-"},
    "5": {"time": "12:35 - 13:20", "name": "Польська мова", "room": "Архів школи [59]"},
    "6": {"time": "13:30 - 14:15", "name": "Геометрія", "room": "Кабінет основ здоров'я [5]"},
    "7": {"time": "14:25 - 15:10", "name": "Українська література", "room": "Архів школи [59]"}
}

# Розклад на четвер
THURSDAY_SCHEDULE = {
    "1": {"time": "08:30 - 09:15", "name": "Інтегрований курс \"Здоров'я, безпека та добробут\"", "room": "Архів школи [59]"},
    "2": {"time": "09:25 - 10:10", "name": "Вікно / Самостійна", "room": "-"},
    "3": {"time": "10:25 - 11:10", "name": "Англійська мова", "room": "Класна кімната 9-Б [46]"},
    "4": {"time": "11:30 - 12:15", "name": "Алгебра", "room": "Кабінет інформатики [33]"},
    "5": {"time": "12:35 - 13:20", "name": "Історія України", "room": "Архів школи [59]"},
    "6": {"time": "13:30 - 14:15", "name": "Інформатика", "room": "Кабінет інформатики [33]"},
    "7": {"time": "14:25 - 15:10", "name": "Геометрія", "room": "Кабінет основ здоров'я [5]"}
}

# Розклад на п'ятницю
FRIDAY_SCHEDULE = {
    "1": {"time": "08:30 - 09:15", "name": "Хімія", "room": "Хімічний кабінет [47]"},
    "2": {"time": "09:25 - 10:10", "name": "Українська мова", "room": "Кабінет укр. мови [54]"},
    "3": {"time": "10:25 - 11:10", "name": "Біологія", "room": "Кабінет біології [7]"},
    "4": {"time": "11:30 - 12:15", "name": "Польська мова", "room": "Архів школи [59]"},
    "5": {"time": "12:35 - 13:20", "name": "Вікно / Самостійна", "room": "-"},
    "6": {"time": "13:30 - 14:15", "name": "Географія", "room": "Архів школи [59]"},
    "7": {"time": "14:25 - 15:10", "name": "Українська література", "room": "Архів школи [59]"}
}

# Головне меню з кнопкою розкладу
def get_main_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="📅 Подивитися розклад", callback_data="show_schedule_menu")
    return builder.as_markup()

# Меню вибору днів тижня
def get_days_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="Понеділок", callback_data="day_monday")
    builder.button(text="Вівторок", callback_data="day_tuesday")
    builder.button(text="Середа", callback_data="day_wednesday")
    builder.button(text="Четвер", callback_data="day_thursday")
    builder.button(text="П'ятниця", callback_data="day_friday")
    builder.adjust(2, 2, 1)
    return builder.as_markup()

@dp.message(Command("start"))
async def cmd_start(message: Message):
    global CHAT_ID
    CHAT_ID = message.chat.id
    await message.answer(
        "Привіт! Я твій шкільний бот-помічник. Я буду сповіщати тебе про початок та кінець уроків, а також показувати актуальний розклад.",
        reply_markup=get_main_keyboard()
    )

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
        text += f"🔹 **{num}. {lesson['name']}** ({lesson['time']})\n   📍 _{lesson['room']}_\n\n"
    
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
    if not CHAT_ID:
        return
    
    lesson = day_schedule.get(lesson_number)
    if lesson and lesson['name'] != "Вікно / Самостійна":
        text = (
            f"🔔 **Урок {lesson_number}: {lesson['name']} почався!**\n\n"
            f"⏰ Час: {lesson['time']}\n"
            f"📍 {lesson['room']}"
        )
        await bot.send_message(CHAT_ID, text, parse_mode="Markdown")

# Сповіщення про кінець уроку
async def send_lesson_end_notification(day_schedule: dict, lesson_number: str):
    if not CHAT_ID:
        return
    
    lesson = day_schedule.get(lesson_number)
    if lesson and lesson['name'] != "Вікно / Самостійна":
        text = (
            f"🔕 **Урок {lesson_number}: {lesson['name']} закінчився!**"
        )
        await bot.send_message(CHAT_ID, text, parse_mode="Markdown")

# Налаштування розкладу подій (початок і кінець для кожного уроку)
def setup_scheduler():
    # Дзвінки для вівторка (8 уроків)
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

    # Дзвінки для середи (7 уроків)
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

    # Дзвінки для четверга (7 уроків)
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

    # Дзвінки для п'ятниці (7 уроків)
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
