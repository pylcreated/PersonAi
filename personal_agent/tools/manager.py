from __future__ import annotations

from datetime import datetime
import json
from typing import Callable

from personal_agent.core.clock import local_now
from personal_agent.security.audit import AuditEvent, AuditSink
from personal_agent.security.permission import PermissionChecker
from personal_agent.tools.base import ToolCall, ToolResult
from personal_agent.tools.registry import ToolRegistry


class ToolManager:
    """Single execution gateway for lookup, authorization, execution and audit."""

    def __init__(
        self,
        registry: ToolRegistry,
        permission: PermissionChecker,
        audit: AuditSink,
        clock: Callable[[], datetime] = local_now,
    ) -> None:
        self.registry = registry
        self.permission = permission
        self.audit = audit
        self.clock = clock

    def execute(
        self,
        call: ToolCall,
        *,
        actor: str = "user",
        user_confirmed: bool = False,
    ) -> ToolResult:
        tool = self.registry.get(call.name)
        if tool is None:
            result = ToolResult(False, f"未知工具：{call.name}")
            self._audit(
                actor,
                call.name,
                "unknown",
                "",
                False,
                result,
                user_confirmed,
            )
            return result
        try:
            authorizations = tool.authorizations(call.arguments)
        except (KeyError, TypeError, ValueError, OSError) as exc:
            result = ToolResult(False, f"工具参数无效：{exc}")
            self._audit(
                actor,
                call.name,
                tool.required_permission,
                "",
                False,
                result,
                user_confirmed,
            )
            return result

        for authorization in authorizations:
            decision = self.permission.check(
                actor=actor,
                action=authorization.action,
                target=authorization.target,
                user_confirmed=user_confirmed,
                requires_confirmation=authorization.requires_confirmation,
            )
            if not decision.allowed:
                result = ToolResult(
                    False,
                    f"权限拒绝：{decision.reason}",
                    {
                        "action": authorization.action,
                        "target": authorization.target,
                        "source": decision.source,
                        "scope": decision.scope,
                    },
                )
                self._audit(
                    actor,
                    call.name,
                    authorization.action,
                    authorization.target,
                    False,
                    result,
                    user_confirmed,
                )
                return result

        try:
            result = tool.execute(call.arguments)
        except Exception as exc:
            result = ToolResult(False, f"工具执行失败：{exc}")

        primary = authorizations[0] if authorizations else None
        self._audit(
            actor,
            call.name,
            primary.action if primary else tool.required_permission,
            primary.target if primary else "",
            True,
            result,
            user_confirmed,
        )
        return result

    def preview(
        self,
        call: ToolCall,
        *,
        actor: str = "user",
    ) -> ToolResult:
        """Generate a non-mutating preview through the same scope checks."""
        tool = self.registry.get(call.name)
        if tool is None:
            result = ToolResult(False, f"未知工具：{call.name}")
            self._audit(actor, call.name, "preview", "", False, result, False)
            return result
        preview_fn = getattr(tool, "preview_call", None)
        if not callable(preview_fn):
            result = ToolResult(False, f"工具不支持预览：{call.name}")
            self._audit(actor, call.name, "preview", "", False, result, False)
            return result
        try:
            authorizations = tool.authorizations(call.arguments)
        except (KeyError, TypeError, ValueError, OSError) as exc:
            result = ToolResult(False, f"工具参数无效：{exc}")
            self._audit(actor, call.name, "preview", "", False, result, False)
            return result
        for authorization in authorizations:
            decision = self.permission.check(
                actor=actor,
                action=authorization.action,
                target=authorization.target,
                user_confirmed=False,
                requires_confirmation=False,
            )
            if not decision.allowed:
                result = ToolResult(False, f"预览权限拒绝：{decision.reason}")
                self._audit(
                    actor,
                    call.name,
                    "preview",
                    authorization.target,
                    False,
                    result,
                    False,
                )
                return result
        try:
            result = preview_fn(call.arguments)
        except Exception as exc:
            result = ToolResult(False, f"预览失败：{exc}")
        target = authorizations[0].target if authorizations else ""
        self._audit(
            actor,
            call.name,
            "preview",
            target,
            True,
            result,
            False,
        )
        return result

    def _audit(
        self,
        actor: str,
        tool: str,
        action: str,
        target: str,
        allowed: bool,
        result: ToolResult,
        user_confirmed: bool,
    ) -> None:
        detail = (
            json.dumps(result.metadata, ensure_ascii=False, default=str)[:1000]
            if result.success
            else result.content[:1000]
        )
        self.audit.record(
            AuditEvent(
                timestamp=self.clock(),
                actor=actor,
                tool=tool,
                action=action,
                target=target,
                allowed=allowed,
                result="success" if result.success else "rejected_or_failed",
                approval="user" if user_confirmed else "policy",
                detail=detail,
            )
        )
