import asyncio
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Токен твого бота
TOKEN = "8952184969:AAHS21Naqs1Hmtvpvi7Eh-oNcclRZFCMj9Q"

# ID твого чату (або групи), куди бот має слати сповіщення та куди пересилати повідомлення з групового чату
CHAT_ID = None 
GROUP_CHAT_ID = -100XXXXXXXXXX  # ЗАМІНИ НА ID СВОЄЇ ГРУПИ (має починатися з -100)

# Змінна для керування статусом сповіщень (увімкнено за замовчуванням)
NOTIFICATIONS_ENABLED = True

bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()  # Додаємо роутер для обробників
scheduler = AsyncIOScheduler(timezone="Europe/Kiev")

# Словники та бази даних в пам'яті
reminders_list = []      # Список активних та виконаних нагадувань
user_creation_step = {}  # Тимчасове збереження кроків створення нагадування
homework_list = []       # Список домашніх завдань
hw_creation_step = {}    # Тимчасове збереження кроків запису ДЗ

# Стани для FSM (режим групового чату)
class ChatStates(StatesGroup):
    waiting_for_message = State()

# Функція для визначення поточного тижня (1 або 2) за номером тижня року
def get_current_week():
    week_number = datetime.now().isocalendar()[1]
    return 1 if week_number % 2 != 0 else 2

# Функція для автоматичного додавання емодзі до предметів
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

# Головне меню (тепер з кнопкою "Груповий чат")
def get_main_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="📅 Подивитися розклад", callback_data="show_schedule_menu")
    builder.button(text="📚 Домашнє завдання", callback_data="show_homework")
    builder.button(text="📘 ГДЗ", callback_data="show_gdz_menu")
    builder.button(text="⏰ Нагадування", callback_data="show_reminders")
    builder.button(text="💬 Груповий чат", callback_data="open_group_chat")
    
    notif_text = "🔕 Вимкнути сповіщення" if NOTIFICATIONS_ENABLED else "🔔 Увімкнути сповіщення"
    builder.button(text=notif_text, callback_data="toggle_notifications")
    
    builder.adjust(1, 2, 1, 1, 1, 1)
    return builder.as_markup()

# Клавіатура для виходу з групового чату
def get_back_to_chat_menu_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Вийти з чату (в меню)", callback_data="exit_chat")
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

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    global CHAT_ID
    CHAT_ID = message.chat.id
    await state.clear()
    status = "увімкнені ✅" if NOTIFICATIONS_ENABLED else "вимкнені ❌"
    await message.answer(
        f"Привіт! Я твій шкільний бот-помічник.\nПоточні сповіщення: {status}",
        reply_markup=get_main_keyboard()
    )

@router.callback_query(F.data == "back_to_main")
async def process_back_to_main(callback: CallbackQuery, state: FSMContext):
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

# --- РОЗДІЛ ГДЗ ---

@router.callback_query(F.data == "show_gdz_menu")
async def process_gdz_menu(callback: CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="🇺🇦 Українська мова (Заболотний)", url="https://4book.org/gdz-reshebniki-ukraina/9-klas/gdz-ukrayinska-mova-9-klas-zabolotniy-nush-2026")
    builder.button(text="📐 Алгебра", url="https://gdzister.com.ua/alhebra")
    builder.button(text="📐 Геометрія", url="https://gdzister.com.ua/heometriia")
    builder.button(text="⬅️ Назад у меню", callback_data="back_to_main")
    builder.adjust(1)
    
    await callback.message.edit_text(
        "📘 **Виберіть предмет для перегляду ГДЗ:**",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )
    await callback.answer()

# --- РОЗДІЛ ДОМАШНІХ ЗАВДАНЬ (ДЗ) ---

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
        f"📅 Обрано день: **{day_name}**\n\n✍️ **Тепер напиши саме домашнє завдання (наприклад: *Математика: № 12, стор. 45*):**",
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

# --- РОЗДІЛ НАГАДУВАНЬ ---

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
        f"📅 День обрано: **{days_map[day_code][0]}**\n\n⏰ **Тепер напишіть годину у форматі Година:Хвилина (наприклад: 14:30 або 08:15):**",
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


# --- ЛОГІКА ГРУПОВОГО ЧАТУ (НОВЕ) ---

