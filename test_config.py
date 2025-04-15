# Test the config import
from config import CandidateStates

# Print all the states to verify they exist
print("Available CandidateStates:")
for attr in dir(CandidateStates):
    if not attr.startswith('__'):
        print(f"- {attr} = {getattr(CandidateStates, attr)}")

# Specifically check for WAITING_FOR_SOLUTION
print("\nSpecifically checking for WAITING_FOR_SOLUTION:")
if hasattr(CandidateStates, 'WAITING_FOR_SOLUTION'):
    print(f"✓ Found: CandidateStates.WAITING_FOR_SOLUTION = {CandidateStates.WAITING_FOR_SOLUTION}")
else:
    print("✗ Error: CandidateStates has no attribute 'WAITING_FOR_SOLUTION'")
