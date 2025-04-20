import os
from dotenv import load_dotenv

load_dotenv()
# Load PostgreSQL configuration
load_dotenv('postgres.env')

# Bot tokens
CANDIDATE_BOT_TOKEN = os.getenv('CANDIDATE_BOT_TOKEN')
RECRUITER_BOT_TOKEN = os.getenv('RECRUITER_BOT_TOKEN')

# PostgreSQL database configuration
DB_HOST = os.getenv("HOST")
DB_PORT = os.getenv("PORT")
DB_NAME = os.getenv("DATABASE")
DB_USER = os.getenv("USER")
DB_PASSWORD = os.getenv("PASSWORD")
BOT_PREFIX = os.getenv("BOT_PREFIX", "naim_bot_")

# States for the FSM (Finite State Machine)
class CandidateStates:
    MAIN_MENU = 'main_menu'
    ABOUT_COMPANY = 'about_company'
    PRIMARY_FILE = 'primary_file'
    PRIMARY_TEST = 'primary_test'
    WHERE_TO_START = 'where_to_start'
    WHERE_TO_START_TEST = 'where_to_start_test'
    PREPARATION_MATERIALS = 'preparation_materials'
    CONTACT_DEVELOPERS = 'contact_developers'
    TAKE_TEST = 'take_test'
    INTERVIEW_PREP = 'interview_prep'
    SCHEDULE_INTERVIEW = 'schedule_interview'
    STOPWORDS_TEST = 'stopwords_test'

class RecruiterStates:
    MAIN_MENU = 'main_menu'
    REVIEW_TEST = 'review_test'
    SCHEDULE_INTERVIEW = 'schedule_interview'
