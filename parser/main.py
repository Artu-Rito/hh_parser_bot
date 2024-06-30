import json
import requests
import aiosqlite
from fake_useragent import UserAgent
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# Пути к базам данных
DB_PATH_VACANCIES = 'vacancies.db'
DB_PATH_USERS = 'users.db'

# Токен API для бота
API_TOKEN = '7418121276:AAGhBCSglrlN5kz53vZqbk_G9Km_Q3GHVSc'
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

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
                company_name TEXT
            )
        ''')
        await db.commit()

# Очистка таблицы вакансий
async def clear_vacancies():
    async with aiosqlite.connect(DB_PATH_VACANCIES) as db:
        await db.execute('DELETE FROM vacancies')
        await db.commit()

# Асинхронная функция для получения вакансий и сохранения их в базу данных
async def get_vacancies(text):
    await clear_vacancies()  # Очищаем таблицу перед добавлением новых данных
    await init_db()  # Инициализируем базу данных и таблицу
    url = "https://api.hh.ru/vacancies"
    user_agent = UserAgent().random

    params = {
        "text": text,
        "area": 1,
        "page": 0,
        "per_page": 100
    }
    headers = {
        "User-Agent": user_agent
    }

    response = requests.get(url, params=params, headers=headers)

    if response.status_code == 200:
        data = response.content.decode()
        json_data = json.loads(data)
        vacancies = json_data['items']
        print(f"Найдено вакансий: {json_data['found']}")

        async with aiosqlite.connect(DB_PATH_VACANCIES) as db:
            for vacancy in vacancies:
                id = vacancy.get("id")
                title = vacancy.get("name")
                url = vacancy.get("alternate_url")
                requirement = vacancy.get("snippet", {}).get("requirement", "Не указано")
                responsibility = vacancy.get("snippet", {}).get("responsibility", "Не указано")
                company_name = vacancy.get("employer", {}).get("name", "Не указано")

                if not all([id, title, url, requirement, responsibility, company_name]):
                    print(f"Пропускаем вакансию {id} из-за отсутствия данных")
                    continue

                await db.execute('''
                    INSERT INTO vacancies (id, title, url, requirement, responsibility, company_name)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (id, title, url, requirement, responsibility, company_name))
            await db.commit()

    else:
        print("Ошибка запроса к API: HTTP статус", response.status_code)

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

# Обработчик для поиска вакансий
@dp.message_handler(lambda message: message.text and 'Найти вакансии' in message.text)
async def ask_for_keyword(message: types.Message):
    await message.reply("Введите ключевое слово для поиска вакансий.")

# Обработчик команды для очистки базы данных вакансий
@dp.message_handler(commands=['clear'])
async def clear_database(message: types.Message):
    await clear_vacancies()  # Вызов функции для очистки таблицы вакансий
    await message.reply("База данных вакансий очищена.")

# Обработчик текстовых сообщений для сохранения ключевого слова и поиска вакансий
@dp.message_handler()
async def search_vacancies(message: types.Message):
    # Проверяем, что сообщение не является командой /clear
    if message.text.startswith('/'):
        return
    # Сохранение ключевого слова в базу данных пользователей
    user_id = message.from_user.id
    keyword = message.text
    async with aiosqlite.connect(DB_PATH_USERS) as db:
        await db.execute('UPDATE users SET search_keyword = ? WHERE user_id = ?', (keyword, user_id))
        await db.commit()
    # Вызов функции для получения вакансий
    await get_vacancies(text=keyword)

# Запуск бота
if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
