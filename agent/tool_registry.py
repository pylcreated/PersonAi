# chat-agent/agent/tool_registry.py
from tools.clean_conversation import clean_conversation

# 给 LLM 看的工具描述
TOOLS = {
    "clean_conversation": {
        "function": clean_conversation,
        "description": "清洗原始对话，提取 user 和 assistant，去除 Markdown 格式，输出结构化 Q/A。仅在需要存入知识库时调用。",
        "parameters": {
            "type": "object",
            "properties": {
                "conversation_id": {
                    "type": "string",
                    "description": "原始会话 ID"
                }
            },
            "required": ["conversation_id"]
        }
    }
}