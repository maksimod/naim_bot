# Simple test just to print one state
from config import CandidateStates

# Try to access the problematic state
try:
    waiting_state = CandidateStates.WAITING_FOR_SOLUTION
    print(f"Success! WAITING_FOR_SOLUTION = {waiting_state}")
except AttributeError as e:
    print(f"Error: {e}")

# Also print all available states to see what's actually there
print("\nAll available CandidateStates attributes:")
for name in dir(CandidateStates):
    if not name.startswith("__"):
        try:
            value = getattr(CandidateStates, name)
            print(f"- {name} = {value}")
        except Exception as e:
            print(f"- {name}: ERROR - {e}")
