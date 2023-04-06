import sys
import os
import telegram
import logging
import time
import requests

from http import HTTPStatus
from exeptions import SendMessageError, APIRequestError

from dotenv import load_dotenv


load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    filename='main.log',
    filemode='w',
    format='%(asctime)s -  %(levelname)s - %(message)s')


def check_tokens():
    """Проверяет доступность переменных окружения.
    Если отсутствует хотя бы одна переменная окружения,
    прерывает работу прграммы.
    """
    if not all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
        logging.critical('Отсуствуют обязательные переменные.')
        sys.exit()


def send_message(bot, message):
    """Отправляет в телеграмм статус проверки домашней работы."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug('Сообщение успешно отправлено.')
    except telegram.error.TelegramError:
        logging.error('Не удалось отправить сообщение.')
        raise SendMessageError('Не удалось отправить сообщение.')


def get_api_answer(timestamp):
    """Делает запрос к эндпоинту API-сервиса."""
    payload = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
    except requests.RequestException as error:
        raise APIRequestError(f'Ошибка ответа сервера: {error}')
    if response.status_code != HTTPStatus.OK:
        raise HTTPStatus.BAD_REQUEST(
            f'Сервер вернул ошибку. Код ошибки: {response.status_code}')
    try:
        response = response.json()
        return response
    except requests.exceptions.JSONDecodeError as exc:
        logging.error(f'Произошла ошибка метода json: {str(exc)}')


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API не является словарем.')
    if 'homeworks' not in response:
        raise KeyError('В ответе сервера отсутствует ключ homeworks')
    if 'current_date' not in response:
        raise KeyError('В ответе сервера отсутствует ключ current_date')
    if not isinstance(response['homeworks'], list):
        raise TypeError('Ответ API не является списком.')


def parse_status(homework):
    """Извлекает из информации о конкретной домашней работе."""
    homework_status = homework['status']
    if 'status' not in homework:
        raise KeyError('Нет ключа homework_status')

    if 'homework_name' not in homework:
        raise TypeError('Нет ключа homework_name')
    homework_name = homework['homework_name']

    if homework_status not in HOMEWORK_VERDICTS:
        raise KeyError('Неожиданный статус домашней работы')
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            if response['homeworks']:
                homework = response['homeworks'][0]
                message = parse_status(homework)
                previous_message = ''
                if message != previous_message:
                    send_message(bot, message)
                    previous_message = message
                else:
                    message = 'Статус не изменился.'

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
