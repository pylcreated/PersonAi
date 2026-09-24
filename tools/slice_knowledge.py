# chat-agent/tools/slice_knowledge.py
import json
from config import SLICE_POLICIES_DIR


def load_slice_policy(policy_id: str) -> dict:
    path = SLICE_POLICIES_DIR / f"{policy_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"找不到切片策略：{path}")
    return json.loads(path.read_text(encoding="utf-8"))


def get_field(obj: dict, path: str):
    cur = obj
    for key in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(key)
        else:
            return None
    return cur


def _safe_format(template: str, data: dict) -> str:
    try:
        return template.format(**data)
    except (KeyError, IndexError):
        # 简单替换失败时，用 str 兜底
        result = template
        for k, v in data.items():
            result = result.replace("{" + k + "}", str(v))
        return result


def split_chunk(item: dict, policy: dict) -> list:
    """
    按 slice_policy 拆片。
    返回 [(id_suffix, text, type_, layer), ...]
    """
    fragments = []

    # 基础字段
    for s in policy.get("base_slices", []):
        value = get_field(item, s["field"])
        if value:
            data = {**item, "value": value}
            text = _safe_format(s["template"], data)
            fragments.append((
                s["type"],
                text,
                s["type"],
                s.get("layer", "conclusion"),
            ))

    # 实体字段
    for e in policy.get("entities", []):
        values = get_field(item, e["field"]) or []
        if not isinstance(values, list):
            continue
        for i, v in enumerate(values):
            if isinstance(v, str):
                v = {"value": v}
            if not isinstance(v, dict):
                continue
            key = v.get(e.get("key", "value"), i)
            text = _safe_format(e["template"], v)
            fragments.append((
                f"{e['type']}-{key}",
                text,
                e["type"],
                e.get("layer", "conclusion"),
            ))

    return fragments