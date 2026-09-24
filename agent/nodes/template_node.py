# chat-agent/agent/nodes/template_node.py
from agent.state import NegotiationState
from agent.nodes import ask_llm_json

PROMPT = """你是一个"知识库架构师"，正在帮用户定义"存储模板"。

【领域】{goal}
【已有模板】{template}

【你的任务】
阅读对话历史，判断用户是否明确想结束关于“存储维度”的讨论。

【绝对遵守的强制原则】
1. 只有用户明确说了“确认”、“可以了”、“开始整理吧”、“就这样”，你才能输出 `action: "done"`。
2. 如果用户输入包含问号（? 或 ？），或者包含“什么是”、“怎么”、“为什么”等疑问词，你**必须**输出 `action: "ask"`，并在 `question` 里耐心解释，然后问一个更容易理解的问题。
3. 比如用户问“什么是实体”，你**必须**回答：“实体就是具体的东西，比如人物名、地点名。以后你搜‘人物A’就能直接找到他。你希望我按人物单独存，还是按整体主题存？”（输出 action="ask"）。
4. 只有物理数学等有硬性边界的领域，你才可以因为关键字段缺失而强制追问。

输出纯 JSON：
{{
  "action": "done" | "ask",
  "question": "如果 action=ask，这是要问的问题（要通俗易懂）",
  "template": {{
    "fields": {{
      "base": ["topic", "summary", "reasoning_summary", "key_points", "terms", "source_ref"],
      "extensions": {{
        "扩展字段1": ["子字段1", "子字段2"]
      }}
    }}
  }},
  "confidence": 0.0
}}
"""


def run(state: NegotiationState) -> NegotiationState:
    prompt = PROMPT.format(
        goal=state.get("goal"),
        template=state.get("template") or {},
    )
    result = ask_llm_json(prompt, state.get("history"))

    if "error" in result:
        state["history"].append({
            "role": "assistant",
            "content": "我出了点小问题，我们继续聊，你希望我按什么维度整理？",
        })
        return state

    if result.get("action") == "done":
        state["template"] = result.get("template")
        state["phase"] = "slice"
        state["history"].append({
            "role": "assistant",
            "content": "✅ 好，模板确定。接下来我们聊聊检索策略：\n你以后想怎么查这些内容？比如直接搜'人物A'，还是搜个主题就能找到相关内容？",
        })
    else:
        state["history"].append({
            "role": "assistant",
            "content": result.get("question", "你还希望我按哪些维度整理这些知识？"),
        })

    return state