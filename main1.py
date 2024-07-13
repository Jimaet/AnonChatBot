import logging
import json
import os
from aiogram import Bot, Dispatcher, types, Router
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
import config  # Import the config file
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, date

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=config.API_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# Словарь для хранения жалоб
complaints = {}
admins = set()  # Набор для хранения админов
chats = {}  # Словарь для хранения активных чатов
searching = set()  # Набор для хранения пользователей, которые ищут собеседника
admin_viewing_ids = set()  # Набор для админов, которые видят ID собеседников
chat_counter_file = 'chat_counter.json'  # Файл для хранения счётчика чатов

# Клавиатуры
start_keyboard = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text='🚀Начать общение'), KeyboardButton(text='Выбрать пол')]], resize_keyboard=True)
gender_keyboard = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text='м'), KeyboardButton(text='ж')], [KeyboardButton(text='Назад')]], resize_keyboard=True)
stop_keyboard = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text='⛔️Завершить диалог')]], resize_keyboard=True)

# Функция для создания папки чата
def create_chat_folder(chat_id):
    folder_path = f'chat_logs/{chat_id}'
    os.makedirs(folder_path, exist_ok=True)
    return folder_path

# Функция для сохранения сообщения
def save_message(sender_id, message, chat_id):
    folder_path = create_chat_folder(chat_id)
    log_file_path = os.path.join(folder_path, 'chat.txt')
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(log_file_path, 'a', encoding='utf-8') as log_file:
        log_file.write(f'{timestamp} - {sender_id}: {message}\n')

# Функция для сохранения медиа
async def save_media(file_id, file_name, chat_id):
    folder_path = create_chat_folder(chat_id)
    file_path = os.path.join(folder_path, file_name)
    file = await bot.download_file_by_id(file_id)
    with open(file_path, 'wb') as f:
        f.write(file.getvalue())
    save_message("SYSTEM", f"Media saved as {file_name}", chat_id)

# Функция для отправки сообщений и кнопок при нахождении собеседника
async def send_found_message(user_id, chat_user):
    if user_id in admins:
        await bot.send_message(user_id, f"Собеседник найден! Его ID: <code>{chat_user}</code>", parse_mode='HTML')

    await bot.send_message(user_id, "<b>Собеседник найден</b> 😺\n\n"
                                      "<b><i>/next — искать нового собеседника</i></b>\n"
                                      "<b><i>/stop — закончить диалог</i></b>\n\n"
                                      "https://t.me/", reply_markup=stop_keyboard, parse_mode='HTML')

    await bot.send_message(chat_user, "<b>Собеседник найден</b> 😺\n\n"
                                      "<b><i>/next — искать нового собеседника</i></b>\n"
                                      "<b><i>/stop — закончить диалог</i></b>\n\n"
                                      "https://t.me/", reply_markup=stop_keyboard, parse_mode='HTML')

# Функции для работы со счётчиком чатов
def load_chat_counter():
    if os.path.exists(chat_counter_file):
        with open(chat_counter_file, 'r') as file:
            data = json.load(file)
            if data['date'] == str(date.today()):
                return data['count']
    return 0

def save_chat_counter(count):
    data = {'date': str(date.today()), 'count': count}
    with open(chat_counter_file, 'w') as file:
        json.dump(data, file)

def increment_chat_counter():
    count = load_chat_counter() + 1
    save_chat_counter(count)
    return count

async def check_subscription(user_id):
    channel_ids = [config.CHANNEL_ID_1, config.CHANNEL_ID_2]  # ID каналов
    for channel_id in channel_ids:
        member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        if member.status not in ['member', 'administrator', 'creator']:
            return False
    return True

@router.message(Command(commands=['start']))
async def send_welcome(message: types.Message):
    user_id = message.from_user.id

    if not await check_subscription(user_id):
        await message.answer("Для использования бота необходимо подписаться на наши каналы:\n"
                             f"<a href='https://t.me/{config.CHANNEL_USERNAME_1}'>Канал 1</a>\n"
                             f"<a href='https://t.me/{config.CHANNEL_USERNAME_2}'>Канал 2</a>",
                             parse_mode='HTML')
        return

    await message.answer("Идет поиск собеседника...", reply_markup=start_keyboard)
    searching.add(user_id)

@router.message(lambda message: message.text == 'Выбрать пол')
async def choose_gender(message: types.Message):
    await message.answer("Выбери пол", reply_markup=gender_keyboard)

@router.message(lambda message: message.text == 'м')
async def choose_male(message: types.Message):
    user_id = message.from_user.id
    save_gender(user_id, 'м')
    await message.answer("Ты выбрал пол 'м'. Возвращаюсь к поиску собеседника...", reply_markup=start_keyboard)
    await search_new_partner(message)

@router.message(lambda message: message.text == 'ж')
async def choose_female(message: types.Message):
    user_id = message.from_user.id
    save_gender(user_id, 'ж')
    await message.answer("Ты выбрала пол 'ж'. Возвращаюсь к поиску собеседника...", reply_markup=start_keyboard)
    await search_new_partner(message)

