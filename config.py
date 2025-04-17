import enum
import os
from collections import OrderedDict
from dotenv import load_dotenv

# Загрузка переменных окружения из .env
load_dotenv()

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

# Database configuration
DATABASE_NAME = 'hiring_bot.db'
