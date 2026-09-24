# chat-agent/tools/clean_conversation.py
import re
import hashlib
from typing import Dict, Any

def normalize_text(text: str) -> str:
    """基础清洗：换行统一、去多余空格"""
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def strip_markdown(text: str) -> str:
    """去除 Markdown 格式，但保护代码和公式"""
    if not text:
        return ""
    # 1. 保护代码块（替换为占位符）
    code_blocks = []
    def save_code(m):
        code_blocks.append(m.group(1))
        return f"__CODE_{len(code_blocks)-1}__"
    text = re.sub(r"```[\w+-]*\n(.*?)```", save_code, text, flags=re.S)
    
    # 2. 保护行内代码
    inline_codes = []
    def save_inline(m):
        inline_codes.append(m.group(1))
        return f"__ICODE_{len(inline_codes)-1}__"
    text = re.sub(r"`([^`]+)`", save_inline, text)

    # 3. 去除公式定界符（保留内容）
    text = re.sub(r"\$\$(.*?)\$\$", r"\1", text, flags=re.S)
    text = re.sub(r"\$(.*?)\$", r"\1", text)

    # 4. 去除 Markdown 标记
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.M)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"__(.*?)__", r"\1", text)
    text = re.sub(r"\*(.*?)\*", r"\1", text)
    text = re.sub(r"_(.*?)_", r"\1", text)
    text = re.sub(r"~~(.*?)~~", r"\1", text)
    text = re.sub(r"^>\s?", "", text, flags=re.M)
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.M)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.M)
    text = re.sub(r"<[^>]+>", "", text)

    # 5. 合并多余换行为空格（如果是要一整段纯文本）
    text = re.sub(r"\n+", " ", text)

    # 6. 还原代码和公式
    for i, c in enumerate(code_blocks):
        text = text.replace(f"__CODE_{i}__", c)
    for i, c in enumerate(inline_codes):
        text = text.replace(f"__ICODE_{i}__", c)

    return text.strip()

def clean_conversation(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    输入原始 JSON，输出清洗后的结构化数据。
    """
    messages = raw.get("messages", [])
    turns = []
    current_user = None

    for msg in messages:
        role = msg.get("role")
        content = normalize_text(msg.get("content", ""))

        if role == "system":
            continue  # 暂不处理系统提示词

        if role == "user":
            current_user = {
                "content": content,
                "timestamp": msg.get("timestamp")
            }
        elif role == "assistant" and current_user:
            # 配对成一轮对话
            answer_plain = strip_markdown(content)
            question = strip_markdown(current_user["content"])
            
            turns.append({
                "turn_index": len(turns),
                "question": question,
                "answer_plain": answer_plain,
                "text_plain": f"用户：{question}\n助手：{answer_plain}",
                "user_timestamp": current_user["timestamp"],
                "assistant_timestamp": msg.get("timestamp"),
            })
            current_user = None

    result = {
        "conversation_id": raw.get("conversation_id"),
        "source": raw.get("source"),
        "title": raw.get("title"),
        "created_at": raw.get("created_at"),
        "turns": turns,
    }
    result["clean_hash"] = hashlib.md5(str(result).encode("utf-8")).hexdigest()
    return result