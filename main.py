import aiosqlite
from fake_useragent import UserAgent
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
import aiohttp
import openpyxl

# Пути к базам данных
DB_PATH_VACANCIES = 'vacancies.db'
DB_PATH_USERS = 'users.db'

storage = MemoryStorage()

# Токен API для бота
API_TOKEN = '7418121276:AAGhBCSglrlN5kz53vZqbk_G9Km_Q3GHVSc'
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=storage)
dp.middleware.setup(LoggingMiddleware())
ADMIN_USER_ID = 1473547063

# Классы для определения состояний
class Form(StatesGroup):
    keyword = State()  # Ключевое слово для поиска
    vacancies_count = State()
    table_choice = State()  # Выбор таблицы пользователем
    filter_table_choice = State()

class FilterForm(StatesGroup): #Отдльный класс состояний для определения состояния выбора вильтра
    employment = State()
    experience = State()
    schedule = State()

# Списки для фильтров
employment_values = [
    "Пропустить",
    "Полная занятость",
    "Частичная занятость",
    "Проектная работа",
    "Волонтерство",
    "Стажировка"
]

experience_values = [
    "Пропустить",
    "Нет опыта",
    "От 1 года до 3 лет",
    "От 3 до 6 лет",
    "Более 6 лет"
]

schedule_values = [
    "Пропустить",
    "Полный день",
    "Сменный график",
    "Гибкий график",
    "Удаленная работа",
    "Вахтовый метод"
]


### Функции и их описание


# Функция для проверки длины ключевого слова
async def is_valid_length(keyword):
    MIN_KEYWORD_LENGTH = 3
    MAX_KEYWORD_LENGTH = 20
    #Так идет отсечение коротких и длинных запросов, которые могут поломать бота
    return MIN_KEYWORD_LENGTH <= len(keyword) <= MAX_KEYWORD_LENGTH

