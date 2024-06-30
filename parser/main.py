import aiosqlite
from fake_useragent import UserAgent
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
import aiohttp

# Пути к базам данных
DB_PATH_VACANCIES = 'vacancies.db'
DB_PATH_USERS = 'users.db'

storage = MemoryStorage()

# Токен API для бота
API_TOKEN = '7418121276:AAGhBCSglrlN5kz53vZqbk_G9Km_Q3GHVSc'
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=storage)
dp.middleware.setup(LoggingMiddleware())

# Определение состояний
class Form(StatesGroup):
    keyword = State()  # Ключевое слово для поиска
    page = State()     # Номер страницы для поиска

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
async def init_db():
    async with aiosqlite.connect(DB_PATH_VACANCIES) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS vacancies (
                id TEXT PRIMARY KEY,
                title TEXT,
                url TEXT,
                requirement TEXT,
                responsibility TEXT,
                company_name TEXT,
                salary TEXT
            )
        ''')
        await db.commit()

# Очистка таблицы вакансий
async def clear_vacancies():
    async with aiosqlite.connect(DB_PATH_VACANCIES) as db:
        await db.execute('DELETE FROM vacancies')
        await db.commit()

# Асинхронная функция для получения вакансий и сохранения их в базу данных
async def get_vacancies(text, message: types.Message, page):
    await clear_vacancies()  # Очищаем таблицу перед добавлением новых данных
    await init_db()  # Инициализируем базу данных и таблицу
    url = "https://api.hh.ru/vacancies"
    user_agent = UserAgent().random

    params = {
        "text": text,
        "area": 1,
        "page": page,
        "per_page": 100,
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
                found_count = json_data['found']
                await message.reply(f"Найдено вакансий: {found_count}")

                async with aiosqlite.connect(DB_PATH_VACANCIES) as db:
                    for vacancy in vacancies:
                        id = vacancy.get("id")
                        title = vacancy.get("name")
                        url = vacancy.get("alternate_url")
                        requirement = vacancy.get("snippet", {}).get("requirement", "Не указано")
                        responsibility = vacancy.get("snippet", {}).get("responsibility", "Не указано")
                        company_name = vacancy.get("employer", {}).get("name", "Не указано")
                        salary_info = vacancy.get("salary")
                        salary = 'Не указано'
                        if salary_info:
                            salary = f"{salary_info.get('from', '—')} — {salary_info.get('to', '—')} {salary_info.get('currency', '—')}"

                        if not all([id, title, url, requirement, responsibility, company_name]):
                            print(f"Пропускаем вакансию {id} из-за отсутствия данных")
                            continue

                        try:
                            await db.execute('''
                                INSERT INTO vacancies (id, title, url, requirement, responsibility, company_name, salary)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            ''', (id, title, url, requirement, responsibility, company_name, salary))
                            print(f"Вакансия {id} добавлена в базу данных")
                        except Exception as e:
                            print(f"Ошибка при добавлении вакансии {id}: {e}")
                    await db.commit()
            else:
                await message.reply(f"Ошибка запроса к API: HTTP статус {response.status}")

# Клавиатура для бота
keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
button_search = KeyboardButton('Найти вакансии')
keyboard.add(button_search)

# Обработчик команды старта
@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    # Регистрация пользователя в базе данных
    user_id = message.from_user.id
    username = message.from_user.username
    async with aiosqlite.connect(DB_PATH_USERS) as db:
        await db.execute('INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)', (user_id, username))
        await db.commit()
    # Приветственное сообщение пользователю
    await message.reply("Привет! Я могу помочь тебе найти вакансии. Нажми на кнопку ниже или введи ключевое слово.", reply_markup=keyboard)

# Обработчик для начала диалога поиска вакансий
@dp.message_handler(lambda message: message.text and 'Найти вакансии' in message.text, state='*')
async def ask_for_keyword(message: types.Message, state: FSMContext):
    await Form.keyword.set()
    await message.reply("Введите ключевое слово для поиска вакансий.")

# Обработчик для сохранения ключевого слова и запроса номера страницы
@dp.message_handler(state=Form.keyword)
async def set_keyword(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['keyword'] = message.text
    # Вызов функции для получения общего количества вакансий
    await get_total_vacancies_count(data['keyword'], message)

# Новая асинхронная функция для получения общего количества вакансий
async def get_total_vacancies_count(text, message: types.Message):
    url = "https://api.hh.ru/vacancies"
    user_agent = UserAgent().random
    params = {
        "text": text,
        "area": 1,
        "per_page": 1,  # Запрашиваем только одну вакансию для получения общего количества
        "only_with_salary": 1
    }
    headers = {
        "User-Agent": user_agent
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, headers=headers) as response:
            if response.status == 200:
                json_data = await response.json()
                found_count = json_data['found']
                max_pages = (found_count - 1) // 100 + 1  # Рассчитываем количество страниц
                await message.reply(f"Найдено вакансий: {found_count}. Можете выбрать страницу от 1 до {max_pages}.")
                await Form.page.set()  # Переходим к следующему состоянию для запроса номера страницы
            else:
                await message.reply(f"Ошибка запроса к API: HTTP статус {response.status}")

# Обработчик для сохранения номера страницы и запуска поиска вакансий
@dp.message_handler(state=Form.page)
async def set_page(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['page'] = message.text
    await state.finish()
    # Вызов функции для получения вакансий
    await get_vacancies(data['keyword'], message, int(data['page']))

# Запуск бота
if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
