# chat-agent/tools/knowledge_updater.py
import json
from config import UPDATE_POLICIES_DIR
from tools.vector_store import embed, update_metadata, get_by_entity_key, _collection


def load_update_policy(policy_id: str) -> dict:
    path = UPDATE_POLICIES_DIR / f"{policy_id}.json"
    if not path.exists():
        return {
            "default_strategy": "append",
            "by_type": {},
            "fallback": "append",
        }
    return json.loads(path.read_text(encoding="utf-8"))


def mark_deprecated(entity_key: str):
    if not entity_key:
        return
    ids = get_by_entity_key(entity_key)
    if ids:
        metas = [{"status": "deprecated"} for _ in ids]
        update_metadata(ids, metas)


def get_next_version(entity_key: str) -> int:
    ids = get_by_entity_key(entity_key)
    return len(ids) + 1


def add_new(item: dict):
    """单条入向量库（简单实现，失败会忽略）"""
    try:
        text = item.get("text") or item.get("summary") or ""
        if not text:
            return
        uid = item.get("id") or f"{item.get('entity_key', 'unknown')}-{id(item)}"
        _collection.upsert(
            ids=[uid],
            documents=[text],
            metadatas=[{k: v for k, v in item.items() if isinstance(v, (str, int, float, bool))}],
            embeddings=[embed(text)],
        )
    except Exception:
        pass


def upsert_knowledge(item: dict, policy: dict):
    ktype = item.get("knowledge_type", "unknown")
    entity_key = item.get("entity_key")
    confidence = item.get("confidence", 0.0)

    by_type = policy.get("by_type", {})
    strategy = by_type.get(ktype)

    if strategy is None or confidence < 0.5 or ktype == "unknown":
        strategy = policy.get("fallback", "append")

    if strategy == "append":
        item["status"] = "current"
        add_new(item)

    elif strategy == "overwrite":
        if entity_key:
            mark_deprecated(entity_key)
        item["status"] = "current"
        add_new(item)

    elif strategy == "version":
        if entity_key:
            mark_deprecated(entity_key)
            item["version"] = get_next_version(entity_key)
        item["status"] = "current"
        add_new(item)

    else:
        item["status"] = "unclassified"
        item["needs_review"] = True
        add_new(item)