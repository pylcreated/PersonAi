# chat-agent/config.py
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(dotenv_path=BASE_DIR / ".env")

# ========== 模型配置 ==========
API_KEY = os.getenv("SILICONFLOW_API_KEY", "ollama")
BASE_URL = os.getenv("SILICONFLOW_BASE_URL", "http://localhost:11434/v1")
MODEL_NAME = os.getenv("SILICONFLOW_MODEL", "qwen2.5:7b")
EMBED_MODEL = os.getenv("EMBED_MODEL", "bge-m3")
SYSTEM_PROMPT = os.getenv(
    "SYSTEM_PROMPT",
    "你是一个友好的 AI 助手，请用简洁清晰的方式回答问题。",
)

# ========== 路径配置 ==========
DATA_DIR = BASE_DIR / "data"
INBOX_DIR = DATA_DIR / "inbox"
PROCESSED_DIR = DATA_DIR / "processed"
CHUNKS_DIR = DATA_DIR / "chunks"
VECTORS_DIR = DATA_DIR / "vectors"

# ========== 策略目录 ==========
POLICY_DIR = BASE_DIR / "policies"
TEMPLATES_DIR = POLICY_DIR / "templates"
SLICE_POLICIES_DIR = POLICY_DIR / "slice_policies"
UPDATE_POLICIES_DIR = POLICY_DIR / "update_policies"

for d in (INBOX_DIR, PROCESSED_DIR, CHUNKS_DIR, VECTORS_DIR,
          TEMPLATES_DIR, SLICE_POLICIES_DIR, UPDATE_POLICIES_DIR):
    d.mkdir(parents=True, exist_ok=True)