"""
Admin commands configuration file.
This file contains all admin command definitions used in the bot.
Commands can be easily renamed by changing the first element in each list.
"""

# Admin mode activation commands - enable admin privileges
ADMIN_COMMANDS = ['admin123!', 'admin_mode']

# Reset progress commands - reset all user progress
RESET_COMMANDS = ['!reload2!', 'reset_progress']

# Skip module commands - mark current module as completed and unlock next module
SKIP_COMMANDS = ['!skip2!', 'skip_module']

# Success completion commands - mark current module as successfully completed with a checkmark
SUCCESS_COMMANDS = ['!good!', 'success_completion']

# Failure completion commands - mark current module as failed with an X mark
FAILURE_COMMANDS = ['!bad!', 'failure_completion']

# Previous module commands - lock the current module and reset the previous module's status
PREVIOUS_COMMANDS = ['!prev!', 'previous_module']

# Module order defines the progression of modules
MODULE_ORDER = [
    "about_company",
    "logic_test",
    "preparation_materials",
    "take_test",
    "interview_prep",
    "schedule_interview",
    "contact_leader"
]

# Mapping of modules to their corresponding test results
MODULE_TEST_MAPPING = {
    "logic_test": "logic_test_result",
    "take_test": "take_test_result",
    "interview_prep": "interview_prep_test"
}

def is_admin_command(text):
    """Check if the given text is an admin command"""
    return (text in ADMIN_COMMANDS or 
            text in RESET_COMMANDS or 
            text in SKIP_COMMANDS or 
            text in SUCCESS_COMMANDS or 
            text in FAILURE_COMMANDS or 
            text in PREVIOUS_COMMANDS) 