# Используйте официальный образ Python как базовый
FROM python:3.8

# Установите рабочую директорию в контейнере
WORKDIR /usr/src/app

# Копируйте файлы зависимостей в контейнер
COPY requirements.txt ./

# Установите зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируйте исходный код бота и базы данных в контейнер
COPY . .

# Укажите команду для запуска приложения
CMD [ "python", "./main.py" ]
