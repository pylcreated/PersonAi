from __future__ import annotations

import json
from typing import Callable

from personal_agent.agent.prompt import build_planner_prompt
from personal_agent.agent.task import TaskPlan, TaskStep
from personal_agent.llm.base import LLMClient
from personal_agent.tools.registry import ToolRegistry


class Planner:
    """LLM-backed planner constrained to the registered tool allowlist."""

    MAX_STEPS = 8

    def __init__(
        self,
        llm: LLMClient,
        registry: ToolRegistry,
        context_provider: Callable[[str], str] | None = None,
    ) -> None:
        self.llm = llm
        self.registry = registry
        self.context_provider = context_provider or (lambda _: "")

    def create_plan(self, user_input: str) -> TaskPlan:
        cleaned = (user_input or "").strip()
        if not cleaned:
            raise ValueError("任务内容不能为空")
        raw = self.llm.complete(
            build_planner_prompt(
                cleaned,
                self.registry.descriptions(),
                self.context_provider(cleaned),
            ),
            json_mode=True,
        )
        return self.parse(raw, cleaned)

    def parse(self, raw_text: str, user_input: str) -> TaskPlan:
        text = raw_text.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            lines = lines[1:] if lines else lines
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end < start:
            raise ValueError("Planner 没有返回 JSON 对象")
        value = json.loads(text[start : end + 1])
        if not isinstance(value, dict):
            raise ValueError("Planner 结果必须是 JSON 对象")
        goal = str(value.get("goal", "")).strip()
        raw_steps = value.get("steps")
        if not goal:
            raise ValueError("计划 goal 不能为空")
        if not isinstance(raw_steps, list) or not raw_steps:
            raise ValueError("计划至少需要一个步骤")
        if len(raw_steps) > self.MAX_STEPS:
            raise ValueError(f"计划最多允许 {self.MAX_STEPS} 个步骤")

        allowed = {
            str(item["name"]): item
            for item in self.registry.descriptions()
        }
        steps: list[TaskStep] = []
        for index, raw_step in enumerate(raw_steps, start=1):
            if not isinstance(raw_step, dict):
                raise ValueError(f"步骤 {index} 必须是 JSON 对象")
            tool = str(raw_step.get("tool", "")).strip()
            if tool not in allowed:
                raise ValueError(f"步骤 {index} 使用未注册工具：{tool}")
            description = str(raw_step.get("description", "")).strip()
            arguments = raw_step.get("arguments", raw_step.get("args"))
            if not description:
                raise ValueError(f"步骤 {index} 缺少 description")
            if not isinstance(arguments, dict):
                raise ValueError(f"步骤 {index} arguments 必须是对象")
            self._validate_arguments(
                index,
                arguments,
                allowed[tool].get("input_schema", {}),
            )
            steps.append(
                TaskStep(
                    id=index,
                    tool=tool,
                    description=description,
                    arguments=arguments,
                )
            )
        return TaskPlan(goal=goal, steps=steps, user_input=user_input)

    @staticmethod
    def _validate_arguments(
        step_index: int,
        arguments: dict[str, object],
        raw_schema: object,
    ) -> None:
        if not isinstance(raw_schema, dict):
            return
        unknown = set(arguments) - set(raw_schema)
        if unknown:
            raise ValueError(
                f"步骤 {step_index} 包含未知参数：{', '.join(sorted(unknown))}"
            )
        missing = [
            key
            for key, description in raw_schema.items()
            if "optional" not in str(description).casefold()
            and key not in arguments
        ]
        if missing:
            raise ValueError(
                f"步骤 {step_index} 缺少参数：{', '.join(sorted(missing))}"
            )
        for key, value in arguments.items():
            expected = str(raw_schema[key]).casefold()
            if "string" in expected and not isinstance(value, str):
                raise ValueError(f"步骤 {step_index} 参数 {key} 必须是字符串")
            if "integer" in expected and (
                not isinstance(value, int) or isinstance(value, bool)
            ):
                raise ValueError(f"步骤 {step_index} 参数 {key} 必须是整数")
