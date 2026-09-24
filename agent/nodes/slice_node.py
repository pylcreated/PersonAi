# chat-agent/agent/nodes/slice_node.py
from agent.state import NegotiationState
from agent.nodes import ask_llm_json

PROMPT = """你正在帮用户确定知识库的"检索与切片策略"。

【当前模板】
{template}

【当前已有策略】
{slice_policy}

【核心原则】
1. 绝对不要自作主张结束。
2. 用户说"可以了"、"确认"、"就这样"，才输出 action="done"。
3. 用户问"什么是实体"，解释清楚："实体就是具体的东西，比如人物名、地点名。按实体切，就是每个人物单独存一条。"
4. 如果用户说"你决定"，你给一个默认策略（按summary、key_points、terms切），并问："这样可以吗？"
5. 一直提问和解释，直到用户喊停。

输出纯 JSON：
{{
  "action": "done" | "ask",
  "question": "如果 action=ask，这是要问的问题（要通俗易懂）",
  "slice_policy": {{
    "strategy": "mixed",
    "base_slices": [...],
    "entities": [...],
    "preserve_raw": true,
    "raw_strategy": "on_demand",
    "granularity": "fine"
  }},
  "confidence": 0.0
}}
"""


def run(state: NegotiationState) -> NegotiationState:
    prompt = PROMPT.format(
        template=state.get("template") or {},
        slice_policy=state.get("slice_policy") or {},
    )
    result = ask_llm_json(prompt, state.get("history"))

    if "error" in result:
        state["history"].append({
            "role": "assistant",
            "content": "请继续告诉我你想怎么查这些内容。",
        })
        return state

    if result.get("action") == "done":
        state["slice_policy"] = result.get("slice_policy")
        state["phase"] = "update"
        state["history"].append({
            "role": "assistant",
            "content": (
                "✅ 好，检索策略确定。最后确认：\n"
                "如果修改了设定，你希望我保留旧版本，还是直接覆盖？"
            ),
        })
    else:
        state["history"].append({
            "role": "assistant",
            "content": result.get("question", "你以后想怎么查这些内容？"),
        })

    return state