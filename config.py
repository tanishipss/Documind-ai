# config.py  (new file — add to project root)
import os
from dataclasses import dataclass

@dataclass
class Config:
    OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3")
    BACKEND_URL: str = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
    CHROMA_PATH: str = os.getenv("CHROMA_PATH", "./data/chroma_db")
    MAX_QUESTIONS: int = int(os.getenv("MAX_QUESTIONS", "25"))
    TOP_K_CHUNKS: int = int(os.getenv("TOP_K_CHUNKS", "8"))

config = Config()

# Then in every file, replace hardcoded values:
# from config import config
# OLLAMA_URL = config.OLLAMA_URL