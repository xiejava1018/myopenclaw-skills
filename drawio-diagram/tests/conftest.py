import sys
from pathlib import Path

# Make scripts/ importable as a package root for tests.
SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_ROOT / "scripts"))