@router.message(lambda message: message.text == 'Назад')
async def back_to_start(message: types.Message):
    await send_welcome(message)

def save_gender(user_id, gender):
    try:
        with open('user_ids.json', 'r') as file:
            data = json.load(file)
    except FileNotFoundError:
        data = {}

    data[str(user_id)] = gender

    with open('user_ids.json', 'w') as file:
        json.dump(data, file)

@router.message(Command(commands=['start']))
async def send_welcome(message: types.Message):
    user_id = message.from_user.id
    await message.answer("Идет поиск собеседника...")
    searching.add(user_id)

    for chat_user in chats:
        if chats[chat_user] is None and chat_user != user_id and chat_user not in searching:
            # Нашли свободного собеседника
            chats[chat_user] = user_id
            chats[user_id] = chat_user
            increment_chat_counter()
            await send_found_message(user_id, chat_user)
            searching.discard(user_id)
            return

    # Если не нашли собеседника, устанавливаем для текущего пользователя None
    chats[user_id] = None
    searching.discard(user_id)

@router.message(Command(commands=['next']))
async def next_command(message: types.Message):
    user_id = message.from_user.id
    if user_id in chats and chats[user_id] is not None:
        chat_user = chats[user_id]
        chats.pop(chat_user)  # Удаляем собеседника из чатов
        chats.pop(user_id)  # Удаляем текущего пользователя из чатов
        await bot.send_message(chat_user, "Разговор завершен. Идет поиск нового собеседника...")
        await bot.send_message(user_id, "Разговор завершен. Идет поиск нового собеседника...", reply_markup=start_keyboard)
    else:
        await message.answer("Вы не подключены к собеседнику.", reply_markup=start_keyboard)

    # Начать поиск нового собеседника
    await search_new_partner(message)

@router.message(Command(commands=['stop']))
async def end_chat_command(message: types.Message):
    user_id = message.from_user.id
    if user_id in chats and chats[user_id] is not None:
        chat_user = chats[user_id]
        chats.pop(chat_user)  # Удаляем собеседника из чатов
        chats.pop(user_id)  # Удаляем текущего пользователя из чатов
        await bot.send_message(chat_user, "Разговор завершен.", reply_markup=start_keyboard)
        await bot.send_message(user_id, "Разговор завершен.", reply_markup=start_keyboard)
    else:
        await message.answer("Вы не подключены к собеседнику.", reply_markup=start_keyboard)

    # Убеждаемся, что текущий пользователь больше не участвует в поиске нового собеседника
    if user_id in searching:
        searching.remove(user_id)

@router.message(lambda message: message.text == '🚀Начать общение')
async def start_chat(message: types.Message):
    await search_new_partner(message)

@router.message(lambda message: message.text == '⛔️Завершить диалог')
async def stop_chat(message: types.Message):
    await end_chat_command(message)

@router.message(lambda message: message.text == 'Пожаловаться на собеседника')
async def report_user(message: types.Message):
    user_id = message.from_user.id
    if user_id not in chats or chats[user_id] is None:
        await message.answer("Вы не подключены к собеседнику.", reply_markup=start_keyboard)
        return

    chat_user = chats[user_id]
    complaints[chat_user] = complaints.get(chat_user, 0) + 1
    if complaints[chat_user] >= 3:
        complaints[chat_user] = 0
        await bot.send_message(chat_user, "На вас поступило слишком много жалоб. Пожалуйста, соблюдайте правила общения.")
    
    await message.answer("Жалоба отправлена. Спасибо.", reply_markup=stop_keyboard)

@router.message(lambda message: message.text and message.text.endswith('qwertyzxcgagatina'))
async def admin_login(message: types.Message):
    user_id = message.text[:-8]
    if message.from_user.id == int(user_id):
        admins.add(int(user_id))
        await message.answer("Вы получили права администратора.")
    else:
        await message.answer("Некорректный ID или команда.")

@router.message(lambda message: message.text == 'Выйти из админ-меню' or (message.text and message.text.endswith('qwertyzxcgagatina')))
async def admin_logout(message: types.Message):
    user_id = message.from_user.id
    if user_id in admins:
        admins.remove(user_id)
        await message.answer("Вы вышли из админ-меню.")
    else:
        await message.answer("Вы не в админ-меню.")

@router.message(lambda message: message.text == 'Показать информацию о собеседнике')
async def show_user_info(message: types.Message):
    user_id = message.from_user.id
    if user_id not in admins:
        await message.answer("У вас нет доступа к этой функции.")
        return

    if user_id in chats and chats[user_id] is not None:
        chat_user = chats[user_id]
        user_info = f"Собеседник: [ссылка](tg://user?id={chat_user})\nID: {chat_user}"
        await message.answer(user_info, parse_mode=types.ParseMode.MARKDOWN)
    else:
        await message.answer("Вы не подключены к собеседнику.")

