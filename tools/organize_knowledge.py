# chat-agent/tools/organize_knowledge.py
import json
from openai import OpenAI
from config import API_KEY, BASE_URL, MODEL_NAME, TEMPLATES_DIR

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)


def load_template(policy_id: str) -> dict:
    path = TEMPLATES_DIR / f"{policy_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"找不到模板：{path}")
    return json.loads(path.read_text(encoding="utf-8"))


def build_prompt(template: dict, text_plain: str, source_ref: dict) -> str:
    return f"""你是知识库整理助手。请严格按下面的模板整理对话。

【模板】
{json.dumps(template, ensure_ascii=False, indent=2)}

【输入文本】
{text_plain}

【来源】
{json.dumps(source_ref, ensure_ascii=False)}

要求：
1. 模板里定义的字段必须全部输出。
2. 不要增减字段。
3. 没有内容的字段留空，不要编造。
4. 只基于原文提取，不要补充外部知识。
5. 输出纯 JSON，不要 Markdown 代码块。
"""


def organize_one_turn(cleaned: dict, turn: dict, template: dict) -> dict:
    source_ref = {
        "conversation_id": cleaned.get("conversation_id"),
        "turn_index": turn.get("turn_index", 0),
    }
    prompt = build_prompt(template, turn.get("text_plain", ""), source_ref)

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            stream=False,
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.strip("`").strip()
            if raw.startswith("json"):
                raw = raw[4:].strip()
        result = json.loads(raw)
        # 补上 source_ref 和 knowledge_type
        result.setdefault("source_ref", source_ref)
        result.setdefault("knowledge_type", "unknown")
        result.setdefault("update_strategy", "append")
        result.setdefault("entity_key", None)
        result.setdefault("confidence", 0.7)
        return result
    except json.JSONDecodeError:
        return {
            "error": "LLM 输出不是合法 JSON",
            "raw": raw if "raw" in locals() else "无返回内容",
            "source_ref": source_ref,
        }
    except Exception as e:
        return {
            "error": f"调用 LLM 失败: {str(e)}",
            "source_ref": source_ref,
        }


def organize_conversation(cleaned: dict, policy_id: str) -> list:
    template = load_template(policy_id)
    results = []
    for turn in cleaned.get("turns", []):
        results.append(organize_one_turn(cleaned, turn, template))
    return results