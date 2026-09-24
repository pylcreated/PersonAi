# chat-agent/agent/nodes/update_node.py
from agent.state import NegotiationState
from agent.nodes import ask_llm_json

PROMPT = """你正在确定知识库的更新策略。

【用户最新回答】
{last_user}

【任务】
根据用户的回答，判断他希望的更新策略。

可选：
- append：追加（每次都是新知识）
- overwrite：覆盖（新知识替换旧知识）
- version：版本化（保留旧版本，标记新版本为 current）

用户回答里包含"保留"、"旧版本"、"复盘" → version
用户回答里包含"覆盖"、"最新"、"不用留" → overwrite
用户回答里包含"追加"、"都留着" → append
不确定 → 默认 append

输出纯 JSON：
{{
  "action": "done",
  "update_policy": {{
    "default_strategy": "append | overwrite | version",
    "by_type": {{
      "fact": "overwrite",
      "conclusion": "overwrite",
      "evolution": "version",
      "discussion": "append",
      "reasoning": "append"
    }},
    "fallback": "append"
  }}
}}
"""


def run(state: NegotiationState) -> NegotiationState:
    last_user = ""
    for h in reversed(state.get("history", [])):
        if h["role"] == "user":
            last_user = h["content"]
            break

    prompt = PROMPT.format(last_user=last_user)
    result = ask_llm_json(prompt)

    if "error" in result:
        state["update_policy"] = {
            "default_strategy": "append",
            "by_type": {
                "fact": "overwrite",
                "conclusion": "overwrite",
                "evolution": "version",
                "discussion": "append",
                "reasoning": "append",
            },
            "fallback": "append",
        }
    else:
        state["update_policy"] = result.get("update_policy") or {}

    state["phase"] = "confirm"

    # 生成预览
    tpl = state.get("template") or {}
    sp = state.get("slice_policy") or {}
    summary = "【协商结果预览】\n"
    summary += f"领域：{state.get('goal')}\n"
    summary += f"模板字段：{list(tpl.get('fields', {}).get('extensions', {}).keys())}\n"
    summary += f"切片策略：{sp.get('strategy', 'by_field')}\n"
    summary += f"更新策略：{state['update_policy'].get('default_strategy')}\n"
    summary += "\n确认使用这套方案吗？（回复：确认 / 修改）"

    state["history"].append({"role": "assistant", "content": summary})
    return state