@router.callback_query(F.data == "open_group_chat")
async def open_group_chat_handler(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ChatStates.waiting_for_message)
    await callback.message.edit_text(
        "💬 **Ти увійшов у груповий чат!**\n\n"
        "Будь-яке твоє повідомлення (текст чи фото) буде автоматично надіслано в загальну групу разом із твоїм ніком.\n\n"
        "Напиши щось або надішли фото:",
        reply_markup=get_back_to_chat_menu_kb(),
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(F.data == "exit_chat")
async def exit_chat_handler(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    status = "увімкнені ✅" if NOTIFICATIONS_ENABLED else "вимкнені ❌"
    await callback.message.edit_text(
        f"Ти вийшов із групового чату.\nГоловне меню:\nПоточні сповіщення: {status}",
        reply_markup=get_main_keyboard()
    )
    await callback.answer()


# Загальний обробник текстових повідомлень та фото
@router.message(F.text & ~F.text.startswith("/"))
async def handle_text_inputs(message: Message, state: FSMContext):
    user_id = message.from_user.id
    current_state = await state.get_state()
    
    # 0. Перевірка чи користувач перебуває у режимі групового чату
    if current_state == ChatStates.waiting_for_message.state:
        user = message.from_user
        username_str = f"@{user.username}" if user.username else "без юзернейму"
        user_link = f"<a href='tg://user?id={user.id}'>{user.first_name}</a>"
        header = f"💬 <b>Повідомлення від {user_link}</b> ({username_str}):\n"

        try:
            if message.text:
                await bot.send_message(
                    chat_id=GROUP_CHAT_ID,
                    text=header + message.text,
                    parse_mode="HTML"
                )
            await message.answer("✅ Надіслано в чат!", reply_markup=get_back_to_chat_menu_kb())
        except Exception as e:
            logging.error(f"Помилка при пересиланні тексту: {e}")
            await message.answer("❌ Сталася помилка при відправці у загальний чат.")
        return

    # 1. Перевірка чи створюється ДЗ
    if user_id in hw_creation_step and hw_creation_step[user_id].get("step") == "waiting_text":
        day = hw_creation_step[user_id]["day"]
        hw_text = message.text
        
        hw_id = len(homework_list) + 1
        homework_list.append({"id": hw_id, "day": day, "text": hw_text})
        del hw_creation_step[user_id]
        
        builder = InlineKeyboardBuilder()
        builder.button(text="📚 До розділу ДЗ", callback_data="show_homework")
        builder.button(text="🏠 Головне меню", callback_data="back_to_main")
        builder.adjust(1)
        
        await message.answer(
            f"✅ **Домашнє завдання успішно записано!**\n\n📅 День: **{day}**\n📌 Завдання: {hw_text}",
            reply_markup=builder.as_markup(),
            parse_mode="Markdown"
        )
        return

    # 2. Перевірка чи створюється нагадування
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
                await message.answer("❌ Неправильний формат часу. Введіть у форматі Година:Хвилина, наприклад `14:30`:", parse_mode="Markdown")
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
                f"✅ **Нагадування успішно створено!**\n\n📌 Що: {new_reminder['text']}\n📅 Коли: {new_reminder['day_name']} о {time_text}",
                reply_markup=builder,
                parse_mode="Markdown"
            )


# Обробник фотографій для групового чату
@router.message(F.photo)
async def handle_photo_inputs(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state == ChatStates.waiting_for_message.state:
        user = message.from_user
        username_str = f"@{user.username}" if user.username else "без юзернейму"
        user_link = f"<a href='tg://user?id={user.id}'>{user.first_name}</a>"
        header = f"💬 <b>Повідомлення від {user_link}</b> ({username_str}):\n"

        try:
            photo_file_id = message.photo[-1].file_id
            caption = message.caption if message.caption else ""
            await bot.send_photo(
                chat_id=GROUP_CHAT_ID,
                photo=photo_file_id,
                caption=header + caption,
                parse_mode="HTML"
            )
            await message.answer("✅ Фото успішно надіслано в чат!", reply_markup=get_back_to_chat_menu_kb())
        except Exception as e:
            logging.error(f"Помилка при пересиланні фото: {e}")
            await message.answer("❌ Сталася помилка при відправці фото у загальний чат.")


async def send_user_reminder(rem_id: int):
    if not CHAT_ID or not NOTIFICATIONS_ENABLED:
        return
    
    for item in reminders_list:
        if item['id'] == rem_id and not item['done']:
            text = f"⏰ **Нагадування!**\n\n{item['text']}"
            await bot.send_message(CHAT_ID, text, parse_mode="Markdown")

# --- РОЗКЛАД УРОКІВ ---

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
        
        if " - " in raw_name:
            parts = raw_name.split(" - ")
            part1 = parts[0].strip()
            part2 = parts[1].strip()
            
            if current_week == 1:
                formatted_name = f"**{get_subject_with_emoji(part1)}** - {get_subject_with_emoji(part2)}"
            else:
                formatted_name = f"{get_subject_with_emoji(part1)} - **{get_subject_with_emoji(part2)}**"
        else:
            formatted_name = get_subject_with_emoji(raw_name)
            
        text += f"▫️ **{num}.** {formatted_name} ({lesson['time']})\n\n"
    
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
    scheduler.start()
    
    # Реєструємо роутер у диспетчері
    dp.include_router(router)
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
