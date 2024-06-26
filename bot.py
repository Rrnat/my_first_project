import os.path
import telebot
from telebot import types

from creds import get_bot_token  # модуль для получения bot_token
from validators import *  # модуль для валидации
from yandex_gpt import *  # модуль для работы с GPT
from config import *
from database import *
from SpeechKit import *

bot = telebot.TeleBot(get_bot_token())  # создаём объект бота
# bot = telebot.TeleBot(TOKEN)

logging.basicConfig(
    filename=LOGS,
    level=logging.DEBUG,
    format="%(asctime)s %(message)s", filemode="w"
)


def menu_keyboard(options):
    """Создаёт клавиатуру с указанными кнопками."""
    buttons = (types.KeyboardButton(text=option) for option in options)
    keyboard = types.ReplyKeyboardMarkup(
        row_width=2,
        resize_keyboard=True,
        one_time_keyboard=True
    )
    keyboard.add(*buttons)
    return keyboard


@bot.message_handler(commands=['debug'])
def send_logs(message):
    # Если текущий пользователь имеет id = ADMIN_ID:
    # с помощью os.path.exists проверяем что файл с логами существует
    # если все ОК - отправляем пользователю файл с логами LOGS
    # если НЕ ОК - пишем пользователю сообщение что файл не найден
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "Вы не являетесь администратором этого бота.")
        return

    if os.path.exists(LOGS):
        with open(LOGS, 'rb') as lg:
            bot.send_document(message.chat.id, lg)
    else:
        bot.send_message(message.chat.id, "Файл не найден.")


@bot.message_handler(commands=['help'])
def help(message):
    bot.send_message(message.from_user.id, "Чтобы приступить к общению, отправь мне голосовое сообщение или текст\n"
                                           "Так же ты можешь сделать проверку:\n"
                                           "/stt - проверка синтеза речи\n"
                                           "/tts - проверка распознавания речи",
                     reply_markup=menu_keyboard(["/stt", "/tts"]))


@bot.message_handler(commands=['start'])
def start(message):
    user_name = message.from_user.first_name
    bot.send_message(message.chat.id, f"Привет, {user_name}! Я твой личный психолог,"
                                      f" который поможет тебе решить твои вопросы.\n"
                                      "Напиши или запиши мне голосовое сообщение, чтобы начать.\n"
                                      "Либо нажми --> /help <-- чтобы узнать дополнительную информацию")


@bot.message_handler(commands=['tts'])
def tts_handler(message):
    user_id = message.from_user.id
    bot.send_message(user_id, 'Отправь следующим сообщеним текст, чтобы я его озвучил!')
    bot.register_next_step_handler(message, tts)


def tts(message):
    user_id = message.from_user.id
    text = message.text

    # Проверка, что сообщение действительно текстовое
    if message.content_type != 'text':
        bot.send_message(user_id, 'Отправь текстовое сообщение')
        logging.info(f"TELEGRAM BOT: Input: {message.text}\nOutput: Error: пользователь отправил не текстовое сообщение")
        return

        # ВАЛИДАЦИЯ: проверяем, есть ли место для ещё одного пользователя (если пользователь новый)
        status_check_users, error_message = check_number_of_users(user_id)
        if not status_check_users:
            bot.send_message(user_id, error_message)  # мест нет =(
            return

        # БД: добавляем сообщение пользователя и его роль в базу данных
        full_user_message = [message.text, 'user', 0, 0, 0]
        add_message(user_id=user_id, full_message=full_user_message)

        # ВАЛИДАЦИЯ: считаем количество доступных пользователю GPT-токенов
        # получаем последние 4 (COUNT_LAST_MSG) сообщения и количество уже потраченных токенов
        last_messages, total_spent_tokens = select_n_last_messages(user_id, COUNT_LAST_MSG)
        # получаем сумму уже потраченных токенов + токенов в новом сообщении и оставшиеся лимиты пользователя
        total_gpt_tokens, error_message = is_gpt_token_limit(last_messages, total_spent_tokens)
        if error_message:
            # если что-то пошло не так — уведомляем пользователя и прекращаем выполнение функции
            bot.send_message(user_id, error_message)
            return

    # Получаем статус и содержимое ответа от SpeechKit
    status, content = text_to_speech(text)

    # Если статус True - отправляем голосовое сообщение, иначе - сообщение об ошибке
    if status:
        bot.send_voice(user_id, content)
    else:
        bot.send_message(user_id, content)
        logging.info(f"TELEGRAM BOT: Input: {message.text}\nOutput: Error: При запросе в SpeechKit возникла ошибка")


