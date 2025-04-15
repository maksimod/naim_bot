import os
from dotenv import load_dotenv

load_dotenv()

# Bot tokens
CANDIDATE_BOT_TOKEN = os.getenv('CANDIDATE_BOT_TOKEN')
RECRUITER_BOT_TOKEN = os.getenv('RECRUITER_BOT_TOKEN')

# Database configuration
DATABASE_NAME = 'hiring_bot.db'

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
    WAITING_FOR_SOLUTION = 'waiting_for_solution'
    INTERVIEW_PREP = 'interview_prep'
    INTERVIEW_PREP_TEST = 'interview_prep_test'
    SCHEDULE_INTERVIEW = 'schedule_interview'

class RecruiterStates:
    MAIN_MENU = 'main_menu'
    REVIEW_TEST = 'review_test'
    SCHEDULE_INTERVIEW = 'schedule_interview'
