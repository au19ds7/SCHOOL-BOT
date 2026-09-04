import asyncio
import logging
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from google import genai
from PIL import Image
import io

# Токени та ключі
TOKEN = "8952184969:AAHS21Naqs1Hmtvpvi7Eh-oNcclRZFCMj9Q"
GEMINI_API_KEY = "AQ.Ab8RN6K1T7Oob-DdHDVRXvRJREBpQlaYCzESys5T4H9EqkuHTw"

# Твій юзернейм для надсилання анонімних запитань адміну
ADMIN_USERNAME = "fyto3"

# Змінна для керування статусом сповіщень (увімкнено за замовчуванням)
NOTIFICATIONS_ENABLED = True

bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()
scheduler = AsyncIOScheduler(timezone="Europe/Kiev")

# Клієнт Google GenAI для розв'язання задач
ai_client = genai.Client(api_key=GEMINI_API_KEY)

# Словники та бази даних в пам'яті
reminders_list = []      # Список нагадувань
user_creation_step = {}  # Кроки створення нагадування
homework_list = []       # Список ДЗ
hw_creation_step = {}    # Кроки запису ДЗ

# Бази даних для Рейтингу доброти
kindness_ratings = {}    
user_votes_history = {}  

# База всіх користувачів, які колись запускали бота
known_users = {}

# Стани для FSM
class BroadcastStates(StatesGroup):
    waiting_for_broadcast_content = State()
    waiting_for_anonymous_message = State()
    waiting_for_anon_target = State()     # Очікування юзернейму одержувача анонімки
    waiting_for_anon_text = State()       # Очікування тексту анонімного повідомлення
    waiting_for_solver_photo = State()    # Очікування фото з задачею для ШІ

class RatingStates(StatesGroup):
    waiting_for_username = State()

# Словник вчителів за предметами
TEACHERS = {
    "Англ. мова": "Галина Зиновіївна / Людмила Петрівна",
    "Хімія": "Володимир Леонідович",
    "Укр. мова": "Ольга Степанівна",
    "Укр. літ.": "Наталія Вікторівна",
    "Ф-ра": "Михайло Леонідович",
    "Фізика": "Ірина Володимирівна",
    "Зарубіжна": "Ірина Василівна",
    "Матем. а.": "Оксана Миколаївна",
    "Матем. геом.": "Оксана Миколаївна",
    "Матем. ат.": "Оксана Миколаївна",
    "Історія": "Іванна Богданівна",
    "Інфор.": "Оксана Миколаївна",
    "Технології": "Іванна Петрівна",
    "Біологія": "Надія Григорівна",
    "Мист.": "Ірина Василівна",
    "Географія": "Тетяна Теодорівна",
    "ЗБД - ПРГ": "Оксана Миколаївна / Іванна Петрівна"
}

def get_teacher_for_subject(subject_name: str) -> str:
    for key, teacher in TEACHERS.items():
        if key.lower() in subject_name.lower():
            return teacher
    return "Не вказано"

def get_current_week():
    week_number = datetime.now().isocalendar()[1]
    return 1 if week_number % 2 != 0 else 2

def get_subject_with_emoji(name: str) -> str:
    lower_name = name.lower()
    if "англі" in lower_name:
        return f"🇬🇧 {name}"
    elif "хім" in lower_name:
        return f"🧪 {name}"
    elif "укр. мов" in lower_name or "укр мов" in lower_name:
        return f"🇺🇦 {name}"
    elif "укр. літ" in lower_name or "укр літ" in lower_name:
        return f"📖 {name}"
    elif "ф-ра" in lower_name or "фіз" in lower_name and "культ" in lower_name:
        return f"⚽ {name}"
    elif "фізик" in lower_name:
        return f"⚛️ {name}"
    elif "зарубіж" in lower_name:
        return f"📚 {name}"
    elif "матем" in lower_name or "алгебр" in lower_name or "геометр" in lower_name:
        return f"📐 {name}"
    elif "історі" in lower_name:
        return f"🏛️ {name}"
    elif "інфор" in lower_name:
        return f"💻 {name}"
    elif "технолог" in lower_name or "збд" in lower_name or "прг" in lower_name:
        return f"🛠️ {name}"
    elif "біолог" in lower_name:
        return f"🧬 {name}"
    elif "мист" in lower_name:
        return f"🎨 {name}"
    elif "польськ" in lower_name:
        return f"🇵🇱 {name}"
    elif "географ" in lower_name:
        return f"🌍 {name}"
    else:
        return f"📖 {name}"

# --- ЛОГІКА ЧЕРГУВАНЬ ПАРТ ---
def get_duty_desk_info(target_date=None):
    if target_date is None:
        target_date = datetime.now()
    
    weekday = target_date.weekday()
    if weekday >= 5:
        return "Вихідний день (субота або неділя). Чергових немає! 🎉"
    
    anchor_date = datetime(2026, 9, 4)
    anchor_desk = 3
    
    curr = anchor_date.date()
    target = target_date.date()
    
    school_days_diff = 0
    if target > curr:
        d = curr + timedelta(days=1)
        while d <= target:
            if d.weekday() < 5:
                school_days_diff += 1
            d += timedelta(days=1)
    elif target < curr:
        d = curr
        while d > target:
            if d.weekday() < 5:
                school_days_diff -= 1
            d -= timedelta(days=1)
            
    desk_number = ((anchor_desk - 1 + school_days_diff) % 15) + 1
    day_names = ["Понеділок", "Вівторок", "Середа", "Четвер", "П'ятниця"]
    return f"🏫 Сьогодні **{day_names[weekday]}**.\n🧹 Чергова парта на сьогодні: **{desk_number} парта**."