def is_tts_symbol_limit(message, text):
    user_id = message.from_user.id
    text_symbols = len(text)

    # Функция из БД для подсчёта всех потраченных пользователем символов
    all_symbols = count_all_symbol(user_id) + text_symbols

    # Сравниваем all_symbols с количеством доступных пользователю символов
    if all_symbols >= MAX_USER_TTS_SYMBOLS:
        msg = (f"Превышен общий лимит SpeechKit TTS {MAX_USER_TTS_SYMBOLS}. "
               f"Использовано: {all_symbols} символов. Доступно: {MAX_USER_TTS_SYMBOLS - all_symbols}")
        bot.send_message(user_id, msg)
        return None

    # Сравниваем количество символов в тексте с максимальным количеством символов в тексте
    if text_symbols >= MAX_TTS_SYMBOLS:
        msg = f"Превышен лимит SpeechKit TTS на запрос {MAX_TTS_SYMBOLS}, в сообщении {text_symbols} символов"
        bot.send_message(user_id, msg)
        logging.info(f"TELEGRAM BOT: Input: {message.text}\nOutput: Error: Превышен лимит SpeechKit TTS на запрос")
        return None
    return len(text)


@bot.message_handler(commands=['stt'])
def stt_handler(message):
    user_id = message.from_user.id
    bot.send_message(user_id, 'Отправь голосовое сообщение, чтобы я его распознал!')
    bot.register_next_step_handler(message, stt)


# Переводим голосовое сообщение в текст после команды stt
def stt(message):
    user_id = message.from_user.id

    # Проверка, что сообщение действительно голосовое
    if not message.voice:
        logging.info(f"TELEGRAM BOT: Input: {message.text}\nOutput: Error: пользователь отправил не голосовое сообщение")
        return

    # Считаем аудиоблоки и проверяем сумму потраченных аудиоблоков
    stt_blocks = is_stt_block_limit(message, message.voice.duration)
    if not stt_blocks:
        return

    file_id = message.voice.file_id  # получаем id голосового сообщения
    file_info = bot.get_file(file_id)  # получаем информацию о голосовом сообщении
    file = bot.download_file(file_info.file_path)  # скачиваем голосовое сообщение

    # Получаем статус и содержимое ответа от SpeechKit
    status, text = speech_to_text(file)  # преобразовываем голосовое сообщение в текст

    # Если статус True - отправляем текст сообщения и сохраняем в БД, иначе - сообщение об ошибке
    if status:
        bot.send_message(user_id, text, reply_to_message_id=message.id)
    else:
        bot.send_message(user_id, text)
        logging.info(f"TELEGRAM BOT: Input: {message.text}\nOutput: Error: При запросе в SpeechKit возникла ошибка")

    # Запись в БД
    add_message(user_id=user_id, full_message=[text, 'user', 0, 0, stt_blocks])

    # Проверка на доступность GPT-токенов
    last_messages, total_spent_tokens = select_n_last_messages(user_id, COUNT_LAST_MSG)
    total_gpt_tokens, error_message = is_gpt_token_limit(last_messages, total_spent_tokens)
    if error_message:
        bot.send_message(user_id, error_message)
        return


