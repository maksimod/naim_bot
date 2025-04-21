import enum
import os
from collections import OrderedDict
from dotenv import load_dotenv

# Загрузка переменных окружения из .env
load_dotenv()

# Определение режима работы (develop или production)
MODE = os.getenv("MODE")

# Загрузка переменных для PostgreSQL из соответствующего файла
if MODE == "develop":
    load_dotenv('postgres.develop.env')
    print("Running in DEVELOPMENT mode")
else:
    load_dotenv('postgres.env')
    print("Running in PRODUCTION mode")

class CandidateStates(enum.Enum):
    """Состояния для бота кандидата"""
    START = 0
    MAIN_MENU = 1
    ABOUT_COMPANY = 2
    WHERE_TO_START = 3
    STOPWORDS_TEST = 4  # Новое состояние для теста стоп-слов
    PRIMARY_TEST = 5
    LOGIC_TEST = 6
    PREPARATION_MATERIALS = 7
    PRACTICE_TEST = 8
    TAKE_TEST = 9
    INTERVIEW_PREP = 10
    SCHEDULE_INTERVIEW = 11
    CONTACT_DEVELOPERS = 12
    
    # Добавляем старые состояния для обратной совместимости
    PRIMARY_FILE = 13
    LOGIC_TEST_PREPARE = 14
    LOGIC_TEST_TESTING = 15
    WHERE_TO_START_TEST = 16
    WAITING_FOR_SOLUTION = 17
    INTERVIEW_PREP_TEST = 18

class RecruiterStates(enum.Enum):
    """Состояния для бота рекрутера"""
    START = 0
    MAIN_MENU = 1
    LOGIN = 2
    REGISTRATION = 3
    CANDIDATES = 4
    SCHEDULE = 5
    SETTINGS = 6
    STATISTICS = 7
    HELP = 8
    SCHEDULE_INTERVIEW = 9
    MANAGE_CANDIDATES = 10
    VIEW_CANDIDATE = 11
    REVIEW_TEST = 12  # Добавил для совместимости
    REVIEW_FEEDBACK = 13  # Добавлено для обработки отзывов на тестовые задания
    INTERVIEW_RESPONSE = 14  # Добавлено для обработки ответов на запросы интервью

class RegistrationStates(enum.Enum):
    """Состояния для процесса регистрации рекрутера"""
    NAME = 0
    EMAIL = 1
    POSITION = 2
    CITY = 3
    CONFIRM = 4

# Загрузка токенов ботов
CANDIDATE_BOT_TOKEN = os.getenv("CANDIDATE_BOT_TOKEN")
RECRUITER_BOT_TOKEN = os.getenv("RECRUITER_BOT_TOKEN")

# Проверка наличия токенов
if not CANDIDATE_BOT_TOKEN:
    raise ValueError("CANDIDATE_BOT_TOKEN not set in environment variables")

if not RECRUITER_BOT_TOKEN:
    raise ValueError("RECRUITER_BOT_TOKEN not set in environment variables")

# PostgreSQL database configuration
DB_HOST = os.getenv("HOST")
DB_PORT = os.getenv("PORT")
DB_NAME = os.getenv("DATABASE")
DB_USER = os.getenv("DB_USER")  # Исправлено с USER на DB_USER для соответствия с файлами конфигурации
DB_PASSWORD = os.getenv("DB_PASSWORD")
BOT_PREFIX = os.getenv("BOT_PREFIX", "naim_bot_")

# Проверка наличия необходимых переменных для подключения к PostgreSQL
if not all([DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD]):
    raise ValueError(f"PostgreSQL connection parameters not set in {'postgres.develop.env' if MODE == 'develop' else 'postgres.env'}")
