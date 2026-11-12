import sys
from pathlib import Path

RULES = Path(__file__).resolve().parents[1]
REPO = RULES.parents[3]
for p in (str(RULES), str(REPO)):
    if p not in sys.path:
        sys.path.insert(0, p)
