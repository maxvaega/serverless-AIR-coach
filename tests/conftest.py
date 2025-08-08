import sys
from pathlib import Path

# Assicura che la root del progetto sia nel PYTHONPATH quando pytest cambia i path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