# РОЗКЛАД УРОКІВ
MONDAY_SCHEDULE = {
    "1": {"time": "08:30 - 09:15", "name": "Англ. мова"},
    "2": {"time": "09:25 - 10:10", "name": "Хімія"},
    "3": {"time": "10:25 - 11:10", "name": "Укр. мова"},
    "4": {"time": "11:30 - 12:15", "name": "Ф-ра"},
    "5": {"time": "12:35 - 13:20", "name": "Фізика"},
    "6": {"time": "13:30 - 14:15", "name": "Зарубіжна"},
    "7": {"time": "14:25 - 15:10", "name": "Фізика 2х"}
}

TUESDAY_SCHEDULE = {
    "1": {"time": "08:30 - 09:15", "name": "Англ. - Матем. ат."},
    "2": {"time": "09:25 - 10:10", "name": "Укр. мова"},
    "3": {"time": "10:25 - 11:10", "name": "Матем. а."},
    "4": {"time": "11:30 - 12:15", "name": "Історія"},
    "5": {"time": "12:35 - 13:20", "name": "Інфор."},
    "6": {"time": "13:30 - 14:15", "name": "Технології"},
    "7": {"time": "14:25 - 15:10", "name": "Біологія"},
    "8": {"time": "15:20 - 16:05", "name": "Мист."}
}

WEDNESDAY_SCHEDULE = {
    "1": {"time": "08:30 - 09:15", "name": "Англ. мова"},
    "2": {"time": "09:25 - 10:10", "name": "Укр. мова - Польська"},
    "3": {"time": "10:25 - 11:10", "name": "Фізика"},
    "4": {"time": "11:30 - 12:15", "name": "Ф-ра"},
    "5": {"time": "12:35 - 13:20", "name": "Укр. мова - Польська"},
    "6": {"time": "13:30 - 14:15", "name": "Матем. геом."},
    "7": {"time": "14:25 - 15:10", "name": "Укр. літ."}
}

THURSDAY_SCHEDULE = {
    "1": {"time": "08:30 - 09:15", "name": "ЗБД - ПРГ"},
    "2": {"time": "09:25 - 10:10", "name": "Ф-ра"},
    "3": {"time": "10:25 - 11:10", "name": "Англ. мова"},
    "4": {"time": "11:30 - 12:15", "name": "Математика а."},
    "5": {"time": "12:35 - 13:20", "name": "Історія"},
    "6": {"time": "13:30 - 14:15", "name": "Інфор. - Історія"},
    "7": {"time": "14:25 - 15:10", "name": "Матем. ат."}
}

FRIDAY_SCHEDULE = {
    "1": {"time": "08:30 - 09:15", "name": "Хімія"},
    "2": {"time": "09:25 - 10:10", "name": "Укр. мова"},
    "3": {"time": "10:25 - 11:10", "name": "Біологія"},
    "4": {"time": "11:30 - 12:15", "name": "Укр. мова - Польська"},
    "5": {"time": "12:35 - 13:20", "name": "Історія"},
    "6": {"time": "13:30 - 14:15", "name": "Географія"},
    "7": {"time": "14:25 - 15:10", "name": "Укр. літ."}
}

WEEK_SCHEDULES = {
    0: MONDAY_SCHEDULE,
    1: TUESDAY_SCHEDULE,
    2: WEDNESDAY_SCHEDULE,
    3: THURSDAY_SCHEDULE,
    4: FRIDAY_SCHEDULE
}

# --- АВТОМАТИЧНІ СПОВІЩЕННЯ ---
async def send_evening_homework_reminder():
    if not NOTIFICATIONS_ENABLED:
        return
        
    now = datetime.now()
    weekday_index = now.weekday()
    
    day_names_ua = ["Понеділок", "Вівторок", "Середа", "Четвер", "П'ятниця", "Субота", "Неділя"]
    today_name = day_names_ua[weekday_index]
    
    all_users = set(item['user_id'] for item in homework_list)
    
    for uid in all_users:
        user_hw_today = [item for item in homework_list if item['user_id'] == uid and item['day'].lower() == today_name.lower()]
        
        if user_hw_today:
            text = f"⏰ **Вечірнє нагадування о 16:00!**\n\nТи записував домашнє завдання на сьогодні (**{today_name}**):\n"
            for item in user_hw_today:
                text += f"📌 {item['text']}\n"
            text += "\n_Не забудь зробити уроки! 💪_"
            
            try:
                await bot.send_message(chat_id=uid, text=text, parse_mode="Markdown")
            except Exception:
                pass

