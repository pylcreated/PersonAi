# chat-agent/agent/nodes/confirm_node.py
from agent.state import NegotiationState


def run(state: NegotiationState) -> NegotiationState:
    # 取用户最新回答
    last_user = ""
    for h in reversed(state.get("history", [])):
        if h["role"] == "user":
            last_user = h["content"]
            break

    if any(k in last_user for k in ["确认", "可以", "好", "yes", "ok", "OK", "Yes"]):
        state["user_confirmed"] = True
        state["phase"] = "finalize"
    else:
        # 用户要求修改，回到 template 阶段
        state["phase"] = "template"
        state["history"].append({
            "role": "assistant",
            "content": "好的，请告诉我要修改哪一部分（模板 / 切片 / 更新策略）？",
        })

    return state