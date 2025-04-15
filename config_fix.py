"""
Temporary fix to ensure all states are properly defined
"""
import os
from dotenv import load_dotenv
import importlib
import sys

# Force reload the config module
if 'config' in sys.modules:
    del sys.modules['config']

# Now import the original config
from config import *

# Ensure WAITING_FOR_SOLUTION is defined in CandidateStates
if not hasattr(CandidateStates, 'WAITING_FOR_SOLUTION'):
    # Add the missing state
    setattr(CandidateStates, 'WAITING_FOR_SOLUTION', 'waiting_for_solution')
    print("Added missing WAITING_FOR_SOLUTION state")

# Ensure INTERVIEW_PREP_TEST is defined in CandidateStates
if not hasattr(CandidateStates, 'INTERVIEW_PREP_TEST'):
    # Add the missing state
    setattr(CandidateStates, 'INTERVIEW_PREP_TEST', 'interview_prep_test')
    print("Added missing INTERVIEW_PREP_TEST state")