async def send_automatic_lesson_notification(day_index: int, lesson_num: str):
    if not NOTIFICATIONS_ENABLED:
        return
    
    schedule = WEEK_SCHEDULES.get(day_index)
    if not schedule or lesson_num not in schedule:
        return
        
    lesson = schedule[lesson_num]
    raw_name = lesson['name']
    lesson_time = lesson['time']
    current_week = get_current_week()
    
    day_names_ua = ["понеділок", "вівторок", "середу", "четвер", "п'ятницю"]
    day_str = day_names_ua[day_index]
    
    text = f"🔔 **Увага! Початок уроку ({lesson_time}) на {day_str}!**\n\n"
    
    if " - " in raw_name:
        parts = raw_name.split(" - ")
        part1 = parts[0].strip()
        part2 = parts[1].strip()
        teacher1 = get_teacher_for_subject(part1)
        teacher2 = get_teacher_for_subject(part2)
        
        if current_week == 1:
            formatted_name = f"1️⃣ **{get_subject_with_emoji(part1)}** (👩‍🏫 _{teacher1}_)\n   2️⃣ {get_subject_with_emoji(part2)} (👩‍🏫 _{teacher2}_)"
        else:
            formatted_name = f"1️⃣ {get_subject_with_emoji(part1)} (👩‍🏫 _{teacher1}_)\n   2️⃣ **{get_subject_with_emoji(part2)}** (👩‍🏫 _{teacher2}_)"
        text += f"▫️ **Урок {lesson_num}**:\n{formatted_name}"
    else:
        formatted_name = get_subject_with_emoji(raw_name)
        teacher = get_teacher_for_subject(raw_name)
        text += f"▫️ **Урок {lesson_num}.** {formatted_name}\n   👩‍🏫 Вчитель: _{teacher}_"

    for uid in known_users:
        try:
            await bot.send_message(chat_id=uid, text=text, parse_mode="Markdown")
        except Exception:
            pass

async def send_morning_greeting():
    if not NOTIFICATIONS_ENABLED:
        return
    
    now = datetime.now()
    day_index = now.weekday()
    if day_index > 4:
        return
        
    schedule = WEEK_SCHEDULES.get(day_index)
    if not schedule:
        return
        
    current_week = get_current_week()
    day_names_ua = ["понеділок", "вівторок", "середу", "четвер", "п'ятницю"]
    day_str = day_names_ua[day_index]
    
    text = f"🌅 **Доброго ранку! Розклад на сьогодні ({day_str}), {current_week}-й тиждень:**\n\n"
    
    for num, lesson in schedule.items():
        raw_name = lesson['name']
        lesson_time = lesson['time']
        if " - " in raw_name:
            parts = raw_name.split(" - ")
            subj = parts[0].strip() if current_week == 1 else parts[1].strip()
            text += f"▫️ **{num}.** {get_subject_with_emoji(subj)} (`{lesson_time}`)\n"
        else:
            text += f"▫️ **{num}.** {get_subject_with_emoji(raw_name)} (`{lesson_time}`)\n"
            
    text += "\n🔔 Перший урок розпочнеться о **08:30**! Гарного дня!"

    for uid in known_users:
        try:
            await bot.send_message(chat_id=uid, text=text, parse_mode="Markdown")
        except Exception:
            pass

def setup_lesson_notifications():
    for day_idx, sch in WEEK_SCHEDULES.items():
        for l_num, data in sch.items():
            start_time_str = data['time'].split(" - ")[0].strip()
            hour, minute = map(int, start_time_str.split(":"))
            
            scheduler.add_job(
                send_automatic_lesson_notification,
                'cron',
                day_of_week=str(day_idx),
                hour=hour,
                minute=minute,
                args=[day_idx, l_num]
            )
            
    scheduler.add_job(
        send_morning_greeting,
        'cron',
        day_of_week='mon-fri',
        hour=8,
        minute=15
    )
    
    scheduler.add_job(
        send_evening_homework_reminder,
        'cron',
        hour=16,
        minute=0
    )

# Головне меню (з новою кнопкою ШІ-розв'язателя)
def get_main_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🔍 Що зараз?", callback_data="what_is_now")
    builder.button(text="🧹 Хто черговий?", callback_data="who_is_duty")
    builder.button(text="🧠 Розв'язати задачу (ШІ)", callback_data="start_ai_solver")
    builder.button(text="📅 Подивитися розклад", callback_data="show_schedule_menu")
    builder.button(text="📚 Домашнє завдання", callback_data="show_homework")
    builder.button(text="📘 ГДЗ та Посилання (НЗ)", callback_data="show_gdz_menu")
    builder.button(text="⭐ Рейтинг доброти", callback_data="show_kindness_rating")
    builder.button(text="🤫 Анонімне запитання / скарга", callback_data="start_anonymous")
    builder.button(text="👤🤫 Написати анонімно людині", callback_data="start_anon_to_user")
    builder.button(text="⏰ Нагадування", callback_data="show_reminders")
    builder.button(text="📢 Скинути всім", callback_data="start_broadcast")
    
    notif_text = "🔕 Вимкнути сповіщення" if NOTIFICATIONS_ENABLED else "🔔 Увімкнути сповіщення"
    builder.button(text=notif_text, callback_data="toggle_notifications")
    
    builder.adjust(1, 1, 1, 1, 2, 1, 1, 1, 1, 1, 1, 1)
    return builder.as_markup()

def get_cancel_broadcast_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Скасувати", callback_data="back_to_main")
    return builder.as_markup()

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

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    user = message.from_user
    known_users[user.id] = {
        "id": user.id,
        "username": user.username if user.username else "",
        "first_name": user.first_name
    }
    await state.clear()
    status = "увімкнені ✅" if NOTIFICATIONS_ENABLED else "вимкнені ❌"
    await message.answer(
        f"Привіт! Я твій шкільний бот-помічник.\nПоточні сповіщення: {status}",
        reply_markup=get_main_keyboard()
    )

@router.callback_query(F.data == "back_to_main")
async def process_back_to_main(callback: CallbackQuery, state: FSMContext):
    user = callback.from_user
    known_users[user.id] = {
        "id": user.id,
        "username": user.username if user.username else "",
        "first_name": user.first_name
    }
    await state.clear()
    status = "увімкнені ✅" if NOTIFICATIONS_ENABLED else "вимкнені ❌"
    await callback.message.edit_text(
        f"Головне меню:\nПоточні сповіщення: {status}",
        reply_markup=get_main_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data == "toggle_notifications")
