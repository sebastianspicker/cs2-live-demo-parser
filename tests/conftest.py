import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER_DIR = ROOT / "server"
sys.path.insert(0, str(SERVER_DIR))
