from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Any

from personal_agent.llm.base import LLMClient
from personal_agent.memory.models import (
    CandidateMemoryDraft,
    EVIDENCE_TYPES,
    EvidenceDraft,
    MEMORY_TYPES,
)


@dataclass(frozen=True)
class DailyMemoryResult:
    analysis: dict[str, Any]
    candidates: list[CandidateMemoryDraft]
    evidence: list[EvidenceDraft]


class DailyMemoryAnalyzer:
    """Uses an LLM to summarize a day and propose reviewable memories."""

    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    @property
    def model_name(self) -> str:
        return self.llm.model_name

    def analyze(
        self,
        analysis_date: date,
        messages: list[dict[str, object]],
    ) -> DailyMemoryResult:
        if self.llm.model_name == "mock":
            analysis, evidence = self._mock_analysis(messages)
            return DailyMemoryResult(
                analysis=analysis,
                candidates=[],
                evidence=evidence,
            )
        raw = self.llm.complete(
            self._build_prompt(analysis_date, messages),
            json_mode=True,
        )
        return self._parse_result(raw, messages)

    @staticmethod
    def _build_prompt(
        analysis_date: date,
        messages: list[dict[str, object]],
    ) -> str:
        conversation_text = "\n".join(
            f"[message_id={item['id']}][{item['created_at']}] "
            f"{item['role']}: {item['content']}"
            for item in messages
        )
        return f"""
请分析下面一天的真实聊天，生成日报并提出“候选长期记忆”。

重要原则：
1. 只能依据聊天，不得编造。
2. 候选记忆不会自动生效，之后由用户审核。
3. 只提取未来仍可能有价值的信息，例如稳定资料、明确偏好、长期目标、
   持续项目、技能或重要经验。
4. 不要把临时情绪、当天身体状态、随口一说或助手自己的内容作为长期记忆。
5. 不确定时不要生成候选。
6. 只返回 JSON，不要 Markdown。
7. progress、next_actions 中的每一项都必须提供至少一条 evidence。
8. evidence 只能引用 user 消息，quote 必须逐字来自对应消息。
9. confidence 是对整份日报事实可靠度的 0 到 1 评分。

允许的记忆类型：
profile, preference, goal, project, skill, experience

日期：{analysis_date.isoformat()}

聊天记录：
{conversation_text}

返回结构：
{{
  "summary": "...",
  "progress": ["..."],
  "patterns": ["..."],
  "mood": "...",
  "next_actions": ["..."],
  "confidence": 0.85,
  "evidence": [
    {{
      "evidence_type": "progress",
      "claim": "完成FastAPI接口",
      "message_id": 123,
      "quote": "FastAPI接口已经测试通过"
    }}
  ],
  "memory_candidates": [
    {{
      "type": "project",
      "content": "用户正在开发个人Agent",
      "confidence": 0.8,
      "importance": 0.7,
      "evidence_message_ids": [123],
      "created_reason": "用户明确描述了持续项目进展"
    }}
  ]
}}
""".strip()

    @staticmethod
    def _parse_result(
        raw_text: str,
        messages: list[dict[str, object]],
    ) -> DailyMemoryResult:
        text = raw_text.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end < start:
            raise ValueError("模型没有返回 JSON 对象")
        data = json.loads(text[start : end + 1])
        if not isinstance(data, dict):
            raise ValueError("每日分析必须是 JSON 对象")

        for field in ("summary", "mood"):
            if not isinstance(data.get(field), str) or not data[field].strip():
                raise ValueError(f"每日分析字段 {field} 无效")
            data[field] = data[field].strip()
        for field in ("progress", "patterns", "next_actions"):
            value = data.get(field)
            if value is None:
                items: list[object] = []
            elif isinstance(value, str):
                items = [value]
            elif isinstance(value, list):
                items = value
            else:
                raise ValueError(f"每日分析字段 {field} 必须是字符串数组")
            data[field] = [
                item.strip()
                for item in items
                if isinstance(item, str) and item.strip()
            ]
        # Retained internally for backward-compatible SQLite storage only.
        data["obstacles"] = []

        try:
            confidence = float(data.get("confidence", 0.5))
        except (TypeError, ValueError) as exc:
            raise ValueError("日报 confidence 必须是 0 到 1 的数字") from exc
        if not 0 <= confidence <= 1:
            raise ValueError("日报 confidence 必须位于 0 到 1")
        data["confidence"] = confidence

        evidence = DailyMemoryAnalyzer._parse_evidence(
            data.pop("evidence", []),
            data,
            messages,
        )

        raw_candidates = data.pop("memory_candidates", [])
        if not isinstance(raw_candidates, list):
            raw_candidates = []
        candidates: list[CandidateMemoryDraft] = []
        seen: set[tuple[str, str]] = set()
        evidence_message_ids = {item.message_id for item in evidence}
        for raw_candidate in raw_candidates:
            if not isinstance(raw_candidate, dict):
                continue
            memory_type = str(raw_candidate.get("type", "")).strip().lower()
            if memory_type and memory_type not in MEMORY_TYPES:
                raise ValueError(f"无效记忆类型：{memory_type}")
            try:
                candidate = CandidateMemoryDraft.from_mapping(raw_candidate)
            except ValueError:
                continue
            key = (candidate.type, candidate.content.casefold())
            if key not in seen:
                known_ids = {
                    int(item["id"])
                    for item in messages
                    if item.get("role") == "user"
                }
                if not set(candidate.evidence_message_ids) <= known_ids:
                    continue
                if not set(candidate.evidence_message_ids) <= evidence_message_ids:
                    continue
                candidates.append(candidate)
                seen.add(key)
        return DailyMemoryResult(
            analysis=data,
            candidates=candidates,
            evidence=evidence,
        )

    @staticmethod
    def _parse_evidence(
        raw_evidence: object,
        analysis: dict[str, Any],
        messages: list[dict[str, object]],
    ) -> list[EvidenceDraft]:
        if not isinstance(raw_evidence, list):
            raise ValueError("日报 evidence 必须是数组")
        user_messages = {
            int(item["id"]): item
            for item in messages
            if item.get("role") == "user"
        }
        field_values: dict[str, set[str]] = {
            "summary": {analysis["summary"]},
            "progress": set(analysis["progress"]),
            "pattern": set(analysis["patterns"]),
            "mood": {analysis["mood"]},
            "next_action": set(analysis["next_actions"]),
        }
        result: list[EvidenceDraft] = []
        seen: set[tuple[str, str, int, str]] = set()
        for item in raw_evidence:
            if not isinstance(item, dict):
                raise ValueError("每条 evidence 必须是对象")
            evidence_type = str(item.get("evidence_type", "")).strip()
            claim = str(item.get("claim", "")).strip()
            quote = str(item.get("quote", "")).strip()
            message_id = item.get("message_id")
            if evidence_type not in EVIDENCE_TYPES:
                raise ValueError(f"无效 evidence 类型：{evidence_type}")
            if evidence_type == "obstacle":
                # Ignore legacy obstacle evidence from older model responses.
                continue
            if claim not in field_values[evidence_type]:
                raise ValueError("evidence claim 不属于对应日报字段")
            if not isinstance(message_id, int) or message_id not in user_messages:
                raise ValueError("evidence message_id 不存在或不是用户消息")
            source = user_messages[message_id]
            if not quote or quote not in str(source["content"]):
                raise ValueError("evidence quote 与原始消息不一致")
            key = (evidence_type, claim, message_id, quote)
            if key in seen:
                continue
            seen.add(key)
            result.append(
                EvidenceDraft(
                    evidence_type=evidence_type,
                    claim=claim,
                    message_id=message_id,
                    quote=quote,
                    message_created_at=str(source["created_at"]),
                )
            )

        for evidence_type, analysis_field in (
            ("progress", "progress"),
            ("next_action", "next_actions"),
        ):
            covered = {
                item.claim
                for item in result
                if item.evidence_type == evidence_type
            }
            missing = set(analysis[analysis_field]) - covered
            if missing:
                raise ValueError(
                    f"日报 {analysis_field} 缺少 evidence：{sorted(missing)}"
                )
        return result

    @staticmethod
    def _mock_analysis(
        messages: list[dict[str, object]],
    ) -> tuple[dict[str, Any], list[EvidenceDraft]]:
        user_messages = [
            item
            for item in messages
            if item.get("role") == "user"
        ]
        if not user_messages:
            return {
                "summary": "当天没有用户对话内容。",
                "progress": [],
                "obstacles": [],
                "patterns": [],
                "mood": "信息不足，无法进一步判断",
                "next_actions": [],
                "confidence": 1.0,
            }, []
        contents = [str(item["content"]) for item in user_messages]
        summary = f"当天共记录 {len(contents)} 条用户消息：" + "；".join(
            contents[:5]
        )
        first = user_messages[0]
        return {
            "summary": summary,
            "progress": [],
            "obstacles": [],
            "patterns": [],
            "mood": "信息不足，无法进一步判断",
            "next_actions": [],
            "confidence": 1.0,
        }, [
            EvidenceDraft(
                evidence_type="summary",
                claim=summary,
                message_id=int(first["id"]),
                quote=str(first["content"]),
                message_created_at=str(first["created_at"]),
            )
        ]
