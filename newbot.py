import logging
import sqlite3
import calendar
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from datetime import datetime, timedelta

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)

# Создаем приложение с токеном
application = Application.builder().token("7762715566:AAHgE3JQgE6ouxct7M0Hdy6wYVOMuRpNmWU").build()

# Подключение к базе данных SQLite
conn = sqlite3.connect('bot_database.db')
cursor = conn.cursor()

# Создание таблиц для пользователей, каналов и слотов
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE
)
''')
cursor.execute('''
CREATE TABLE IF NOT EXISTS channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    slot_times TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users (user_id)
)
''')
cursor.execute('''
CREATE TABLE IF NOT EXISTS slots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id INTEGER NOT NULL,
    month TEXT NOT NULL,
    day TEXT NOT NULL,
    time TEXT NOT NULL,
    description TEXT,
    manager_contact TEXT,
    channel_link TEXT,
    price TEXT,
    FOREIGN KEY (channel_id) REFERENCES channels (id)
)
''')
conn.commit()

# Словарь для преобразования числового значения месяца в текстовое представление
MONTHS = {
    "01": "Января", "02": "Февраля", "03": "Марта", "04": "Апреля",
    "05": "Мая", "06": "Июня", "07": "Июля", "08": "Августа",
    "09": "Сентября", "10": "Октября", "11": "Ноября", "12": "Декабря"
}


# Функция для преобразования месяца
def get_month_name(month):
    return MONTHS.get(month.zfill(2), month)


# Генерация клавиатуры для выбора месяца
def generate_month_keyboard():
    keyboard = []
    keyboard.append([InlineKeyboardButton("Январь", callback_data="month_01"),
                     InlineKeyboardButton("Февраль", callback_data="month_02")])
    keyboard.append([InlineKeyboardButton("Март", callback_data="month_03"),
                     InlineKeyboardButton("Апрель", callback_data="month_04")])
    keyboard.append([InlineKeyboardButton("Май", callback_data="month_05"),
                     InlineKeyboardButton("Июнь", callback_data="month_06")])
    keyboard.append([InlineKeyboardButton("Июль", callback_data="month_07"),
                     InlineKeyboardButton("Август", callback_data="month_08")])
    keyboard.append([InlineKeyboardButton("Сентябрь", callback_data="month_09"),
                     InlineKeyboardButton("Октябрь", callback_data="month_10")])
    keyboard.append([InlineKeyboardButton("Ноябрь", callback_data="month_11"),
                     InlineKeyboardButton("Декабрь", callback_data="month_12")])
    keyboard.append([InlineKeyboardButton("Назад", callback_data="back_to_previous_step")])  # Кнопка "Назад"
    return keyboard


# Генерация клавиатуры для главного меню
def generate_main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("Добавить слот", callback_data="add_slots"),
         InlineKeyboardButton("Показать слоты 2.0", callback_data="view_slots_2.0")],  # Новая кнопка
        [InlineKeyboardButton("Статистика", callback_data="statistic"),
         InlineKeyboardButton("Настройки", callback_data="settings")],
        [InlineKeyboardButton("Назад", callback_data="back_to_channel_selection")],  # Кнопка "Назад"
    ]
    return InlineKeyboardMarkup(keyboard)

def generate_slots_interface(booked_days=None):
    """
    Генерирует интерфейс для отображения забронированных дней месяца.

    :param booked_days: Список дней с забронированными слотами.
    :return: InlineKeyboardMarkup с кнопками для дней месяца.
    """
    from datetime import datetime
    import calendar
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    # Названия дней недели
    days_of_week = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    keyboard = [[InlineKeyboardButton(day, callback_data="disabled") for day in days_of_week]]

    # Получаем текущий месяц и год
    year, month = datetime.now().year, datetime.now().month
    first_day_of_week, days_in_month = calendar.monthrange(year, month)
    days_buttons = []

    # Пустые кнопки для выравнивания (до первого дня месяца)
    for _ in range(first_day_of_week):
        days_buttons.append(InlineKeyboardButton(" ", callback_data="disabled"))

    # Генерация кнопок для каждого дня месяца
    for day in range(1, days_in_month + 1):
        text = f"{day}"
        if day in (booked_days or []):  # Добавляем точку к забронированным дням
            text += "."

        callback_data = f"day_info_{month:02}_{day:02}"  # Префикс для забронированных
        days_buttons.append(InlineKeyboardButton(text, callback_data=callback_data))

    # Разбиваем кнопки по строкам (по неделям)
    for i in range(0, len(days_buttons), 7):
        keyboard.append(days_buttons[i:i + 7])

    # Верхние кнопки для переключения периодов
    keyboard.insert(0, [
        InlineKeyboardButton("Свободные на 3 дня", callback_data="free_slots_3_days"),
        InlineKeyboardButton("Свободные на 7 дней", callback_data="free_slots_7_days")
    ])

    # Кнопка поиска
    keyboard.append([InlineKeyboardButton("Поиск", callback_data="search_slots")])

    # Кнопка "Назад"
    keyboard.append([InlineKeyboardButton("Назад", callback_data="back_to_main_menu")])

    return InlineKeyboardMarkup(keyboard)

def get_booked_days(channel_id):
    """
    Возвращает список дней с забронированными слотами для заданного канала.

    :param channel_id: ID канала
    :return: Список уникальных дней (int) с забронированными слотами.
    """
    cursor.execute(
        "SELECT DISTINCT day FROM slots WHERE description IS NOT NULL AND channel_id = ?",
        (channel_id,)
    )
    result = cursor.fetchall()
    return [int(row[0]) for row in result]

# Генерация клавиатуры для меню настроек
def generate_settings_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("Добавить канал", callback_data="add_channel"),
         InlineKeyboardButton("Удалить канал", callback_data="delete_channel")],
        [InlineKeyboardButton("Назад", callback_data="back_to_main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


# Генерация клавиатуры для возврата в главное меню
def generate_back_to_main_menu_keyboard():
    keyboard = []
    keyboard.append([KeyboardButton("Главное меню")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

#Функция для генерации клавиатуры выбора дней:
def generate_day_selection_keyboard(month):
    year = datetime.now().year
    first_day_of_week, days_in_month = calendar.monthrange(year, month)

    # Генерация заголовка с днями недели
    days_of_week = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    keyboard = [[InlineKeyboardButton(day, callback_data="disabled") for day in days_of_week]]

    # Добавляем пустые кнопки для сдвига первого дня месяца
    days_buttons = []
    for _ in range(first_day_of_week):
        days_buttons.append(InlineKeyboardButton(" ", callback_data="disabled"))

    # Добавляем кнопки для каждого дня месяца
    for day in range(1, days_in_month + 1):
        days_buttons.append(InlineKeyboardButton(str(day), callback_data=f"day_{month:02}_{day:02}"))

    # Добавляем пустые кнопки для завершения последней недели (если она не полная)
    remaining_days = len(days_buttons) % 7
    if remaining_days != 0:
        for _ in range(7 - remaining_days):
            days_buttons.append(InlineKeyboardButton(" ", callback_data="disabled"))

    # Разбиваем кнопки по строкам (по 7 кнопок в строке)
    for i in range(0, len(days_buttons), 7):
        keyboard.append(days_buttons[i:i + 7])

    # Добавляем кнопку "Назад"
    keyboard.append([InlineKeyboardButton("Назад", callback_data="back_to_previous_step")])

    return InlineKeyboardMarkup(keyboard)


# Генерация клавиатуры для выбора канала с возможностью удаления
def generate_channel_selection_keyboard(user_id):
    cursor.execute('SELECT name FROM channels WHERE user_id = ?', (user_id,))
    channels = cursor.fetchall()
    keyboard = [[InlineKeyboardButton(channel[0], callback_data=f"select_channel_{channel[0]}")] for channel in channels]
    return InlineKeyboardMarkup(keyboard)


# Генерация клавиатуры для кнопки "Статистика"
def generate_statistic_keyboard():
    keyboard = []
    keyboard.append([InlineKeyboardButton("Статистика", callback_data="statistic")])
    return InlineKeyboardMarkup(keyboard)




# Генерация клавиатуры для подменю "Показать забронированные слоты"
def generate_view_booked_slots_submenu():
    keyboard = [
        [InlineKeyboardButton("На ближайшие три дня", callback_data="view_slots_three_days"),
         InlineKeyboardButton("Ближайшие семь дней", callback_data="view_slots_seven_days")],
        [InlineKeyboardButton("Ближайшие 14 дней", callback_data="view_slots_fourteen_days"),
         InlineKeyboardButton("Все слоты", callback_data="view_slots_all")],
        [InlineKeyboardButton("Назад", callback_data="back_to_previous_step")]
    ]
    return InlineKeyboardMarkup(keyboard)


# Генерация клавиатуры для подменю "Показать свободные слоты"
def generate_view_free_slots_submenu():
    keyboard = [
        [InlineKeyboardButton("На ближайшие три дня", callback_data="view_free_slots_three_days"),
         InlineKeyboardButton("Ближайшие семь дней", callback_data="view_free_slots_seven_days")],
        [InlineKeyboardButton("Ближайшие 14 дней", callback_data="view_free_slots_fourteen_days"),
         InlineKeyboardButton("Назад", callback_data="back_to_previous_step")]
    ]
    return InlineKeyboardMarkup(keyboard)


# Генерация клавиатуры для выбора времени с проверкой на занятость слота
def generate_time_keyboard(channel_id, month, day):
    cursor.execute('SELECT slot_times FROM channels WHERE id = ?', (channel_id,))
    slot_times = cursor.fetchone()[0].split(", ")
    cursor.execute('SELECT time FROM slots WHERE channel_id = ? AND month = ? AND day = ?', (channel_id, month, day))
    existing_times = {row[0] for row in cursor.fetchall()}

    keyboard = []
    keyboard.append([
        InlineKeyboardButton(
            time, callback_data="disabled" if time in existing_times else f"time_{month}_{day}_{time}"
        ) for time in slot_times
    ])
    keyboard.append([InlineKeyboardButton("Назад", callback_data="back_to_previous_step")])
    return InlineKeyboardMarkup(keyboard)


# Функция для проверки наличия слота на то же время в тот же день
def is_slot_taken(channel_id, month, day, time):
    cursor.execute('SELECT 1 FROM slots WHERE channel_id = ? AND month = ? AND day = ? AND time = ?',
                   (channel_id, month, day, time))
    return cursor.fetchone() is not None


# Функция для генерации ответа со слотами
def generate_slots_response(rows, title):
    response = f"{title}:\n\n"
    if rows:
        # Найти ближайший слот по дате и времени
        now = datetime.now()
        closest_slot = min(rows, key=lambda row: datetime.strptime(f"{row[3]}.{row[2]}.{now.year} {row[4]}", "%d.%m.%Y %H:%M"))
        month_name = get_month_name(closest_slot[2])
        response += (f"{closest_slot[3]} {month_name}\nВремя: {closest_slot[4]}\nОписание: {closest_slot[5]}\n"
                     f"Контакты: {closest_slot[6]}\nСсылка: {closest_slot[7]}\nСтоимость: {closest_slot[8]} \n\n")
    else:
        response += "Нет доступных слотов."
    return response


# Функция для генерации ответа со свободными слотами на ближайшие три дня
def generate_free_slots_three_days_response(rows, title, slot_times):
    response = f"{title}:\n\n"
    today = datetime.now()
    end_of_three_days = today + timedelta(days=2)
    slots_by_day = {}

    for single_date in (today + timedelta(days=i) for i in range((end_of_three_days - today).days + 1)):
        formatted_day = f"{single_date.day:02}"
        month = single_date.strftime("%m")
        slots_by_day[formatted_day] = []

        for time in slot_times:
            # Проверяем, свободен ли слот
            if not any(row[3] == formatted_day and row[2] == month and row[4] == time for row in rows):
                slots_by_day[formatted_day].append(time)

    for day, times in slots_by_day.items():
        if times:
            response += f"{int(day)} {get_month_name(month)}:\n"
            response += "\n".join([f"{time} свободен" for time in times]) + "\n\n"

    if not any(slots_by_day.values()):
        response += "Нет доступных слотов."

    return response



# Функция для генерации ответа со свободными слотами на ближайшие семь дней
def generate_free_slots_seven_days_response(rows, title, slot_times):
    response = f"{title}:\n\n"
    today = datetime.now()
    end_of_seven_days = today + timedelta(days=6)
    slots_by_day = {}

    # Генерация диапазона дат
    for single_date in (today + timedelta(days=i) for i in range((end_of_seven_days - today).days + 1)):
        formatted_day = f"{single_date.day:02}"  # Приведение дня к формату двух цифр
        month = single_date.strftime("%m")
        slots_by_day[f"{formatted_day}.{month}"] = []

        # Проверка каждого времени на занятость
        for time in slot_times:
            if not any(row[3] == formatted_day and row[2] == month and row[4] == time for row in rows):
                slots_by_day[f"{formatted_day}.{month}"].append(time)

    # Формирование ответа
    for key, times in slots_by_day.items():
        day, month = key.split(".")
        if times:
            response += f"{int(day)} {get_month_name(month)}:\n"
            response += "\n".join([f"{time} свободен" for time in times]) + "\n\n"

    if not any(slots_by_day.values()):
        response += "Нет доступных слотов."

    return response




# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    context.user_data.pop("slot_info", None)  # Сброс информации о слоте
    cursor.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (user_id,))
    conn.commit()

    cursor.execute('SELECT name FROM channels WHERE user_id = ?', (user_id,))
    channels = cursor.fetchall()

    if not channels:
        await update.effective_message.reply_text("Пожалуйста, введите название вашего канала:",
                                                  reply_markup=generate_back_to_main_menu_keyboard())
    else:
        context.user_data["channels"] = {channel[0]: channel[0] for channel in channels}
        reply_markup = generate_channel_selection_keyboard(user_id)
        await update.effective_message.reply_text("Выберите канал или добавьте новый:", reply_markup=reply_markup)


# Команда /add
async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["previous_steps"] = ["main_menu"]
    keyboard = generate_month_keyboard()
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.effective_message.reply_text("Пожалуйста, выберите месяц, чтобы добавить рекламный слот:",
                                              reply_markup=reply_markup)


# Команда /menu
async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "channel_name" not in context.user_data:
        await update.effective_message.reply_text("Пожалуйста, введите название вашего канала:")
        return

    reply_markup = generate_main_menu_keyboard()
    cursor.execute('SELECT * FROM slots WHERE channel_id = ? ORDER BY date(day || "." || month || "." || strftime("%Y", "now")), time', (context.user_data["channel_id"],))
    rows = cursor.fetchall()
    slot_info = generate_slots_response(rows, "Информация о ближайшем слоте") if rows else "Нет доступных слотов."

    if update.message:
        await update.message.reply_text(
            f"Вы выбрали канал '{context.user_data['channel_name']}'. Как я могу помочь вам сегодня? Выберите действие ниже:\n\n{slot_info}",
            reply_markup=reply_markup
        )
    elif update.callback_query:
        await update.callback_query.message.edit_text(
            f"Вы выбрали канал '{context.user_data['channel_name']}'. Как я могу помочь вам сегодня? Выберите действие ниже:\n\n{slot_info}",
            reply_markup=reply_markup
        )


# Команда /view
async def view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["previous_steps"] = ["main_menu"]
    reply_markup = generate_view_slots_submenu()
    await update.effective_message.reply_text("Вы хотели бы посмотреть уже забронированные слоты или свободные?", reply_markup=reply_markup)


# Генерация клавиатуры для подменю "Статистика"
def generate_statistic_submenu():
    keyboard = [
        [InlineKeyboardButton("За этот месяц", callback_data="statistic_current_month"),
         InlineKeyboardButton("За предыдущий месяц", callback_data="statistic_previous_month")],
        [InlineKeyboardButton("Назад", callback_data="back_to_main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)


# Команда /statistics
async def statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply_markup = generate_statistic_submenu()
    await update.effective_message.reply_text("Выберите период для просмотра статистики:", reply_markup=reply_markup)


# Функция для получения статистики
async def get_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE, month_offset=0):
    current_date = datetime.now()
    target_date = current_date - timedelta(days=current_date.day - 1) - timedelta(days=30 * month_offset)
    target_month = target_date.strftime("%m")
    cursor.execute('SELECT * FROM slots WHERE channel_id = ? AND month = ?',
                   (context.user_data["channel_id"], target_month))
    rows = cursor.fetchall()

    if rows:
        total_slots = len(rows)
        total_profit = 0

        for row in rows:
            try:
                price = float(row[8])
                total_profit += price
            except ValueError:
                logging.error(f"Ошибка при преобразовании цены для строки: {row}")

        response = (
            f"Статистика за {get_month_name(target_month)}:\n"
            f"Количество проданных слотов: {total_slots}\n"
            f"Общая прибыль: {total_profit:.2f} рублей."
        )
    else:
        response = "У нас нет данных за выбранный месяц. Пожалуйста, попробуйте позже."

    # Используем edit_message_text вместо reply_text
    if update.callback_query:
        await update.callback_query.edit_message_text(response, reply_markup=generate_statistic_submenu())
    else:
        await update.message.reply_text(response, reply_markup=generate_statistic_submenu())


# Обработчик CallbackQuery
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "add_channel":
        context.user_data.pop("slot_info", None)  # Сброс информации о слоте
        await query.edit_message_text("Пожалуйста, введите название нового канала:")
        context.user_data.pop("channel_name", None)
        context.user_data.pop("slot_times", None)
        return

    if query.data == "delete_channel":
        user_id = update.effective_user.id

        # Получаем список каналов пользователя
        cursor.execute("SELECT name FROM channels WHERE user_id = ?", (user_id,))
        channels = cursor.fetchall()

        if channels:
            # Формируем список каналов
            channel_list = "\n".join([f"- {channel[0]}" for channel in channels])
            message_text = (
                "Пожалуйста, введите название канала, который вы хотите удалить.\n\n"
                "Ваши каналы:\n"
                f"{channel_list}"
            )
        else:
            # Если каналов нет
            message_text = (
                "У вас пока нет добавленных каналов. Пожалуйста, сначала добавьте канал."
            )

        # Отправляем сообщение с текстом и клавиатурой
        await query.edit_message_text(
            message_text,
            reply_markup=generate_settings_menu_keyboard()
        )

        context.user_data["delete_channel"] = True
        return

    if query.data.startswith("select_channel_"):
        channel_name = query.data.split("select_channel_")[1]
        context.user_data["channel_name"] = channel_name
        cursor.execute(
            'SELECT id, slot_times FROM channels WHERE user_id = ? AND name = ?',
            (update.effective_user.id, channel_name)
        )
        channel = cursor.fetchone()
        if channel:
            context.user_data["channel_id"] = channel[0]
            context.user_data["slot_times"] = channel[1].split(", ")


            cursor.execute('SELECT * FROM slots WHERE channel_id = ?', (context.user_data["channel_id"],))
            rows = cursor.fetchall()
            slots_info = generate_slots_response(rows, "Информация о слотах") if rows else "Нет доступных слотов."

            reply_markup = generate_main_menu_keyboard()
            await query.edit_message_text(
                f"Вы выбрали канал '{context.user_data['channel_name']}'. Как я могу помочь вам сегодня? Выберите действие ниже:\n\n{slots_info}",
                reply_markup=reply_markup
            )
        else:
            await query.edit_message_text("Ошибка: канал не найден. Пожалуйста, попробуйте снова.")
        return

    if query.data == "main_menu":
        await menu(update, context)
        return

    elif query.data == "add_slots":
        context.user_data["previous_steps"] = ["main_menu"]
        keyboard = generate_month_keyboard()
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Пожалуйста, выберите месяц, чтобы добавить рекламный слот:",
                                      reply_markup=reply_markup)


    elif query.data == "back_to_channel_selection":
        user_id = update.effective_user.id
        reply_markup = generate_channel_selection_keyboard(user_id)
        await query.edit_message_text("Выберите канал или добавьте новый:", reply_markup=reply_markup)



    elif query.data == "settings":
        reply_markup = generate_settings_menu_keyboard()
        await query.edit_message_text("Настройки:", reply_markup=reply_markup)

    elif query.data == "statistic":
        if "previous_steps" not in context.user_data:
            context.user_data["previous_steps"] = []

        context.user_data["previous_steps"].append("main_menu")

        reply_markup = generate_statistic_submenu()
        await query.edit_message_text("Выберите период для просмотра статистики:", reply_markup=reply_markup)







    elif query.data == "free_slots_3_days":

        channel_id = context.user_data.get("channel_id")

        if not channel_id:
            await query.edit_message_text("Выберите канал перед просмотром слотов.")

            return

        # Получаем все временные слоты из столбца slot_times таблицы channels

        cursor.execute("SELECT slot_times FROM channels WHERE id = ?", (channel_id,))

        result = cursor.fetchone()

        if not result:
            await query.edit_message_text("Ошибка: не удалось найти временные слоты для выбранного канала.")

            return

        all_possible_slots = result[0].split(", ")

        # Проверяем слоты на сегодня и следующие 2 дня

        response = "Свободные слоты на ближайшие 3 дня:\n\n"

        current_date = datetime.now()

        for i in range(3):  # Проверяем слоты на сегодня и следующие 2 дня

            day_to_check = current_date + timedelta(days=i)

            month_str = day_to_check.strftime("%m")

            day_str = day_to_check.strftime("%d")

            # Получаем занятые слоты из таблицы slots

            cursor.execute(

                "SELECT time FROM slots WHERE channel_id = ? AND month = ? AND day = ?",

                (channel_id, month_str, day_str)

            )

            booked_slots = [row[0] for row in cursor.fetchall()]

            # Определяем свободные слоты

            free_slots = [slot for slot in all_possible_slots if slot not in booked_slots]

            if free_slots:

                response += f"{day_str}.{month_str}:\n"

                for slot in free_slots:
                    response += f"  - Время: {slot}\n"

                response += "\n"

            else:

                response += f"{day_str}.{month_str}: Нет свободных слотов.\n\n"

        # Добавляем кнопку "Назад"

        reply_markup = InlineKeyboardMarkup([

            [InlineKeyboardButton("Назад", callback_data="view_slots_2.0")]

        ])

        await query.edit_message_text(response, reply_markup=reply_markup)


    elif query.data == "free_slots_7_days":

        channel_id = context.user_data.get("channel_id")

        if not channel_id:
            await query.edit_message_text("Выберите канал перед просмотром слотов.")

            return

        # Получаем все временные слоты из столбца slot_times таблицы channels

        cursor.execute("SELECT slot_times FROM channels WHERE id = ?", (channel_id,))

        result = cursor.fetchone()

        if not result:
            await query.edit_message_text("Ошибка: не удалось найти временные слоты для выбранного канала.")

            return

        all_possible_slots = result[0].split(", ")

        # Проверяем слоты на ближайшие 7 дней

        response = "Свободные слоты на ближайшие 7 дней:\n\n"

        current_date = datetime.now()

        for i in range(7):  # Проверяем слоты на сегодня и следующие 6 дней

            day_to_check = current_date + timedelta(days=i)

            month_str = day_to_check.strftime("%m")

            day_str = day_to_check.strftime("%d")

            # Получаем занятые слоты из таблицы slots

            cursor.execute(

                "SELECT time FROM slots WHERE channel_id = ? AND month = ? AND day = ?",

                (channel_id, month_str, day_str)

            )

            booked_slots = [row[0] for row in cursor.fetchall()]

            # Определяем свободные слоты

            free_slots = [slot for slot in all_possible_slots if slot not in booked_slots]

            if free_slots:

                response += f"{day_str}.{month_str}:\n"

                for slot in free_slots:
                    response += f"  - Время: {slot}\n"

                response += "\n"

            else:

                response += f"{day_str}.{month_str}: Нет свободных слотов.\n\n"

        # Добавляем кнопку "Назад"

        reply_markup = InlineKeyboardMarkup([

            [InlineKeyboardButton("Назад", callback_data="view_slots_2.0")]

        ])

        await query.edit_message_text(response, reply_markup=reply_markup)




    elif query.data.startswith("day_info_"):

        print(f"Получен callback_data: {query.data}")  # Для отладки

        parts = query.data.split("_")

        if len(parts) != 4:  # Проверяем, что формат данных корректен

            print("Некорректный формат данных в callback_data")

            await query.answer("Некорректный формат данных.")

            return

        month = parts[2]

        day = parts[3]

        print(f"Извлечён месяц: {month}, день: {day}")

        channel_id = context.user_data.get("channel_id")

        print(f"Проверка channel_id: {channel_id}")

        if not channel_id:
            print("channel_id отсутствует, завершение обработчика.")

            await query.edit_message_text("Ошибка: канал не выбран. Пожалуйста, выберите канал и попробуйте снова.")

            return

        print(f"Параметры запроса: channel_id={channel_id}, month={month}, day={day}")

        # Выполняем SQL-запрос

        cursor.execute(

            "SELECT time, description, manager_contact, channel_link, price "

            "FROM slots WHERE channel_id = ? AND month = ? AND day = ? AND description IS NOT NULL",

            (channel_id, month, day)

        )

        slots = cursor.fetchall()

        print(f"Результат запроса: {slots}")

        # Формируем сообщение

        if slots:

            response = f"Забронированные слоты на {day}.{month}:\n\n"

            for slot in slots:
                response += (

                    f"Время: {slot[0]}\n"

                    f"Описание: {slot[1]}\n"

                    f"Контакты: {slot[2]}\n"

                    f"Ссылка: {slot[3]}\n"

                    f"Стоимость: {slot[4]} руб.\n\n"

                )

        else:

            response = f"На {day}.{month} нет забронированных слотов."

        # Кнопка "Назад"

        reply_markup = InlineKeyboardMarkup([

            [InlineKeyboardButton("Назад к календарю", callback_data="back_to_calendar")]

        ])

        # Отправляем сообщение

        await query.edit_message_text(response, reply_markup=reply_markup)



    elif query.data == "back_to_calendar":
        channel_id = context.user_data.get("channel_id")

        if not channel_id:
            await query.edit_message_text("Выберите канал перед просмотром календаря.")
            return

        # Получаем забронированные дни
        booked_days = get_booked_days(channel_id)

        # Генерируем интерфейс календаря
        reply_markup = generate_slots_interface(booked_days)

        await query.edit_message_text("Показ слотов 2.0:", reply_markup=reply_markup)




    elif query.data == "view_slots_2.0":

        channel_id = context.user_data.get("channel_id")

        if not channel_id:
            await query.edit_message_text("Выберите канал перед просмотром слотов.")

            return

        # Получаем забронированные дни

        booked_days = get_booked_days(channel_id)

        # Генерируем интерфейс календаря

        reply_markup = generate_slots_interface(booked_days)

        await query.edit_message_text("Показ слотов 2.0:", reply_markup=reply_markup)


    elif query.data == "booked_slots":

        channel_id = context.user_data.get("channel_id")

        if not channel_id:
            await query.edit_message_text("Выберите канал перед просмотром слотов.")

            return

        # Получаем забронированные дни

        booked_days = get_booked_days(channel_id)

        reply_markup = generate_slots_interface(booked_days)

        await query.edit_message_text("Забронированные слоты:", reply_markup=reply_markup)

    elif query.data == "generate_channel_selection_keyboard":

        # Возвращаемся к выбору канала

        user_id = update.effective_user.id

        reply_markup = generate_channel_selection_keyboard(user_id)

        await query.edit_message_text("Выберите канал или добавьте новый:", reply_markup=reply_markup)

    elif query.data == "statistic_current_month":
        await get_statistics(update, context, month_offset=0)

    elif query.data == "statistic_previous_month":
        await get_statistics(update, context, month_offset=1)



    elif query.data.startswith("month_"):

        # Получаем месяц из callback_data

        month = int(query.data.split("_")[1])  # Месяц в формате числа

        context.user_data["month"] = month

        context.user_data["previous_steps"].append("month_selection")

        # Определяем год и получаем информацию о месяце

        year = datetime.now().year  # Используем текущий год

        first_day_of_week, days_in_month = calendar.monthrange(year, month)

        # Генерация клавиатуры с учётом дней недели

        days_of_week = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

        keyboard = [[InlineKeyboardButton(day, callback_data="disabled") for day in days_of_week]]

        # Добавляем пустые кнопки для сдвига первого дня месяца

        days_buttons = []

        for _ in range(first_day_of_week):
            days_buttons.append(InlineKeyboardButton(" ", callback_data="disabled"))

        # Добавляем кнопки для каждого дня месяца

        for day in range(1, days_in_month + 1):
            days_buttons.append(InlineKeyboardButton(str(day), callback_data=f"day_{month:02}_{day:02}"))

        # Добавляем пустые кнопки для завершения последней недели (если она не полная)

        remaining_days = len(days_buttons) % 7

        if remaining_days != 0:

            for _ in range(7 - remaining_days):
                days_buttons.append(InlineKeyboardButton(" ", callback_data="disabled"))

        # Разбиваем кнопки по неделям (по 7 кнопок в строке)

        for i in range(0, len(days_buttons), 7):
            keyboard.append(days_buttons[i:i + 7])

        # Добавляем кнопку "Назад"

        keyboard.append([InlineKeyboardButton("Назад", callback_data="back_to_previous_step")])

        # Отправляем пользователю обновлённое сообщение

        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(

            f"Теперь выберите день для месяца {get_month_name(str(month).zfill(2))}:",

            reply_markup=reply_markup

        )

    elif query.data.startswith("day_"):
        parts = query.data.split("_")
        month, day = parts[1], parts[2]
        context.user_data["day"] = day
        context.user_data["previous_steps"].append("day_selection")

        reply_markup = generate_time_keyboard(context.user_data["channel_id"], month, day)
        await query.edit_message_text(f"Теперь выберите удобное время для {day}.{month}:", reply_markup=reply_markup)

    elif query.data.startswith("time_"):
        parts = query.data.split("_")
        month, day, time = parts[1], parts[2], parts[3]
        context.user_data["time"] = time
        context.user_data["previous_steps"].append("time_selection")

        # Проверка на наличие слота на то же время в тот же день
        if is_slot_taken(context.user_data["channel_id"], month, day, time):
            await query.edit_message_text(
                f"Ошибка: Слот на {day} {get_month_name(month)} в {time} уже существует. Пожалуйста, выберите другое время.",
                reply_markup=generate_time_keyboard(context.user_data["channel_id"], month, day))
            return

        await query.edit_message_text(
            f"Вы выбрали {day}.{month} в {time}. Пожалуйста, напишите описание для этого слота.", reply_markup=None)

        context.user_data["slot_info"] = {"month": month, "day": day, "time": time}


    elif query.data == "back_to_previous_step":

        previous_steps = context.user_data.get("previous_steps", ["main_menu"])

        if previous_steps:

            previous_step = previous_steps.pop()

            context.user_data["previous_steps"] = previous_steps

            # Универсальная обработка возврата

            if previous_step == "main_menu":

                await menu(update, context)

            elif previous_step == "month_selection":

                reply_markup = InlineKeyboardMarkup(generate_month_keyboard())

                await query.edit_message_text("Пожалуйста, выберите месяц для добавления рекламного слота:",
                                              reply_markup=reply_markup)

            elif previous_step == "day_selection":

                month = context.user_data["month"]

                reply_markup = generate_day_selection_keyboard(month)

                await query.edit_message_text(f"Теперь выберите день для месяца {get_month_name(str(month).zfill(2))}:",
                                              reply_markup=reply_markup)

            elif previous_step == "time_selection":

                month = context.user_data["month"]

                day = context.user_data["day"]

                reply_markup = generate_time_keyboard(context.user_data["channel_id"], month, day)

                await query.edit_message_text(f"Теперь выберите удобное время для {day}.{month}:",
                                              reply_markup=reply_markup)

            elif previous_step == "view_slots":
                reply_markup = generate_view_slots_submenu()
                await query.edit_message_text("Вы хотели бы посмотреть уже забронированные слоты или свободные?", reply_markup=reply_markup)

            elif previous_step == "view_booked_slots":
                reply_markup = generate_view_booked_slots_submenu()
                await query.edit_message_text("Выберите период для просмотра забронированных слотов:",
                                              reply_markup=reply_markup)

            elif previous_step == "month_selection":
                reply_markup = InlineKeyboardMarkup(generate_month_keyboard())
                await query.edit_message_text("Пожалуйста, выберите месяц для добавления рекламного слота:",
                                              reply_markup=reply_markup)




            elif previous_step == "time_selection":
                month = context.user_data.get("month")
                day = context.user_data.get("day")
                keyboard = []
                keyboard.append([InlineKeyboardButton("15:00", callback_data=f"time_{month}_{day}_15:00")])
                keyboard.append([InlineKeyboardButton("19:00", callback_data=f"time_{month}_{day}_19:00")])
                keyboard.append([InlineKeyboardButton("Назад", callback_data="back_to_previous_step")])
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(f"Теперь выберите время для {day}.{month}:", reply_markup=reply_markup)

    elif query.data == "back_to_main_menu":
        await menu(update, context)


# Обработчик описания
async def handle_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_slot = update.message.text.strip()

    if user_slot.lower() == "главное меню":
        await start(update, context)
        return

    if "slot_info" not in context.user_data:
        await update.message.reply_text("Ошибка: информация о слоте отсутствует. Пожалуйста, начните заново.")
        return

    if "description" not in context.user_data["slot_info"]:
        context.user_data["slot_info"]["description"] = user_slot
        await update.message.reply_text(f"Спасибо! Теперь введите контактные данные менеджера.")

    elif "manager_contact" not in context.user_data["slot_info"]:
        context.user_data["slot_info"]["manager_contact"] = user_slot
        await update.message.reply_text(f"Контактные данные менеджера добавлены. Пожалуйста, введите ссылку на канал.")

    elif "channel_link" not in context.user_data["slot_info"]:
        context.user_data["slot_info"]["channel_link"] = user_slot
        await update.message.reply_text(f"Ссылка на канал добавлена. Пожалуйста, введите стоимость рекламы.")

    elif "price" not in context.user_data["slot_info"]:
        context.user_data["slot_info"]["price"] = user_slot
        slot_info = context.user_data["slot_info"]
        slot_info["channel_id"] = context.user_data["channel_id"]

        # Проверка на наличие слота на то же время в тот же день
        if is_slot_taken(slot_info["channel_id"], slot_info["month"], slot_info["day"], slot_info["time"]):
            await update.message.reply_text(
                f"Ошибка: Слот на {slot_info['day']} {get_month_name(slot_info['month'])} в {slot_info['time']} уже существует. Пожалуйста, выберите другое время.",
                reply_markup=generate_time_keyboard(slot_info["channel_id"], slot_info["month"], slot_info["day"]))
            return

        logging.debug(f"Вставка слота: {slot_info}")

        cursor.execute(
            'INSERT INTO slots (channel_id, month, day, time, description, manager_contact, channel_link, price) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (slot_info["channel_id"], slot_info["month"], slot_info["day"], slot_info["time"], slot_info["description"],
             slot_info["manager_contact"], slot_info["channel_link"], slot_info["price"]))
        conn.commit()

        await update.message.reply_text(
            f"Рекламный слот на {slot_info['day']} {get_month_name(slot_info['month'])} в {slot_info['time']} успешно добавлен!\n"
            f"Описание: {slot_info['description']}\n"
            f"Контакты менеджера: {slot_info['manager_contact']}\n"
            f"Ссылка на канал: {slot_info['channel_link']}\n"
            f"Стоимость: {slot_info['price']} руб.")

        context.user_data["slot_info"] = {}
        await menu(update, context)


# Обработчик ввода названия канала
async def handle_channel_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channel_name = update.message.text.strip()
    user_id = update.effective_user.id

    context.user_data["channel_name"] = channel_name
    await update.message.reply_text(f"Введите время слотов через запятую (например, 15:00, 19:00):")


# Обработчик ввода времени слотов
async def handle_slot_times(update: Update, context: ContextTypes.DEFAULT_TYPE):
    slot_times = update.message.text.strip()
    user_id = update.effective_user.id

    cursor.execute(
        'INSERT INTO channels (user_id, name, slot_times) VALUES (?, ?, ?)',
        (user_id, context.user_data["channel_name"], slot_times)
    )
    conn.commit()

    context.user_data["channel_id"] = cursor.lastrowid
    context.user_data["slot_times"] = slot_times

    # Обновление информации о каналах в user_data
    if "channels" not in context.user_data:
        context.user_data["channels"] = {}
    context.user_data["channels"][context.user_data["channel_name"]] = context.user_data["channel_name"]

    await update.message.reply_text(f"Канал '{context.user_data['channel_name']}' успешно добавлен.",
                                    reply_markup=generate_back_to_main_menu_keyboard())
    await start(update, context)


# Обработчик ввода названия канала для удаления
async def handle_delete_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channel_name = update.message.text.strip()
    user_id = update.effective_user.id

    cursor.execute('SELECT id FROM channels WHERE user_id = ? AND name = ?', (user_id, channel_name))
    channel = cursor.fetchone()
    if (channel):
        channel_id = channel[0]
        cursor.execute('DELETE FROM slots WHERE channel_id = ?', (channel_id,))
        cursor.execute('DELETE FROM channels WHERE id = ?', (channel_id,))
        conn.commit()
        await update.message.reply_text(f"Канал '{channel_name}' успешно удален.",
                                        reply_markup=generate_back_to_main_menu_keyboard())
    else:
        await update.message.reply_text(f"Ошибка: канал '{channel_name}' не найден. Пожалуйста, попробуйте снова.",
                                        reply_markup=generate_back_to_main_menu_keyboard())
    context.user_data.pop("delete_channel", None)


# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    context.user_data.pop("slot_info", None)  # Сброс информации о слоте
    cursor.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (user_id,))
    conn.commit()

    cursor.execute('SELECT name FROM channels WHERE user_id = ?', (user_id,))
    channels = cursor.fetchall()

    if not channels:
        await update.effective_message.reply_text("Добро пожаловать!\n\n"
            "Этот бот предназначен для управления рекламными слотами в ваших Telegram-каналах. Основные возможности:\n\n"
            "1. Добавление множества каналов. Вы можете задать доступные времена для рекламных слотов.\n"
            "2. Управление слотами. Просматривайте занятые и свободные слоты, добавляйте новые.\n"
            "3. Анализ статистики. Узнавайте, сколько слотов продано и какая общая прибыль.\n\n"
            "Для начала работы введите название вашего канала, и я зарегистрирую его в системе.",
                                                  reply_markup=generate_back_to_main_menu_keyboard())
    else:
        context.user_data["channels"] = {channel[0]: channel[0] for channel in channels}
        reply_markup = generate_channel_selection_keyboard(user_id)
        await update.effective_message.reply_text("Выберите канал или добавьте новый:", reply_markup=reply_markup)


# Обработчик сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text.strip()

    if user_message.lower() == "главное меню":
        await start(update, context)
        return

    if "delete_channel" in context.user_data:
        await handle_delete_channel(update, context)
    elif "slot_info" in context.user_data:
        await handle_description(update, context)
    elif "channel_name" not in context.user_data:
        await handle_channel_name(update, context)
    elif "slot_times" not in context.user_data:
        await handle_slot_times(update, context)
    else:
        await update.message.reply_text("Неизвестная команда. Пожалуйста, используйте кнопки для навигации.",
                                        reply_markup=generate_back_to_main_menu_keyboard())


# Регистрация обработчиков
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("add", add))
application.add_handler(CommandHandler("menu", menu))
application.add_handler(CommandHandler("view", view))
application.add_handler(CommandHandler("statistics", statistics))
application.add_handler(CallbackQueryHandler(button_handler))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# Запуск бота
application.run_polling()
