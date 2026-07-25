from __future__ import annotations

from pathlib import Path

import pytest

from personal_agent.tools import ToolCall


@pytest.mark.module
def test_file_read_create_update_diff_and_trash_flow(tool_sandbox) -> None:
    source = tool_sandbox.workspace / "test.txt"
    source.write_text("hello agent\n", encoding="utf-8")

    read = tool_sandbox.manager.execute(
        ToolCall("read_file", {"path": str(source)})
    )
    assert read.success
    assert read.content == "hello agent\n"

    created = tool_sandbox.workspace / "test.md"
    result = tool_sandbox.manager.execute(
        ToolCall(
            "create_file",
            {"path": str(created), "content": "hello"},
        )
    )
    assert result.success
    assert created.read_text(encoding="utf-8") == "hello"

    update = ToolCall(
        "update_file",
        {"path": str(created), "content": "hello agent"},
    )
    preview = tool_sandbox.manager.preview(update)
    assert preview.success
    assert "-hello" in preview.content
    assert "+hello agent" in preview.content

    denied = tool_sandbox.manager.execute(update)
    assert not denied.success
    assert created.read_text(encoding="utf-8") == "hello"
    updated = tool_sandbox.manager.execute(update, user_confirmed=True)
    assert updated.success
    assert Path(str(updated.metadata["backup"])).read_text(
        encoding="utf-8"
    ) == "hello"

    deleted = tool_sandbox.manager.execute(
        ToolCall("delete_file", {"path": str(created)}),
        user_confirmed=True,
    )
    assert deleted.success
    assert not created.exists()
    assert (
        tool_sandbox.state
        / "trash"
        / str(deleted.metadata["trash_id"])
        / "test.md"
    ).is_file()


@pytest.mark.security
def test_external_write_system_path_and_traversal_are_denied(tool_sandbox) -> None:
    external_target = tool_sandbox.external / "outside.txt"
    external = tool_sandbox.manager.execute(
        ToolCall(
            "create_file",
            {"path": str(external_target), "content": "blocked"},
        ),
        user_confirmed=True,
    )
    assert not external.success
    assert not external_target.exists()

    system = tool_sandbox.manager.execute(
        ToolCall("read_file", {"path": r"C:\Windows\System32\kernel32.dll"})
    )
    assert not system.success
    assert "权限拒绝" in system.content

    traversal_target = (
        tool_sandbox.workspace / ".." / ".." / "password.txt"
    )
    traversal = tool_sandbox.manager.execute(
        ToolCall(
            "create_file",
            {"path": str(traversal_target), "content": "blocked"},
        )
    )
    assert not traversal.success
    assert not traversal_target.resolve().exists()


@pytest.mark.security
def test_delete_and_execute_require_confirmation(tool_sandbox) -> None:
    target = tool_sandbox.workspace / "important.txt"
    target.write_text("keep", encoding="utf-8")

    delete = tool_sandbox.manager.execute(
        ToolCall("delete_file", {"path": str(target)})
    )
    assert not delete.success
    assert "需要用户确认" in delete.content
    assert target.exists()

    tool_sandbox.permission.grant(
        "execute-task",
        tool_sandbox.workspace,
        {"execute"},
    )
    decision = tool_sandbox.permission.check(
        actor="agent",
        action="execute",
        target=str(tool_sandbox.workspace / "script.py"),
    )
    assert not decision.allowed
    assert "逐次确认" in decision.reason


@pytest.mark.security
def test_internal_agent_state_cannot_be_tampered_with(tool_sandbox) -> None:
    task_file = tool_sandbox.state / "tasks" / ("a" * 32 + ".json")
    result = tool_sandbox.manager.execute(
        ToolCall(
            "create_file",
            {"path": str(task_file), "content": "{}"},
        ),
        user_confirmed=True,
    )
    assert not result.success
    assert "内部状态保护区" in result.content


@pytest.mark.module
def test_convert_md_to_html_and_pdf_gap_is_explicit(tool_sandbox) -> None:
    source = tool_sandbox.workspace / "test.md"
    source.write_text("# Test\nhello", encoding="utf-8")
    html = tool_sandbox.workspace / "test.html"
    converted = tool_sandbox.manager.execute(
        ToolCall(
            "convert_file",
            {"source": str(source), "target": str(html)},
        )
    )
    assert converted.success
    assert "<h1>Test</h1>" in html.read_text(encoding="utf-8")

    pdf = tool_sandbox.workspace / "test.pdf"
    unsupported = tool_sandbox.manager.execute(
        ToolCall(
            "convert_file",
            {"source": str(source), "target": str(pdf)},
        )
    )
    assert not unsupported.success
    assert "PDF/DOCX" in unsupported.content
    assert not pdf.exists()


@pytest.mark.security
def test_audit_does_not_copy_read_content_or_diff(tool_sandbox) -> None:
    target = tool_sandbox.workspace / "secret.txt"
    target.write_text("TOP-SECRET-OLD", encoding="utf-8")
    tool_sandbox.manager.execute(
        ToolCall("read_file", {"path": str(target)})
    )
    tool_sandbox.manager.preview(
        ToolCall(
            "update_file",
            {"path": str(target), "content": "TOP-SECRET-NEW"},
        )
    )

    events = tool_sandbox.audit.recent()
    assert len(events) == 2
    serialized = "\n".join(str(item["detail"]) for item in events)
    assert "TOP-SECRET-OLD" not in serialized
    assert "TOP-SECRET-NEW" not in serialized
