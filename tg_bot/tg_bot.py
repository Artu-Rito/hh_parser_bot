from aiogram import Bot, Dispatcher, executor, types
import psycopg2
import asyncio
import config  # Импорт данных из файла config

# Функция для подключения к базе данных
def connect_db():
    return psycopg2.connect(
        dbname=config.DB_NAME,
        user=config.DB_USER,
        password=config.DB_PASS,
        host=config.DB_HOST
    )

# Функция парсинга данных (заглушка, реализуйте свою логику)
def parse_data(word):
    # Здесь должна быть ваша логика парсинга
    parsed_data = word  # Пример результата
    return parsed_data

# Функция для сохранения данных в базу данных
async def save_to_db(word):
    parsed_data = parse_data(word)
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO words (word, parsed_data) VALUES (%s, %s)", (word, parsed_data))
    conn.commit()
    cursor.close()
    conn.close()

# Инициализация бота и диспетчера
bot = Bot(token=config.TOKEN)
dp = Dispatcher(bot)

# Обработчик команды start
@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    await message.reply("Привет! Отправь мне слово, и я сохраню его в базу данных.")

# Обработчик для текстовых сообщений
@dp.message_handler(content_types=['text'])
async def handle_text(message: types.Message):
    word = message.text
    await save_to_db(word)
    await message.reply("Слово сохранено в базу данных.")

# Запуск бота
if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
