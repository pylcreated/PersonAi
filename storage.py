# chat-agent/storage.py
import json
from config import INBOX_DIR, PROCESSED_DIR


def save_raw(conversation: dict):
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    path = INBOX_DIR / f"{conversation['conversation_id']}.json"
    path.write_text(
        json.dumps(conversation, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_raw(conversation_id: str) -> dict:
    path = INBOX_DIR / f"{conversation_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"找不到原始对话: {conversation_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def save_processed(cleaned: dict):
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    path = PROCESSED_DIR / f"{cleaned['conversation_id']}.json"
    path.write_text(
        json.dumps(cleaned, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )