from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol


class PermissionAction(StrEnum):
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    EXECUTE = "execute"


class ResourceSource(StrEnum):
    WORKSPACE = "workspace"
    TEMPORARY = "temporary"
    EXTERNAL = "external"


@dataclass(frozen=True)
class PermissionDecision:
    allowed: bool
    reason: str
    source: str = ResourceSource.EXTERNAL
    scope: str | None = None


@dataclass(frozen=True)
class PermissionScope:
    name: str
    root: Path
    actions: frozenset[str]


class PermissionChecker(Protocol):
    """Authorization boundary evaluated before every tool operation."""

    def check(
        self,
        *,
        actor: str,
        action: str,
        target: str,
        user_confirmed: bool = False,
        requires_confirmation: bool = False,
    ) -> PermissionDecision: ...


class DenyByDefaultPermissionChecker:
    """Safe placeholder until explicit local permission policies are defined."""

    def check(
        self,
        *,
        actor: str,
        action: str,
        target: str,
        user_confirmed: bool = False,
        requires_confirmation: bool = False,
    ) -> PermissionDecision:
        return PermissionDecision(
            allowed=False,
            reason=f"尚未配置权限策略：{actor} 请求 {action} {target}",
        )


class ScopedPermissionManager:
    """Path-scoped local policy. Scope grants must come from the user interface."""

    def __init__(
        self,
        workspace_root: str | Path,
        temporary_root: str | Path | None = None,
        protected_roots: list[str | Path] | None = None,
    ) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.temporary_root = (
            Path(temporary_root).resolve() if temporary_root else None
        )
        defaults = [self.workspace_root / ".personal_agent"]
        self.protected_roots = [
            Path(item).resolve()
            for item in (
                protected_roots if protected_roots is not None else defaults
            )
        ]
        self._scopes: dict[str, PermissionScope] = {}
        self.grant(
            "workspace",
            self.workspace_root,
            {
                PermissionAction.READ,
                PermissionAction.WRITE,
                PermissionAction.DELETE,
            },
        )
        if self.temporary_root is not None:
            self.grant(
                "temporary",
                self.temporary_root,
                {
                    PermissionAction.READ,
                    PermissionAction.WRITE,
                    PermissionAction.DELETE,
                },
            )

    def grant(
        self,
        name: str,
        root: str | Path,
        actions: set[str | PermissionAction],
    ) -> None:
        normalized = frozenset(str(action) for action in actions)
        invalid = normalized - {item.value for item in PermissionAction}
        if invalid:
            raise ValueError(f"无效权限类型：{', '.join(sorted(invalid))}")
        if not normalized:
            raise ValueError("授权范围至少需要一个操作")
        self._scopes[name] = PermissionScope(
            name=name,
            root=Path(root).resolve(),
            actions=normalized,
        )

    def revoke(self, name: str) -> bool:
        if name in {"workspace", "temporary"}:
            return False
        return self._scopes.pop(name, None) is not None

    def scopes(self) -> list[PermissionScope]:
        return list(self._scopes.values())

    def check(
        self,
        *,
        actor: str,
        action: str,
        target: str,
        user_confirmed: bool = False,
        requires_confirmation: bool = False,
    ) -> PermissionDecision:
        del actor
        normalized_action = action.strip().lower()
        if normalized_action not in {item.value for item in PermissionAction}:
            return PermissionDecision(False, f"未知操作类型：{action}")
        try:
            resolved = Path(target).resolve()
        except (OSError, RuntimeError) as exc:
            return PermissionDecision(False, f"目标路径无效：{exc}")
        source = self._source_of(resolved)
        if any(self._contains(root, resolved) for root in self.protected_roots):
            return PermissionDecision(
                False,
                "目标属于 Agent 内部状态保护区",
                source,
            )
        matching = [
            scope
            for scope in self._scopes.values()
            if self._contains(scope.root, resolved)
            and normalized_action in scope.actions
        ]
        if not matching:
            return PermissionDecision(
                False,
                f"目标不在已授权的 {normalized_action} 范围内",
                source,
            )
        if normalized_action == PermissionAction.EXECUTE and not user_confirmed:
            return PermissionDecision(
                False,
                "执行代码必须由用户逐次确认",
                source,
                matching[0].name,
            )
        if requires_confirmation and not user_confirmed:
            return PermissionDecision(
                False,
                "该操作需要用户确认",
                source,
                matching[0].name,
            )
        return PermissionDecision(
            True,
            "已通过路径范围和操作权限检查",
            source,
            matching[0].name,
        )

    def _source_of(self, path: Path) -> ResourceSource:
        if self._contains(self.workspace_root, path):
            return ResourceSource.WORKSPACE
        if self.temporary_root and self._contains(self.temporary_root, path):
            return ResourceSource.TEMPORARY
        return ResourceSource.EXTERNAL

    @staticmethod
    def _contains(root: Path, path: Path) -> bool:
        return path == root or root in path.parents