async def process_toggle_notifications(callback: CallbackQuery):
    global NOTIFICATIONS_ENABLED
    NOTIFICATIONS_ENABLED = not NOTIFICATIONS_ENABLED
    status = "увімкнені ✅" if NOTIFICATIONS_ENABLED else "вимкнені ❌"
    
    await callback.message.edit_text(
        f"Головне меню:\nСповіщення тепер {status}",
        reply_markup=get_main_keyboard()
    )
    await callback.answer("Статус сповіщень змінено!")

# --- ХТО ЧЕРГОВИЙ ---
@router.callback_query(F.data == "who_is_duty")
async def process_who_is_duty(callback: CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад у меню", callback_data="back_to_main")
    
    duty_text = get_duty_desk_info()
    text = f"🧹 **Графік чергування парт:**\n\n{duty_text}"
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer()

# --- ЩО ЗАРАЗ ---
@router.callback_query(F.data == "what_is_now")
async def process_what_is_now(callback: CallbackQuery):
    now = datetime.now()
    day_index = now.weekday()
    
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад у меню", callback_data="back_to_main")
    
    if day_index > 4:
        text = "🏖️ **Сьогодні вихідний (субота або неділя)!** Уроків немає, відпочивай! 😎"
    else:
        schedule = WEEK_SCHEDULES.get(day_index)
        current_time_minutes = now.hour * 60 + now.minute
        current_week = get_current_week()
        
        active_lesson = None
        next_lesson = None
        
        for num, lesson in schedule.items():
            time_parts = lesson['time'].split(" - ")
            start_h, start_m = map(int, time_parts[0].split(":"))
            end_h, end_m = map(int, time_parts[1].split(":"))
            
            start_total = start_h * 60 + start_m
            end_total = end_h * 60 + end_m
            
            if start_total <= current_time_minutes <= end_total:
                active_lesson = (num, lesson)
                break
            elif current_time_minutes < start_total:
                next_lesson = (num, lesson)
                break
                
        if active_lesson:
            num, lesson = active_lesson
            raw_name = lesson['name']
            if " - " in raw_name:
                parts = raw_name.split(" - ")
                subj = parts[0].strip() if current_week == 1 else parts[1].strip()
            else:
                subj = raw_name
            teacher = get_teacher_for_subject(subj)
            text = f"🟢 **Зараз іде урок!**\n\n▫️ **Урок {num}** ({lesson['time']})\n📌 {get_subject_with_emoji(subj)}\n👩‍🏫 Вчитель: _{teacher}_"
        elif next_lesson:
            num, lesson = next_lesson
            raw_name = lesson['name']
            if " - " in raw_name:
                parts = raw_name.split(" - ")
                subj = parts[0].strip() if current_week == 1 else parts[1].strip()
            else:
                subj = raw_name
            text = f"⏳ **Зараз перерва або до початку уроків.**\n\nНаступний:\n▫️ **Урок {num}** ({lesson['time']})\n📌 {get_subject_with_emoji(subj)}"
        else:
            text = "🏁 **Уроки на сьогодні вже закінчилися!** Можна відпочивати."
            
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer()

# --- РЕЙТИНГ ДОБРОТИ ---
@router.callback_query(F.data == "show_kindness_rating")
async def process_kindness_rating(callback: CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="👍 Оцінити людину", callback_data="rate_someone_start")
    builder.button(text="⬅️ Назад у меню", callback_data="back_to_main")
    builder.adjust(1)
    
    text = "⭐ **Рейтинг доброти та шкідливості**\n\n"
    
    if not kindness_ratings:
        text += "_Тут поки що порожньо. Стань першим, кого оцінять!_\n"
    else:
        sorted_users = sorted(kindness_ratings.values(), key=lambda x: x['score'], reverse=True)
        
        for i, u_data in enumerate(sorted_users[:10], start=1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            uname = f"@{u_data['username']}" if u_data['username'] else u_data['name']
            score = u_data['score']
            score_str = f"+{score}" if score > 0 else str(score)
            text += f"{medal} **{uname}** — `{score_str}` балів\n"
            
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data == "rate_someone_start")
async def process_rate_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(RatingStates.waiting_for_username)
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Скасувати", callback_data="show_kindness_rating")
    
    await callback.message.edit_text(
        "✍️ **Введи юзернейм людини** (наприклад, `@fyto3` або просто тег), якій хочеш змінити рейтинг:",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )
    await callback.answer()

@router.message(RatingStates.waiting_for_username)
async def process_target_username(message: Message, state: FSMContext):
    target_input = message.text.strip().lstrip("@")
    if not target_input:
        await message.answer("❌ Некоректне ім'я. Спробуй ще раз:")
        return
        
    await state.clear()
    
    builder = InlineKeyboardBuilder()
    builder.button(text="❤️ Лайк (+1)", callback_data=f"rate_val_like_{target_input}")
    builder.button(text="💩 Дизлайк (-1)", callback_data=f"rate_val_dislike_{target_input}")
    builder.button(text="⬅️ Назад", callback_data="show_kindness_rating")
    builder.adjust(2, 1)
    
    await message.answer(
        f"Оцінюємо користувача: **@{target_input}**\n\nОбери реакцію:",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )

@router.callback_query(F.data.startswith("rate_val_"))
async def process_rate_value(callback: CallbackQuery):
    parts = callback.data.split("_")
    action = parts[2]
    target_username = parts[3].lower()
    voter_id = callback.from_user.id
    
    target_user_key = None
    for uid, data in kindness_ratings.items():
        if data['username'].lower() == target_username:
            target_user_key = uid
            break
            
    if not target_user_key:
        target_user_key = abs(hash(target_username)) % (10 ** 8)
        kindness_ratings[target_user_key] = {
            "name": target_username,
            "username": target_username,
            "score": 0
        }
        
    vote_key = (voter_id, target_user_key)
    previous_vote = user_votes_history.get(vote_key)
    
    score_change = 0
    if action == "like":
        if previous_vote == "like":
            await callback.answer("⚠️ Ти вже ставив лайк цій людині!", show_alert=True)
            return
        elif previous_vote == "dislike":
            score_change = 2
        else:
            score_change = 1
        user_votes_history[vote_key] = "like"
        
    elif action == "dislike":
        if previous_vote == "dislike":
            await callback.answer("⚠️ Ти вже ставив дизлайк цій людині!", show_alert=True)
            return
        elif previous_vote == "like":
            score_change = -2
        else:
            score_change = -1
        user_votes_history[vote_key] = "dislike"
        
    kindness_ratings[target_user_key]['score'] += score_change
    action_text = "❤️ поставлено лайк (+1)" if action == "like" else "💩 поставлено дизлайк (-1)"
    await callback.answer("Успішно! Голос зараховано.", show_alert=False)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="👍 Оцінити іншу людину", callback_data="rate_someone_start")
    builder.button(text="⬅️ Назад у меню", callback_data="back_to_main")
    builder.adjust(1)
    
    sorted_users = sorted(kindness_ratings.values(), key=lambda x: x['score'], reverse=True)
    text = f"⭐ **Оновлений рейтинг доброти**\n(Твоя дія: {action_text} для @{target_username})\n\n"
    
    for i, u_data in enumerate(sorted_users[:10], start=1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        uname = f"@{u_data['username']}" if u_data['username'] else u_data['name']
        score = u_data['score']
        score_str = f"+{score}" if score > 0 else str(score)
        text += f"{medal} **{uname}** — `{score_str}` балів\n"
        
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

# --- РОЗВ'ЯЗАТИ ЗАДАЧУ ПО ФОТО (ШІ) ---
@router.callback_query(F.data == "start_ai_solver")
async def process_start_ai_solver(callback: CallbackQuery, state: FSMContext):
    await state.set_state(BroadcastStates.waiting_for_solver_photo)
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Скасувати", callback_data="back_to_main")
    
    await callback.message.edit_text(
        "🧠 **Розв'язання задач та прикладів за допомогою ШІ**\n\n"
        "📸 Надішли мені фото з прикладом, рівнянням чи задачею, і я розпишу покрокове розв'язання українською мовою!",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )
    await callback.answer()

# --- АНОНІМНЕ ЗАПИТАННЯ АДМІНІСТРАТОРУ ---
@router.callback_query(F.data == "start_anonymous")
async def process_start_anonymous(callback: CallbackQuery, state: FSMContext):
    await state.set_state(BroadcastStates.waiting_for_anonymous_message)
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Скасувати", callback_data="back_to_main")
    
    await callback.message.edit_text(
        "🤫 **Анонімна скарбничка (питання та скарги адміністратору)**\n\n"
        "Напиши своє запитання або скаргу текстом (чи надішли фото). "
        "Ніхто, крім адміністратора (`fyto3`), не дізнається, хто це надіслав! 🔒",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )
    await callback.answer()

# --- АНОНІМНЕ ПОВІДОМЛЕННЯ БУДЬ-ЯКОМУ КОРИСТУВАЧУ БОТА ---
@router.callback_query(F.data == "start_anon_to_user")
async def process_start_anon_to_user(callback: CallbackQuery, state: FSMContext):
    await state.set_state(BroadcastStates.waiting_for_anon_target)
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Скасувати", callback_data="back_to_main")
    
    await callback.message.edit_text(
        "👤🤫 **Написати анонімне повідомлення людині з бота**\n\n"
        "Введи **юзернейм** людини, якій хочеш написати (наприклад: `@username` або просто `username`):",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )
    await callback.answer()

# --- ГДЗ ТА ПОСИЛАННЯ ---
@router.callback_query(F.data == "show_gdz_menu")
async def process_gdz_menu(callback: CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="🌐 Нові Знання (Електронний щоденник)", url="https://nz.ua/")
    builder.button(text="💻 МійКлас", url="https://www.miklass.com.ua/")
    builder.button(text="🇺🇦 Українська мова (Заболотний)", url="https://4book.org/gdz-reshebniki-ukraina/9-klas/gdz-ukrayinska-mova-9-klas-zabolotniy-nush-2026")
    builder.button(text="📐 Алгебра", url="https://gdzister.com.ua/alhebra")
    builder.button(text="📐 Геометрія", url="https://gdzister.com.ua/heometriia")
    builder.button(text="⬅️ Назад у меню", callback_data="back_to_main")
    builder.adjust(1)
    
    await callback.message.edit_text(
        "📘 **Корисні посилання та ГДЗ:**\nОбери потрібний ресурс:",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )
    await callback.answer()

# --- ДОМАШНІ ЗАВДАННЯ ---
@router.callback_query(F.data == "show_homework")
async def process_homework_menu(callback: CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="✍️ Записати ДЗ", callback_data="create_homework")
    
    hw_text = "📚 **Список домашніх завдань:**\n\n"
    if not homework_list:
        hw_text += "_Поки що немає жодного записаного ДЗ_\n"
    else:
        for item in homework_list:
            hw_text += f"📌 **{item['day']}**: {item['text']}\n"
            builder.button(text=f"❌ Видалити ДЗ: {item['text'][:12]}...", callback_data=f"del_hw_{item['id']}")

    builder.button(text="⬅️ Назад у меню", callback_data="back_to_main")
    builder.adjust(1)
    
    await callback.message.edit_text(
        hw_text,
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(F.data == "create_homework")
async def process_create_homework(callback: CallbackQuery):
    hw_creation_step[callback.from_user.id] = {}
    
    builder = InlineKeyboardBuilder()
    builder.button(text="Понеділок", callback_data="hw_day_Понеділок")
    builder.button(text="Вівторок", callback_data="hw_day_Вівторок")
    builder.button(text="Середа", callback_data="hw_day_Середа")
    builder.button(text="Четвер", callback_data="hw_day_Четвер")
    builder.button(text="П'ятниця", callback_data="hw_day_П'ятниця")
    builder.button(text="Субота", callback_data="hw_day_Субота")
    builder.button(text="❌ Скасувати", callback_data="show_homework")
    builder.adjust(2, 2, 2, 1)
    
    await callback.message.edit_text(
        "📚 **На який день тижня записати домашнє завдання?**\nОбери день:",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("hw_day_"))
async def process_hw_day_chosen(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in hw_creation_step:
        await callback.message.edit_text("Помилка. Спробуйте знову.", reply_markup=get_main_keyboard())
        return
    
    day_name = callback.data.split("_")[2]
    hw_creation_step[user_id]["day"] = day_name
    hw_creation_step[user_id]["step"] = "waiting_text"
    
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Скасувати", callback_data="show_homework")
    
    await callback.message.edit_text(
        f"📅 Обрано день: **{day_name}**\n\n✍️ **Тепер напиши саме домашнє завдання (наприклад: *Математика, номер 412*):**",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("del_hw_"))
async def process_delete_homework(callback: CallbackQuery):
    hw_id = int(callback.data.split("_")[2])
    global homework_list
    homework_list = [item for item in homework_list if item['id'] != hw_id]
    await process_homework_menu(callback)

# --- НАГАДУВАННЯ ---
@router.callback_query(F.data == "show_reminders")
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

@router.callback_query(F.data == "create_reminder")
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

@router.callback_query(F.data.startswith("rem_day_"))
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
        f"📅 День обрано: **{days_map[day_code][0]}**\n\n⏰ **Тепер напишіть годину у форматі Година:Хвилина (наприклад: 14:30):**",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("done_rem_"))
async def process_mark_done(callback: CallbackQuery):
    rem_id = int(callback.data.split("_")[2])
    for item in reminders_list:
        if item['id'] == rem_id:
            item['done'] = True
    await process_reminders_menu(callback)

# --- МАСОВА РОЗСИЛКА ---
@router.callback_query(F.data == "start_broadcast")
async def process_start_broadcast(callback: CallbackQuery, state: FSMContext):
    await state.set_state(BroadcastStates.waiting_for_broadcast_content)
    await callback.message.edit_text(
        "📢 **Режим масової розсилки**\n\n"
        "Надішли текст або скріншот (фото), і бот миттєво перешле його всім користувачам бота!",
        reply_markup=get_cancel_broadcast_kb(),
        parse_mode="Markdown"
    )
    await callback.answer()

# Текстові обробники для FSM
@router.message(F.text & ~F.text.startswith("/"))
async def handle_text_inputs(message: Message, state: FSMContext):
    user = message.from_user
    user_id = user.id
    known_users[user_id] = {
        "id": user_id,
        "username": user.username if user.username else "",
        "first_name": user.first_name
    }
    
    current_state = await state.get_state()
    
    # 1. Обробка введення юзернейму для анонімного повідомлення іншій людині
    if current_state == BroadcastStates.waiting_for_anon_target.state:
        target_username = message.text.strip().lstrip("@").lower()
        
        found_target_id = None
        for uid, udata in known_users.items():
            if udata["username"].lower() == target_username:
                found_target_id = uid
                break
                
        if not found_target_id:
            builder = InlineKeyboardBuilder()
            builder.button(text="🏠 Головне меню", callback_data="back_to_main")
            await message.answer(
                f"❌ Користувача з юзернеймом **@{target_username}** не знайдено в базі бота.\n"
                "Ця людина має хоча б один раз запустити цього бота (`/start`), щоб він міг отримувати повідомлення!",
                reply_markup=builder.as_markup(),
                parse_mode="Markdown"
            )
            await state.clear()
            return
            
        await state.update_data(target_id=found_target_id, target_username=target_username)
        await state.set_state(BroadcastStates.waiting_for_anon_text)
        
        builder = InlineKeyboardBuilder()
        builder.button(text="❌ Скасувати", callback_data="back_to_main")
        await message.answer(
            f"✅ Користувача @{target_username} знайдено!\n\n✍️ **Тепер напиши текст анонімного повідомлення, яке йому надішлють:**",
            reply_markup=builder.as_markup(),
            parse_mode="Markdown"
        )
        return

    # 2. Обробка тексту анонімного повідомлення для обраного користувача
    if current_state == BroadcastStates.waiting_for_anon_text.state:
        data = await state.get_data()
        target_id = data.get("target_id")
        target_username = data.get("target_username")
        await state.clear()
        
        anon_msg_text = f"🤫 **Тобі прийшло нове анонімне повідомлення:**\n\n{message.text}"
        
        try:
            await bot.send_message(chat_id=target_id, text=anon_msg_text, parse_mode="Markdown")
            success = True
        except Exception:
            success = False
            
        builder = InlineKeyboardBuilder()
        builder.button(text="🏠 Головне меню", callback_data="back_to_main")
        
        if success:
            await message.answer(
                f"✅ **Анонімне повідомлення успішно надіслано користувачу @{target_username}!**",
                reply_markup=builder.as_markup(),
                parse_mode="Markdown"
            )
        else:
            await message.answer(
                "❌ Не вдалося надіслати повідомлення (можливо, користувач заблокував бота).",
                reply_markup=builder.as_markup(),
                parse_mode="Markdown"
            )
        return

    # 3. Анонімне запитання адміністратору
    if current_state == BroadcastStates.waiting_for_anonymous_message.state:
        await state.clear()
        anonymous_text = f"🤫 **Нове анонімне повідомлення (скарга/питання):**\n\n{message.text}"
        
        for uid, udata in known_users.items():
            if udata["username"].lower() == ADMIN_USERNAME.lower():
                try:
                    await bot.send_message(chat_id=uid, text=anonymous_text, parse_mode="Markdown")
                except Exception:
                    pass
                
        builder = InlineKeyboardBuilder()
        builder.button(text="🏠 Головне меню", callback_data="back_to_main")
        
        await message.answer(
            "✅ **Твоє анонімне повідомлення успішно надіслано адміністратору!**",
            reply_markup=builder.as_markup(),
            parse_mode="Markdown"
        )
        return

    # 4. Масова розсилка
    if current_state == BroadcastStates.waiting_for_broadcast_content.state:
        await state.clear()
        username_str = f"@{user.username}" if user.username else "немає юзернейму"
        user_link = f"<a href='tg://user?id={user.id}'>{user.first_name}</a>"
        header = f"📢 <b>Повідомлення від {user_link}</b> ({username_str}):\n\n"
        full_text = header + message.text
        
        success_count = 0
        for uid in known_users:
            try:
                await bot.send_message(chat_id=uid, text=full_text, parse_mode="HTML")
                success_count += 1
            except Exception:
                pass
                
        builder = InlineKeyboardBuilder()
        builder.button(text="🏠 Головне меню", callback_data="back_to_main")
        
        await message.answer(
            f"✅ **Розсилку завершено!**\n• Успішно доставлено: {success_count}",
            reply_markup=builder.as_markup(),
            parse_mode="Markdown"
        )
        return

    # Збереження ДЗ
    if user_id in hw_creation_step and hw_creation_step[user_id].get("step") == "waiting_text":
        day = hw_creation_step[user_id]["day"]
        hw_text = message.text
        
        hw_id = len(homework_list) + 1
        homework_list.append({"id": hw_id, "user_id": user_id, "day": day, "text": hw_text})
        del hw_creation_step[user_id]
        
        builder = InlineKeyboardBuilder()
        builder.button(text="📚 До розділу ДЗ", callback_data="show_homework")
        builder.button(text="🏠 Головне меню", callback_data="back_to_main")
        builder.adjust(1)
        
        await message.answer(
            f"✅ **Домашнє завдання успішно записане!**\n\n📅 День: **{day}**\n📌 Завдання: {hw_text}\n\n_💡 О 16:00 ти отримаєш вечірнє нагадування про це завдання, якщо воно на сьогодні!_",
            reply_markup=builder.as_markup(),
            parse_mode="Markdown"
        )
        return

    if user_id in user_creation_step:
        st = user_creation_step[user_id]
        
        if st["step"] == "waiting_text":
            st["text"] = message.text
            st["step"] = "waiting_day"
            
            await message.answer(
                "📌 **Коли нагадати?**\nОберіть день тижня:",
                reply_markup=get_reminder_days_keyboard(),
                parse_mode="Markdown"
            )
            
        elif st["step"] == "waiting_time":
            time_text = message.text.strip()
            try:
                hour_str, minute_str = time_text.split(":")
                hour = int(hour_str)
                minute = int(minute_str)
                if not (0 <= hour <= 23 and 0 <= minute <= 59):
                    raise ValueError()
            except:
                await message.answer("❌ Неправильний формат часу. Введіть у форматі Година:Хвилина (наприклад `14:30`):", parse_mode="Markdown")
                return
            
            rem_id = len(reminders_list) + 1
            new_reminder = {
                "id": rem_id,
                "text": st["text"],
                "day_name": st["day_name"],
                "time": time_text,
                "done": False
            }
            reminders_list.append(new_reminder)
            
            scheduler.add_job(
                send_user_reminder,
                'cron',
                day_of_week=st["day_cron"],
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
                f"✅ **Нагадування створено!**\n\n📌 Що: {new_reminder['text']}\n📅 Коли: {new_reminder['day_name']} о {time_text}",
                reply_markup=builder.as_markup(),
                parse_mode="Markdown"
            )

@router.message(F.photo)
async def handle_photo_inputs(message: Message, state: FSMContext):
    user = message.from_user
    known_users[user.id] = {
        "id": user.id,
        "username": user.username if user.username else "",
        "first_name": user.first_name
    }
    
    current_state = await state.get_state()
    
    # 1. Обробка фото для ШІ-розв'язателя задач
    if current_state == BroadcastStates.waiting_for_solver_photo.state:
        processing_msg = await message.answer("⏳ **Аналізую зображення та шукаю розв'язання...** 🧠")
        try:
            photo = message.photo[-1]
            file_info = await bot.get_file(photo.file_id)
            downloaded_file = await bot.download_file(file_info.file_path)
            
            image = Image.open(downloaded_file)
            
            response = ai_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    image,
                    "Розв'яжи цю задачу або приклад з фото крок за кроком. Напиши детальне, зрозуміле пояснення українською мовою."
                ]
            )
            
            builder = InlineKeyboardBuilder()
            builder.button(text="📸 Розв'язати ще", callback_data="start_ai_solver")
            builder.button(text="🏠 Головне меню", callback_data="back_to_main")
            builder.adjust(1)
            
            await message.answer(f"💡 **Розв'язання від ШІ:**\n\n{response.text}", reply_markup=builder.as_markup(), parse_mode="Markdown")
        except Exception as e:
            await message.answer(f"❌ Сталася помилка при розв'язанні: {e}")
        finally:
            await state.clear()
            try:
                await bot.delete_message(chat_id=message.chat.id, message_id=processing_msg.message_id)
            except:
                pass
        return

    # 2. Обробка анонімного фото для адміністратора
    if current_state == BroadcastStates.waiting_for_anonymous_message.state:
        await state.clear()
        photo_file_id = message.photo[-1].file_id
        caption = message.caption if message.caption else ""
        header = f"🤫 <b>Нове анонімне фото (скарга/питання):</b>\n{caption}"
        
        for uid, udata in known_users.items():
            if udata["username"].lower() == ADMIN_USERNAME.lower():
                try:
                    await bot.send_photo(chat_id=uid, photo=photo_file_id, caption=header, parse_mode="HTML")
                except Exception:
                    pass
                
        builder = InlineKeyboardBuilder()
        builder.button(text="🏠 Головне меню", callback_data="back_to_main")
        await message.answer("✅ **Твоє анонімне фото успішно надіслано адміністратору!**", reply_markup=builder.as_markup(), parse_mode="Markdown")
        return

    # 3. Обробка фото для масової розсилки
    if current_state == BroadcastStates.waiting_for_broadcast_content.state:
        await state.clear()
        user_link = f"<a href='tg://user?id={user.id}'>{user.first_name}</a>"
        header = f"📢 <b>Фото від {user_link}</b>:\n"
        
        photo_file_id = message.photo[-1].file_id
        caption = message.caption if message.caption else ""
        
        for uid in known_users:
            try:
                await bot.send_photo(chat_id=uid, photo=photo_file_id, caption=header+caption, parse_mode="HTML")
            except Exception:
                pass
                
        builder = InlineKeyboardBuilder()
        builder.button(text="🏠 Головне меню", callback_data="back_to_main")
        await message.answer("✅ **Розсилку фото завершено!**", reply_markup=builder.as_markup(), parse_mode="Markdown")

