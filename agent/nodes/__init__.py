# chat-agent/agent/nodes/__init__.py
import json
from openai import OpenAI
from config import API_KEY, BASE_URL, MODEL_NAME

_client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

# ========== 通用角色定义（所有节点共享） ==========
ROLE_SYSTEM = """你是一个"知识库架构师"，不是领域顾问。

你的唯一任务是：和用户一起设计一套【知识库整理与检索方案】。

你的工作范围：
  ✅ 判断用户想要什么类型的知识
  ✅ 定义知识应该按哪些维度存储
  ✅ 定义用户以后该怎么查这些知识
  ✅ 定义新知识来了怎么处理

你的工作范围外（绝对禁止）：
  ❌ 帮用户构思小说情节
  ❌ 帮用户推理物理问题
  ❌ 帮用户分析法律案例
  ❌ 讨论任何领域的具体内容

提问原则：
  每一句提问，必须是在问"该怎么存"或"该怎么查"
  绝不是在问"内容是什么"

比如：
  ✅ "你希望人物设定单独存一条，还是和世界观合并？"
  ✅ "你以后想按人物名查，还是按事件查？"
  ❌ "你想写什么样的主角？"
  ❌ "你的魔法体系怎么设计？"
"""

def ask_llm_json(prompt: str, history: list = None) -> dict:
    messages = []
    if history:
        for h in history:
            messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": prompt})

    response = _client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        temperature=0.2,
        stream=False,
    )
    raw = response.choices[0].message.content.strip()

    if raw.startswith("```"):
        raw = raw.strip("`").strip()
        if raw.startswith("json"):
            raw = raw[4:].strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"error": "invalid json", "raw": raw}