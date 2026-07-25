from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class ConversationContext:
    goals: list[dict[str, object]]
    tasks: list[dict[str, object]]
    messages: list[dict[str, object]]
    recent_analyses: list[dict[str, object]]
    memories: list[dict[str, object]]


class ContextBuilder:
    """Pure prompt builder: no database and no model-provider knowledge."""

    def build_chat_prompt(
        self,
        today: date,
        context: ConversationContext,
    ) -> str:
        goals_text = "\n".join(
            f"- [{goal['id']}] {goal['title']}" for goal in context.goals
        ) or "- 暂无长期目标"
        tasks_text = "\n".join(
            f"- [{'已完成' if task['completed'] else '未完成'}] {task['description']}"
            for task in context.tasks
        ) or "- 本周暂无任务"
        history_text = "\n".join(
            f"- {item['analysis_date']}: {item['summary']}"
            for item in reversed(context.recent_analyses)
        ) or "- 暂无历史每日摘要"
        memory_text = "\n".join(
            f"- [{item['type']}] {item['content']}"
            for item in context.memories
        ) or "- 当前问题未检索到相关的用户确认记忆"

        retained_messages = context.messages[-50:]
        conversation_text = "\n".join(
            f"{'用户' if item['role'] == 'user' else '助手'}: {item['content']}"
            for item in retained_messages
        )
        if len(conversation_text) > 12000:
            conversation_text = conversation_text[-12000:]

        return f"""
你是一个本地运行的个人目标与行动助手。请和用户进行自然、简洁、具体的中文对话。

要求：
1. 优先理解用户当前表达，不要强行说教。
2. 可以结合长期目标和本周任务提出问题或下一步行动。
3. 不要声称用户做过未在上下文中出现的事情。
4. 一次回复尽量控制在 200 字以内。
5. 普通对话只输出给用户的回复正文。涉及数据操作的指令由独立 Tool 调用流程处理。

当前日期：{today.isoformat()}

长期目标：
{goals_text}

本周任务：
{tasks_text}

最近每日摘要：
{history_text}

用户确认的相关长期记忆：
{memory_text}

今天截至目前的对话：
{conversation_text}
""".strip()