@bot.message_handler(content_types=['text'])
def handle_text(message):
    try:
        user_id = message.from_user.id

        # ВАЛИДАЦИЯ: проверяем, есть ли место для ещё одного пользователя (если пользователь новый)
        status_check_users, error_message = check_number_of_users(user_id)
        if not status_check_users:
            bot.send_message(user_id, error_message)  # мест нет =(
            return

        # БД: добавляем сообщение пользователя и его роль в базу данных
        full_user_message = [message.text, 'user', 0, 0, 0]
        add_message(user_id=user_id, full_message=full_user_message)

        # ВАЛИДАЦИЯ: считаем количество доступных пользователю GPT-токенов
        # получаем последние 4 (COUNT_LAST_MSG) сообщения и количество уже потраченных токенов
        last_messages, total_spent_tokens = select_n_last_messages(user_id, COUNT_LAST_MSG)
        # получаем сумму уже потраченных токенов + токенов в новом сообщении и оставшиеся лимиты пользователя
        total_gpt_tokens, error_message = is_gpt_token_limit(last_messages, total_spent_tokens)
        if error_message:
            # если что-то пошло не так — уведомляем пользователя и прекращаем выполнение функции
            bot.send_message(user_id, error_message)
            return

        # GPT: отправляем запрос к GPT
        status_gpt, answer_gpt, tokens_in_answer = ask_gpt(last_messages)
        # GPT: обрабатываем ответ от GPT
        if not status_gpt:
            # если что-то пошло не так — уведомляем пользователя и прекращаем выполнение функции
            bot.send_message(user_id, answer_gpt)
            return
        # сумма всех потраченных токенов + токены в ответе GPT
        total_gpt_tokens += tokens_in_answer

        # БД: добавляем ответ GPT и потраченные токены в базу данных
        full_gpt_message = [answer_gpt, 'assistant', total_gpt_tokens, 0, 0]
        add_message(user_id=user_id, full_message=full_gpt_message)

        bot.send_message(user_id, answer_gpt, reply_to_message_id=message.id)  # отвечаем пользователю текстом
    except Exception as e:
        logging.error(e)  # если ошибка — записываем её в логи
        bot.send_message(message.from_user.id, "Не получилось ответить. Попробуй написать другое сообщение")


# Декоратор для обработки голосовых сообщений, полученных ботом
@bot.message_handler(content_types=['voice'])
def handle_voice(message):
    try:
        user_id = message.from_user.id  # Идентификатор пользователя, который отправил сообщение
        # Получение информации о голосовом файле и его загрузка
        file_id = message.voice.file_id  # Идентификатор голосового файла в сообщении
        file_info = bot.get_file(file_id)  # Получение информации о файле для загрузки
        file = bot.download_file(file_info.file_path)  # Загрузка файла по указанному пути

        last_messages, total_spent_tokens = select_n_last_messages(user_id, COUNT_LAST_MSG)
        total_gpt_tokens, error_message = is_gpt_token_limit(last_messages, total_spent_tokens)

        # Преобразование голосового сообщения в текст с помощью SpeechKit
        status_stt, stt_text = speech_to_text(file)  # Обращение к функции speech_to_text для получения текста
        if not status_stt:
            # Отправка сообщения об ошибке, если преобразование не удалось
            bot.send_message(user_id, stt_text)
            return

            # Отправка нескольких последних сообщений от пользователя в GPT для генерации ответа
            # В константе COUNT_LAST_MSG хранится количество сообщений пользователя, которые передаем
        last_messages, total_spent_tokens = select_n_last_messages(user_id, COUNT_LAST_MSG)
        status_gpt, answer_gpt, tokens_in_answer = ask_gpt(last_messages)
        if not status_gpt:
            bot.send_message(user_id, answer_gpt)
            return
        total_gpt_tokens += tokens_in_answer

        # Преобразование текстового ответа от GPT в голосовое сообщение
        status_tts, voice_response = text_to_speech(
            answer_gpt)  # Обращение к функ ции text_to_speech для получения аудио
        if not status_tts:
            # Отправка текстового ответа GPT, если преобразование в аудио не удалось
            bot.send_message(user_id, answer_gpt, reply_to_message_id=message.id)
        else:
            # Отправка голосового сообщения, если преобразование в аудио прошло успешно
            bot.send_voice(user_id, voice_response, reply_to_message_id=message.id)

    except Exception as e:
        # Логирование ошибки
        logging.error(e)
        # Уведомление пользователя о непредвиденной ошибке
        bot.send_message(user_id, "Не получилось ответить. Попробуй записать другое сообщение")


# обрабатываем все остальные типы сообщений
@bot.message_handler(func=lambda: True)
def handler(message):
    bot.send_message(message.from_user.id, "Отправь мне голосовое или текстовое сообщение, и я тебе отвечу")


bot.polling()