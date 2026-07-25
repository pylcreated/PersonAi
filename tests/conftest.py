from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
from typing import Iterator
from uuid import uuid4

import pytest

from personal_agent.agent import JsonTaskStateStore
from personal_agent.memory import SQLiteAgentRepository
from personal_agent.memory import database
from personal_agent.security import JsonlAuditSink, ScopedPermissionManager
from personal_agent.tools import ToolManager, ToolRegistry
from personal_agent.tools.file_tool import register_file_tools


@dataclass
class ToolSandbox:
    root: Path
    workspace: Path
    external: Path
    state: Path
    registry: ToolRegistry
    permission: ScopedPermissionManager
    audit: JsonlAuditSink
    manager: ToolManager
    task_state: JsonTaskStateStore


@pytest.fixture
def isolated_root() -> Iterator[Path]:
    parent = Path(__file__).resolve().parents[1] / ".pytest_workspace"
    parent.mkdir(exist_ok=True)
    root = (parent / uuid4().hex).resolve()
    root.mkdir()
    try:
        yield root
    finally:
        if root.resolve().parent != parent.resolve():
            raise RuntimeError("拒绝清理 pytest 隔离范围之外的目录")
        shutil.rmtree(root, ignore_errors=True)


@pytest.fixture
def tool_sandbox(isolated_root: Path) -> ToolSandbox:
    workspace = isolated_root / "workspace"
    external = isolated_root / "external"
    state = workspace / ".personal_agent"
    workspace.mkdir()
    external.mkdir()
    registry = ToolRegistry()
    register_file_tools(registry, workspace, state)
    permission = ScopedPermissionManager(workspace)
    audit = JsonlAuditSink(state / "audit" / "tools.jsonl")
    manager = ToolManager(registry, permission, audit)
    return ToolSandbox(
        root=isolated_root,
        workspace=workspace,
        external=external,
        state=state,
        registry=registry,
        permission=permission,
        audit=audit,
        manager=manager,
        task_state=JsonTaskStateStore(state / "tasks"),
    )


@pytest.fixture
def repository(monkeypatch: pytest.MonkeyPatch) -> Iterator[SQLiteAgentRepository]:
    uri = f"file:pytest_{uuid4().hex}?mode=memory&cache=shared"
    monkeypatch.setattr(database, "DB_PATH", uri)
    anchor = database.connect_db()
    repo = SQLiteAgentRepository()
    repo.initialize()
    try:
        yield repo
    finally:
        anchor.close()