# Инициализация базы данных пользователей
async def init_user_db():
    async with aiosqlite.connect(DB_PATH_USERS) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                search_keyword TEXT
            )
        ''')
        await db.commit()

# Инициализация базы данных вакансий
async def init_db(user_id, keyword):
    #При каждом новом запросе о поиске ваканси, создается уникальная таблица,
    #название которой состоит из "vacancies" + Телеграмм id пользователя + слово, которое использовалось для поиска
    table_name = f"vacancies_{user_id}_{keyword}"
    async with aiosqlite.connect(DB_PATH_VACANCIES) as db:
        await db.execute(f'''
            CREATE TABLE IF NOT EXISTS "{table_name}" (
                id TEXT PRIMARY KEY,
                title TEXT,
                url TEXT,
                requirement TEXT,
                responsibility TEXT,
                schedule TEXT,
                experience TEXT,
                employment TEXT,
                company_name TEXT,
                salary TEXT
            )
        ''')
        await db.commit()
    return table_name

# Асинхронная функция для получения вакансий и сохранения их в базу данных
async def get_vacancies(text, message: types.Message, user_id):
    url = "https://api.hh.ru/vacancies"
    user_agent = UserAgent().random

    params = {
        "text": text,
        "area": 1,
        "per_page": 100,  # Запрашиваем максимальное количество вакансий за раз
        "only_with_salary": 1
    }
    headers = {
        "User-Agent": user_agent
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, headers=headers) as response:
            if response.status == 200:
                json_data = await response.json()
                vacancies = json_data['items']
                if len(vacancies) >= 3:
                    table_name = await init_db(user_id, text)
                    await add_vacancies_to_db(vacancies, table_name)
                    await message.reply(
                        f"Поиск по ключевому слову '{text}' начат. Вакансии успешно добавлены в базу данных.")
                else:
                    # Если вакансий меньше трех, отправляем сообщение о том, что вакансии не найдены
                    await message.reply("Не найдено вакансий по вашему запросу.")
            else:
                await message.reply(f"Ошибка запроса к API: HTTP статус {response.status}")

# Функция для добавления вакансий в базу данных
async def add_vacancies_to_db(vacancies, table_name):
    async with aiosqlite.connect(DB_PATH_VACANCIES) as db:
        for vacancy in vacancies:
            id = vacancy.get("id")
            title = vacancy.get("name")
            url = vacancy.get("alternate_url")
            requirement = vacancy.get("snippet", {}).get("requirement", "Не указано")
            responsibility = vacancy.get("snippet", {}).get("responsibility", "Не указано")
            experience = vacancy.get("experience", {}).get("name", "Не указано")
            employment = vacancy.get("employment", {}).get("name", "Не указано")
            schedule = vacancy.get("schedule", {}).get("name", "Не указано")
            company_name = vacancy.get("employer", {}).get("name", "Не указано")
            salary_info = vacancy.get("salary")
            salary = 'Не указано'
            requirement = str(requirement).replace('<highlighttext>', '').replace('</highlighttext>', '')
            responsibility = str(responsibility).replace('<highlighttext>', '').replace('</highlighttext>', '')
            if salary_info:
                salary = f"{salary_info.get('from', '—')} — {salary_info.get('to', '—')} {salary_info.get('currency', '—')}"

            if not all([id, title, url, requirement, responsibility, company_name]):
                print(f"Пропускаем вакансию {id} из-за отсутствия данных")
                continue

            try:
                await db.execute(f'''INSERT INTO "{table_name}" (id, title, url, requirement, responsibility, schedule, experience, employment, company_name, salary)
                                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                                        ''',
                                 (id, title, url, requirement, responsibility, schedule, experience, employment, company_name, salary))
                print(f"Вакансия {id} добавлена в базу данных")
            except Exception as e:
                print(f"Ошибка при добавлении вакансии {id}: {e}")
        await db.commit()

# Функция для получения списка ключевых слов, связанных с пользователем
async def get_user_keywords(user_id):
    async with aiosqlite.connect(DB_PATH_USERS) as db:
        cursor = await db.execute('SELECT search_keyword FROM users WHERE user_id = ?', (user_id,))
        keywords = await cursor.fetchall()
        return [keyword[0] for keyword in keywords if keyword[0]]

# Функция для получения списка названий таблиц для пользователя
async def get_user_table_names(user_id):
    async with aiosqlite.connect(DB_PATH_VACANCIES) as db:
        cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE ?", (f'vacancies_{user_id}_%',))
        tables = await cursor.fetchall()
        return [table[0] for table in tables]

# Функция для выгрузки вакансий в файл Excel
async def export_vacancies_to_excel(table_name, message: types.Message):
    async with aiosqlite.connect(DB_PATH_VACANCIES) as db:
        cursor = await db.execute(f'SELECT * FROM "{table_name}"')
        vacancies = await cursor.fetchall()
        if vacancies:
            # Создаем новый файл Excel
            wb = openpyxl.Workbook()
            ws = wb.active
            # Заголовки столбцов
            ws.append(['ID', 'Название', 'URL', 'Требования', 'Обязанности', 'График', 'Опыт', 'Тип занятости', 'Компания', 'Зарплата'])
            # Добавляем данные вакансий
            for vacancy in vacancies:
                ws.append([
                    vacancy[0],  # ID
                    vacancy[1],  # Название
                    vacancy[2],  # URL
                    vacancy[3],  # Требования
                    vacancy[4],  # Обязанности
                    vacancy[5],  # График
                    vacancy[6],  # Опыт
                    vacancy[7],  # Тип занятости
                    vacancy[8],  # Компания
                    vacancy[9]   # Зарплата
                ])
            # Сохраняем файл
            excel_file = f'{table_name}.xlsx'
            wb.save(excel_file)
            # Отправляем файл пользователю
            with open(excel_file, 'rb') as file:
                await bot.send_document(message.chat.id, file, caption='Ой ой ой...\n'
                                                                       'Я уверен, что вам будет трудно читать такое количество вакансий :)\n'
                                                                       'Для вас я специально сделал табличку вакансий, которую вы сможете сохранить у себя и посмотреть содержимое в Excel')
        else:
            await message.reply("Вакансии не найдены.")

# Функция для получения вакансий из базы данных, начиная с последней
async def get_vacancies_from_db(table_name, limit):
    async with aiosqlite.connect(DB_PATH_VACANCIES) as db:
        # Изменяем запрос, чтобы сортировать вакансии по убыванию ID и получать последние записи
        cursor = await db.execute(f'SELECT * FROM "{table_name}" ORDER BY ROWID DESC LIMIT ?', (limit,))
        rows = await cursor.fetchall()
        # Возвращаем вакансии в обратном порядке, чтобы они шли от самой новой к старой
        return [
            {
                'title': row[1],
                'url': row[2],
                'requirement': row[3],
                'responsibility': row[4],
                'schedule': row[5],
                'experience': row[6],
                'employment': row[7],
                'company_name': row[8],
                'salary': row[9]
            } for row in reversed(rows)
        ]

# Функция для фильтрации вакансий
async def get_filtered_vacancies(table_name, employment, experience, schedule, limit):
    async with aiosqlite.connect(DB_PATH_VACANCIES) as db:
        # Формируем условия фильтрации для SQL запроса
        conditions = []
        if employment in employment_values and employment != "Пропустить":
            conditions.append(f"employment = '{employment}'")
        if experience in experience_values and experience != "Пропустить":
            conditions.append(f"experience = '{experience}'")
        if schedule in schedule_values and schedule != "Пропустить":
            conditions.append(f"schedule = '{schedule}'")

        # Собираем условия в один SQL запрос
        conditions_sql = ' AND '.join(conditions) if conditions else '1'

        # Выполняем запрос с учетом фильтров
        cursor = await db.execute(f'''
            SELECT * FROM "{table_name}"
            WHERE {conditions_sql}
            ORDER BY ROWID DESC
            LIMIT ?
        ''', (limit,))
        rows = await cursor.fetchall()

        # Возвращаем вакансии в обратном порядке, чтобы они шли от самой новой к старой
        return [
            {
                'title': row[1],
                'url': row[2],
                'requirement': row[3],
                'responsibility': row[4],
                'schedule': row[5],
                'experience': row[6],
                'employment': row[7],
                'company_name': row[8],
                'salary': row[9]
            } for row in reversed(rows)
        ]


###Обработчики

@dp.message_handler(commands=['clear_all_tables'], state='*')
async def clear_all_tables(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id == ADMIN_USER_ID:
        # Получаем список всех таблиц с вакансиями
        table_names = await get_user_table_names(user_id)
        async with aiosqlite.connect(DB_PATH_VACANCIES) as db:
            for table_name in table_names:
                await db.execute(f'DROP TABLE IF EXISTS "{table_name}"')
            await db.commit()
        await message.reply("Все таблицы с вакансиями были успешно удалены.")
    else:
        await message.reply("У вас нет прав для выполнения этой команды.")

# Обработчик команды старта
@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    async with aiosqlite.connect(DB_PATH_USERS) as db:
        await db.execute('INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)', (user_id, username))
        await db.commit()
    await message.reply("Привет! Я бот-парсер вакансий с сайта hh.ru. Я могу найти вакансии используя ключевое слово для поиска. Также я могу показать вам последние найденные вакансии")

# Обработчик для случая, когда длина ключевого слова не соответствует требованиям
@dp.message_handler(lambda message: not message.text.startswith('/'), lambda message: not is_valid_length(message.text), state=Form.keyword)
async def keyword_invalid(message: types.Message):
    await message.reply("Длина ключевого слова должна быть от 3 до 20 символов. Пожалуйста, попробуйте другое ключевое слово.")

# Обработчик команды /help
@dp.message_handler(commands=['help'])
async def help_command(message: types.Message):
    help_text = (
        "Я бот для поиска вакансий. Вот список доступных команд:\n"
        "/start - начать работу с ботом\n"
        "/search - поиск вакансий по ключевому слову\n"
        "/show - показать сохраненные вакансии\n"
        "/search_with_filters - поиск вакансий с фильтрами\n"
        "/exit - сбросить все настройки и начать заново\n"
        "\n"
        "Вы можете начать поиск вакансий, используя команду /search и следуя инструкциям.\n"
        "\n"
        "Для просмотра вакансий используйте команду /show.\n"
        "\n"
        "Если хотите использовать фильтры, выберите команду /search_with_filters."
    )
    await message.reply(help_text)

# Обработчик команды /search
@dp.message_handler(commands=['search'])
async def search_command(message: types.Message):
    await Form.keyword.set()
    await message.reply("Введите ключевое слово для поиска вакансий.")

# Обработчик для сохранения ключевого слова и начала поиска вакансий
@dp.message_handler(lambda message: not message.text.startswith('/'), lambda message: is_valid_length(message.text), state=Form.keyword)
async def set_keyword(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['keyword'] = message.text
    user_id = message.from_user.id
    # Добавляем объект message в вызов функции
    await get_vacancies(data['keyword'], message, user_id)
    await state.finish()

# Обработчик команды /show
@dp.message_handler(commands=['show'], state='*')
async def show_command(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    # Получаем список таблиц для пользователя
    table_names = await get_user_table_names(user_id)
    if not table_names:
        await message.reply("У вас нет сохранённых вакансий.")
        return
    # Создаем InlineKeyboardMarkup для выбора таблицы
    markup = InlineKeyboardMarkup(row_width=2)
    for name in table_names:
        table_keyword = name.split('_')[2]
        markup.add(InlineKeyboardButton(table_keyword, callback_data=f'table_{table_keyword}'))
    await message.reply("Выберите таблицу для отображения вакансий:", reply_markup=markup)
    await Form.table_choice.set()

# Обработчик для выбора таблицы пользователем через InlineKeyboardButton
@dp.callback_query_handler(lambda c: c.data.startswith('table_'), state=Form.table_choice)
async def process_table_choice(callback_query: types.CallbackQuery, state: FSMContext):
    table_keyword = callback_query.data.split('_')[1]
    user_id = callback_query.from_user.id
    table_name = f"vacancies_{user_id}_{table_keyword}"
    async with state.proxy() as data:
        data['table_choice'] = table_name
    await Form.vacancies_count.set()
    await bot.send_message(callback_query.from_user.id, "Сколько вакансий вы хотите увидеть?")

# Обработчик для выбора таблицы пользователем
@dp.message_handler(lambda message: not message.text.startswith('/'), state=Form.table_choice)
async def set_table_choice(message: types.Message, state: FSMContext):
    table_keyword = message.text
    user_id = message.from_user.id
    table_name = f"vacancies_{user_id}_{table_keyword}"
    # Сохраняем выбор таблицы в состояние
    async with state.proxy() as data:
        data['table_choice'] = table_name
    await Form.vacancies_count.set()
    await message.reply("Сколько вакансий вы хотите увидеть?")

# Обработчик для сохранения количества вакансий и их отображения или выгрузки в Excel
@dp.message_handler(lambda message: not message.text.startswith('/'), state=Form.vacancies_count)
async def set_vacancies_count(message: types.Message, state: FSMContext):
    vacancies_count = message.text
    if not vacancies_count.isdigit():
        await message.reply("Пожалуйста, введите числовое значение для количества вакансий.")
        return
    vacancies_count = int(vacancies_count)
    async with state.proxy() as data:
        table_name = data['table_choice']
    if vacancies_count > 10:
        # Выгружаем все вакансии из таблицы в файл Excel
        await export_vacancies_to_excel(table_name, message)
    else:
        # Отображаем заданное количество вакансий
        vacancies = await get_vacancies_from_db(table_name, vacancies_count)
        if vacancies:
            vacancie_number = 0
            for vacancy in vacancies:
                vacancie_number += 1
                await message.answer(
                    f"Вакансия № {vacancie_number}\n"
                    f"Название: {vacancy['title']}\n"
                    f"Компания: {vacancy['company_name']}\n"
                    f"Зарплата: {vacancy['salary']}\n"
                    f"Требования: {vacancy['requirement']}\n"
                    f"Обязанности: {vacancy['responsibility']}\n"
                    f"График: {vacancy['schedule']}\n"
                    f"Опыт работы: {vacancy['experience']}\n"
                    f"Тип занятости: {vacancy['employment']}\n"
                    f"Ссылка: {vacancy['url']}\n"
                )
        else:
            await message.reply("Вакансии не найдены.")
    await state.finish()

# Обработчик команды /exit
@dp.message_handler(commands=['exit'], state='*')
async def exit_command(message: types.Message, state: FSMContext):
    # Сброс состояния пользователя
    await state.finish()
    await message.reply("Бот сброшен в начальное состояние. Используйте команду /start, чтобы начать заново.")

# Обработчик команды /search_with_filters
@dp.message_handler(commands=['show_with_filters'])
async def search_with_filters_command(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    # Получаем список таблиц для пользователя
    table_names = await get_user_table_names(user_id)
    if not table_names:
        await message.reply("У вас нет сохранённых вакансий.")
        return
    # Создаем InlineKeyboardMarkup для выбора таблицы
    markup = InlineKeyboardMarkup(row_width=2)
    for name in table_names:
        table_keyword = name.split('_')[2]
        markup.add(InlineKeyboardButton(table_keyword, callback_data=f'table_{table_keyword}'))
    await message.reply("Выберите таблицу для фильтрации вакансий:", reply_markup=markup)
    await Form.filter_table_choice.set()

# Обработчик для выбора таблицы пользователем
@dp.callback_query_handler(lambda c: c.data.startswith('table_'), state=Form.filter_table_choice)
async def process_table_choice(callback_query: types.CallbackQuery, state: FSMContext):
    table_keyword = callback_query.data.split('_')[1]
    user_id = callback_query.from_user.id
    table_name = f"vacancies_{user_id}_{table_keyword}"
    async with state.proxy() as data:
        data['table_choice'] = table_name
    # Переходим к выбору фильтров сразу после выбора таблицы
    await FilterForm.employment.set()
    markup = InlineKeyboardMarkup(row_width=2)
    for employment in employment_values:
        markup.add(InlineKeyboardButton(employment, callback_data=f'employment_{employment}'))
    await bot.send_message(callback_query.from_user.id, "Выберите тип занятости:", reply_markup=markup)

# Обработчик для выбора типа занятости
@dp.callback_query_handler(lambda c: c.data.startswith('employment_'), state=FilterForm.employment)
async def process_employment(callback_query: types.CallbackQuery, state: FSMContext):
    employment = callback_query.data.split('_')[1]
    async with state.proxy() as data:
        data['employment'] = employment
    # Переходим к выбору опыта работы
    markup = InlineKeyboardMarkup(row_width=2)
    for experience in experience_values:
        markup.add(InlineKeyboardButton(experience, callback_data=f'experience_{experience}'))
    await bot.send_message(callback_query.from_user.id, "Выберите опыт работы:", reply_markup=markup)
    await FilterForm.experience.set()

# Обработчик для выбора опыта работы
@dp.callback_query_handler(lambda c: c.data.startswith('experience_'), state=FilterForm.experience)
async def process_experience(callback_query: types.CallbackQuery, state: FSMContext):
    experience = callback_query.data.split('_')[1]
    async with state.proxy() as data:
        data['experience'] = experience
    # Переходим к выбору графика работы
    markup = InlineKeyboardMarkup(row_width=2)
    for schedule in schedule_values:
        markup.add(InlineKeyboardButton(schedule, callback_data=f'schedule_{schedule}'))
    await bot.send_message(callback_query.from_user.id, "Выберите график работы:", reply_markup=markup)
    await FilterForm.schedule.set()

# Обработчик для выбора графика работы
@dp.callback_query_handler(lambda c: c.data.startswith('schedule_'), state=FilterForm.schedule)
async def process_schedule(callback_query: types.CallbackQuery, state: FSMContext):
    schedule = callback_query.data.split('_')[1]
    async with state.proxy() as data:
        data['schedule'] = schedule
        # Получаем выбранные фильтры
        employment = data.get('employment')
        experience = data.get('experience')
        # Получаем вакансии с учетом фильтров
        filtered_vacancies = await get_filtered_vacancies(data['table_choice'], employment, experience, schedule, 10)
        # Отправляем вакансии пользователю
        if filtered_vacancies:
            vacancie_number = 0
            for vacancy in filtered_vacancies:
                vacancie_number += 1
                await bot.send_message(
                    callback_query.from_user.id,
                    f"Вакансия № {vacancie_number}\n" 
                    f"Название: {vacancy['title']}\n"
                    f"Компания: {vacancy['company_name']}\n"
                    f"Зарплата: {vacancy['salary']}\n"
                    f"График: {vacancy['schedule']}\n"
                    f"Требования: {vacancy['requirement']}\n"
                    f"Обязанности: {vacancy['responsibility']}\n"
                    f"Ссылка: {vacancy['url']}\n"
                )
        else:
            await bot.send_message(callback_query.from_user.id, "Вакансии, соответствующие фильтрам, не найдены.")
    await state.finish()

# Запуск бота
if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)