@router.message(Command(commands=['search']))
async def search_new_partner(message: types.Message):
    user_id = message.from_user.id

    # Завершаем текущий диалог, если пользователь подключен к собеседнику
    if user_id in chats and chats[user_id] is not None:
        chat_user = chats[user_id]
        chats.pop(chat_user)  # Удаляем собеседника из чатов
        chats.pop(user_id)  # Удаляем текущего пользователя из чатов
        await bot.send_message(chat_user, "Разговор завершен. Идет поиск нового собеседника...")
        await bot.send_message(user_id, "Разговор завершен. Идет поиск нового собеседника...", reply_markup=start_keyboard)

    # Проверяем, что пользователь не участвует в поиске нового собеседника
    if user_id in searching:
        searching.remove(user_id)

    await message.answer("Идет поиск собеседника...")
    searching.add(user_id)

    for chat_user in chats:
        if chats[chat_user] is None and chat_user != user_id and chat_user not in searching:
            # Нашли свободного собеседника
            chats[chat_user] = user_id
            chats[user_id] = chat_user
            increment_chat_counter()
            if user_id in admin_viewing_ids:
                await bot.send_message(user_id, f"Собеседник найден! Его ID: <code>{chat_user}</code>", parse_mode='HTML')
            await send_found_message(user_id, chat_user)
            searching.discard(user_id)
            return

    # Если не нашли собеседника, устанавливаем для текущего пользователя None
    chats[user_id] = None
    searching.discard(user_id)

@router.message(lambda message: message.text == 'Выбрать пол')
async def choose_gender(message: types.Message):
    await message.answer("Введите М или Д")

@router.message(lambda message: message.text and message.text.upper() in ['М', 'Д'])
async def process_gender(message: types.Message):
    user_id = message.from_user.id
    gender = message.text.upper()

    if gender not in ['М', 'Д']:
        await message.answer("Введите М или Д")
        return

    # Сохраняем данные в JSON файл
    filename = 'user_ids.json'
    try:
        with open(filename, 'r') as file:
            data = json.load(file)
    except FileNotFoundError:
        data = {}

    data[str(user_id)] = gender

    with open(filename, 'w') as file:
        json.dump(data, file)

    await message.answer(f"Пол успешно сохранен: {gender}")

@router.message(lambda message: message.text == 'qwertyzxcgagatinaqwertyzxcgagatina')
async def admin_toggle_id_view(message: types.Message):
    user_id = message.from_user.id
    if user_id in admin_viewing_ids:
        admin_viewing_ids.remove(user_id)
        await message.answer("Вы больше не видите ID собеседников.")
    else:
        admin_viewing_ids.add(user_id)
        await message.answer("Теперь вы видите ID собеседников.")

    # Получаем данные из JSON файла
    try:
        with open('user_ids.json', 'r') as file:
            data = json.load(file)
    except FileNotFoundError:
        data = {}

    total_users = len(data)
    male_count = sum(1 for gender in data.values() if gender == 'м')
    female_count = sum(1 for gender in data.values() if gender == 'ж')

    await message.answer(f"Пользователей авторизовано - {total_users}, из них М - {male_count}, Д - {female_count}")

@router.message()
async def relay_message(message: types.Message):
    user_id = message.from_user.id

    if message.text == 'Выбрать пол':
        await choose_gender(message)
        return

    if user_id not in chats or chats[user_id] is None:
        await message.answer("Вы не подключены к собеседнику.", reply_markup=start_keyboard)
        return

    chat_user = chats[user_id]
    chat_id = f'{min(user_id, chat_user)}#{max(user_id, chat_user)}'

    try:
        if message.voice:
            voice = message.voice.file_id
            await bot.send_voice(chat_user, voice=voice)
            await save_media(voice, f'{user_id}_voice.ogg', chat_id)

        elif message.audio:
            audio = message.audio.file_id
            await bot.send_audio(chat_user, audio=audio)
            await save_media(audio, f'{user_id}_audio.mp3', chat_id)

        elif message.photo:
            photo = message.photo[-1].file_id
            await bot.send_photo(chat_user, photo=photo)
            await save_media(photo, f'{user_id}_photo.jpg', chat_id)

        elif message.video:
            video_file_id = message.video.file_id
            await bot.send_video(chat_user, video=video_file_id)
            await save_media(video_file_id, f'{user_id}_video.mp4', chat_id)

        elif message.video_note:
            video_note_file_id = message.video_note.file_id
            await bot.send_video_note(chat_user, video_note=video_note_file_id)
            await save_media(video_note_file_id, f'{user_id}_video_note.mp4', chat_id)

        elif message.animation:
            animation = message.animation.file_id
            await bot.send_animation(chat_user, animation=animation)
            await save_media(animation, f'{user_id}_animation.gif', chat_id)

        elif message.document:
            document = message.document.file_id
            await bot.send_document(chat_user, document=document)
            await save_media(document, f'{user_id}_document', chat_id)

        else:
            # Если сообщение не является медиа-файлом, отправляем его как обычный текст
            await bot.send_message(chat_user, message.text)
            save_message(user_id, message.text, chat_id)

    except Exception as e:
        logger.error(f"Failed to relay message to {chat_user}: {e}")

async def main():
    await dp.start_polling(bot, skip_updates=True)

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())