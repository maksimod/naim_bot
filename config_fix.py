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

# Ensure LOGIC_TEST states are defined in CandidateStates
if not hasattr(CandidateStates, 'LOGIC_TEST'):
    setattr(CandidateStates, 'LOGIC_TEST', 'logic_test')
    print("Added missing LOGIC_TEST state")

if not hasattr(CandidateStates, 'LOGIC_TEST_PREPARE'):
    setattr(CandidateStates, 'LOGIC_TEST_PREPARE', 'logic_test_prepare')
    print("Added missing LOGIC_TEST_PREPARE state")

if not hasattr(CandidateStates, 'LOGIC_TEST_TESTING'):
    setattr(CandidateStates, 'LOGIC_TEST_TESTING', 'logic_test_testing')
    print("Added missing LOGIC_TEST_TESTING state")

# Ensure REVIEW_FEEDBACK is defined in RecruiterStates
if not hasattr(RecruiterStates, 'REVIEW_FEEDBACK'):
    # Add the missing state
    setattr(RecruiterStates, 'REVIEW_FEEDBACK', 13)
    print("Added missing REVIEW_FEEDBACK state")

# Ensure INTERVIEW_RESPONSE is defined in RecruiterStates
if not hasattr(RecruiterStates, 'INTERVIEW_RESPONSE'):
    # Add the missing state
    setattr(RecruiterStates, 'INTERVIEW_RESPONSE', 14)
    print("Added missing INTERVIEW_RESPONSE state")
