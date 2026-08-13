from pathlib import Path
import os

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

DATA_DIR = PROJECT_ROOT / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
ANALYSIS_DIR = DATA_DIR / "analyses"
SAMPLE_DIR = PROJECT_ROOT / "samples"
DATABASE_PATH = DATA_DIR / "bayyinah.db"

MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE_MB", "10")) * 1024 * 1024
MAX_SHEETS = int(os.getenv("MAX_SHEETS", "20"))
MAX_ROWS = int(os.getenv("MAX_ROWS", "100000"))
MAX_COLUMNS = int(os.getenv("MAX_COLUMNS", "200"))
DEFAULT_MAX_ITERATIONS = max(1, min(5, int(os.getenv("MAX_AGENT_ITERATIONS", "3"))))

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq").strip().lower()
if LLM_PROVIDER not in {"mock", "ollama", "groq"}:
    raise RuntimeError("LLM_PROVIDER must be 'mock', 'ollama', or 'groq'.")

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2").strip()
OLLAMA_TIMEOUT_SECONDS = max(5.0, float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "120")))

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip()
GROQ_TIMEOUT_SECONDS = max(5.0, float(os.getenv("GROQ_TIMEOUT_SECONDS", "60")))

FRONTEND_ORIGINS = [
    origin.strip().rstrip("/")
    for origin in os.getenv(
        "FRONTEND_ORIGINS", "http://127.0.0.1:3000,http://localhost:3000"
    ).split(",")
    if origin.strip()
]
CORS_ORIGIN_REGEX = os.getenv("CORS_ORIGIN_REGEX", "").strip() or None

for directory in (DATA_DIR, UPLOAD_DIR, ANALYSIS_DIR, SAMPLE_DIR):
    directory.mkdir(parents=True, exist_ok=True)
