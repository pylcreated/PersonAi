# chat-agent/agent/nodes/finalize_node.py
import json
from datetime import datetime
from config import TEMPLATES_DIR, SLICE_POLICIES_DIR, UPDATE_POLICIES_DIR
from agent.state import NegotiationState


def run(state: NegotiationState) -> NegotiationState:
    goal = state.get("goal") or "general"
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    policy_id = f"{goal}-{ts}"

    (TEMPLATES_DIR / f"{policy_id}.json").write_text(
        json.dumps(state.get("template") or {}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (SLICE_POLICIES_DIR / f"{policy_id}.json").write_text(
        json.dumps(state.get("slice_policy") or {}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (UPDATE_POLICIES_DIR / f"{policy_id}.json").write_text(
        json.dumps(state.get("update_policy") or {}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    state["policy_id"] = policy_id
    state["phase"] = "done"
    state["history"].append({
        "role": "assistant",
        "content": f"✅ 协商完成，策略 ID：{policy_id}",
    })
    return state