async def send_user_reminder(rem_id: int):
    pass

# --- РОЗКЛАД УРОКІВ (МЕНЮ) ---
@router.callback_query(F.data == "show_schedule_menu")
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
        raw_name = lesson['name']
        lesson_time = lesson['time']
        
        if " - " in raw_name:
            parts = raw_name.split(" - ")
            part1 = parts[0].strip()
            part2 = parts[1].strip()
            teacher1 = get_teacher_for_subject(part1)
            teacher2 = get_teacher_for_subject(part2)
            
            if current_week == 1:
                formatted_name = f"1️⃣ **{get_subject_with_emoji(part1)}** (👩‍🏫 _{teacher1}_)\n   2️⃣ {get_subject_with_emoji(part2)} (👩‍🏫 _{teacher2}_)"
            else:
                formatted_name = f"1️⃣ {get_subject_with_emoji(part1)} (👩‍🏫 _{teacher1}_)\n   2️⃣ **{get_subject_with_emoji(part2)}** (👩‍🏫 _{teacher2}_)"
            
            text += f"▫️ **Урок {num}** ({lesson_time}):\n{formatted_name}\n\n"
        else:
            formatted_name = get_subject_with_emoji(raw_name)
            teacher = get_teacher_for_subject(raw_name)
            text += f"▫️ **{num}.** {formatted_name} — ⏰ `{lesson_time}`\n   👩‍🏫 Вчитель: _{teacher}_\n\n"
    
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад до днів", callback_data="show_schedule_menu")
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data == "day_monday")
async def process_monday(callback: CallbackQuery):
    await show_schedule_text(callback, MONDAY_SCHEDULE, "понеділок")

@router.callback_query(F.data == "day_tuesday")
async def process_tuesday(callback: CallbackQuery):
    await show_schedule_text(callback, TUESDAY_SCHEDULE, "вівторок")

@router.callback_query(F.data == "day_wednesday")
async def process_wednesday(callback: CallbackQuery):
    await show_schedule_text(callback, WEDNESDAY_SCHEDULE, "середу")

@router.callback_query(F.data == "day_thursday")
async def process_thursday(callback: CallbackQuery):
    await show_schedule_text(callback, THURSDAY_SCHEDULE, "четвер")

@router.callback_query(F.data == "day_friday")
async def process_friday(callback: CallbackQuery):
    await show_schedule_text(callback, FRIDAY_SCHEDULE, "п'ятницю")

async def main():
    logging.basicConfig(level=logging.INFO)
    setup_lesson_notifications()
    
    scheduler.start()
    dp.include_router(router)
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
