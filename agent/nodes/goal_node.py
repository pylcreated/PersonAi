# chat-agent/agent/nodes/goal_node.py
from agent.state import NegotiationState
from agent.nodes import ask_llm_json

PROMPT = """你是知识库协商助手。用户刚表达了一个需求。

【用户输入】
{user_input}

【任务】
1. 判断领域（用你自己的判断，不要局限于预设）
2. 基于这个领域，提出3~5个"知识应该按什么维度存储"的建议
3. 用一句话问用户是否同意

【重要】
- 你不是这个领域的顾问，不要讨论领域内容
- 你只是问：这些知识应该怎么分类存

输出纯 JSON（不要 Markdown 包裹）：
{{
  "goal": "novel | academic | legal | general",
  "scene_name": "场景中文名",
  "suggested_dimensions": ["维度1", "维度2", "维度3"],
  "first_question": "向用户提出的第一个问题，用于确认关注维度，要给出 2~4 个候选"
}}
"""


def run(state: NegotiationState) -> NegotiationState:
    prompt = PROMPT.format(user_input=state["user_input"])
    result = ask_llm_json(prompt)

    if "error" in result:
        state["goal"] = "general"
        state["history"].append({
            "role": "assistant",
            "content": "好的，先按通用方式整理。你希望我重点关注哪些方面？",
        })
    else:
        state["goal"] = result.get("goal", "general")
        state["history"].append({
            "role": "assistant",
            "content": result.get("first_question", "你希望我重点关注哪些方面？"),
        })

    state["phase"] = "template"
    return state