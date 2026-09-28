import sys
from pathlib import Path

# Add project root directory to sys.path so tests can import root modules (evaluator.py, db.py, etc.)
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))
