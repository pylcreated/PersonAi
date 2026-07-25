from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import shutil
import unittest
from uuid import uuid4

from personal_agent.security import JsonlAuditSink, ScopedPermissionManager
from personal_agent.interfaces.cli import LocalCLI
from personal_agent.tools import ToolCall, ToolManager, ToolRegistry
from personal_agent.tools.file_tool import register_file_tools


class ToolSystemTests(unittest.TestCase):
    def setUp(self) -> None:
        test_root = Path(__file__).resolve().parent / ".test_tools_tmp"
        test_root.mkdir(exist_ok=True)
        root = (test_root / uuid4().hex).resolve()
        root.mkdir()
        self.addCleanup(self._cleanup_test_root, root, test_root.resolve())
        self.workspace = root / "workspace"
        self.external = root / "external"
        self.state = self.workspace / ".personal_agent"
        self.workspace.mkdir()
        self.external.mkdir()

        self.registry = ToolRegistry()
        register_file_tools(self.registry, self.workspace, self.state)
        self.permission = ScopedPermissionManager(self.workspace)
        self.audit = JsonlAuditSink(self.state / "audit" / "tools.jsonl")
        self.manager = ToolManager(
            self.registry,
            self.permission,
            self.audit,
        )

    @staticmethod
    def _cleanup_test_root(root: Path, expected_parent: Path) -> None:
        resolved = root.resolve()
        if resolved.parent != expected_parent:
            raise RuntimeError("拒绝清理测试范围之外的目录")
        shutil.rmtree(resolved, ignore_errors=True)

    def test_registry_exposes_seven_standardized_tools(self) -> None:
        descriptions = self.registry.descriptions()
        self.assertEqual(len(descriptions), 7)
        self.assertEqual(
            {item["name"] for item in descriptions},
            {
                "read_file",
                "search_file",
                "create_file",
                "update_file",
                "delete_file",
                "restore_file",
                "convert_file",
            },
        )
        self.assertTrue(all(item["input_schema"] for item in descriptions))

    def test_execute_permission_always_requires_explicit_confirmation(self) -> None:
        target = self.workspace / "script.py"
        self.permission.grant("task-execute", self.workspace, {"execute"})
        denied = self.permission.check(
            actor="agent",
            action="execute",
            target=str(target),
        )
        allowed = self.permission.check(
            actor="agent",
            action="execute",
            target=str(target),
            user_confirmed=True,
        )
        self.assertFalse(denied.allowed)
        self.assertTrue(allowed.allowed)

    def test_create_read_and_search_stay_inside_workspace(self) -> None:
        target = self.workspace / "Agent设计.md"
        created = self.manager.execute(
            ToolCall(
                "create_file",
                {"path": str(target), "content": "Memory 和 Tool"},
            )
        )
        self.assertTrue(created.success)

        read = self.manager.execute(
            ToolCall("read_file", {"path": str(target)})
        )
        self.assertTrue(read.success)
        self.assertEqual(read.content, "Memory 和 Tool")

        search = self.manager.execute(
            ToolCall("search_file", {"keyword": "Agent"})
        )
        self.assertTrue(search.success)
        self.assertIn(str(target), search.content)

    def test_external_path_needs_explicit_read_scope_and_never_gains_write(self) -> None:
        external_file = self.external / "private.txt"
        external_file.write_text("private", encoding="utf-8")
        denied = self.manager.execute(
            ToolCall("read_file", {"path": str(external_file)})
        )
        self.assertFalse(denied.success)
        self.assertIn("权限拒绝", denied.content)

        self.permission.grant("study", self.external, {"read"})
        allowed = self.manager.execute(
            ToolCall("read_file", {"path": str(external_file)})
        )
        self.assertTrue(allowed.success)

        write_denied = self.manager.execute(
            ToolCall(
                "create_file",
                {
                    "path": str(self.external / "new.txt"),
                    "content": "should not exist",
                },
            )
        )
        self.assertFalse(write_denied.success)
        self.assertFalse((self.external / "new.txt").exists())

    def test_agent_internal_state_directory_is_protected(self) -> None:
        internal = self.state / "audit" / "tools.jsonl"
        denied = self.manager.execute(
            ToolCall(
                "create_file",
                {"path": str(internal), "content": "tampered"},
            ),
            user_confirmed=True,
        )
        self.assertFalse(denied.success)
        self.assertIn("内部状态保护区", denied.content)

    def test_update_requires_confirmation_and_saves_previous_version(self) -> None:
        target = self.workspace / "note.txt"
        target.write_text("old\n", encoding="utf-8")
        call = ToolCall(
            "update_file",
            {"path": str(target), "content": "new\n"},
        )
        denied = self.manager.execute(call)
        self.assertFalse(denied.success)
        self.assertEqual(target.read_text(encoding="utf-8"), "old\n")

        updated = self.manager.execute(call, user_confirmed=True)
        self.assertTrue(updated.success)
        self.assertEqual(target.read_text(encoding="utf-8"), "new\n")
        backup = Path(str(updated.metadata["backup"]))
        self.assertEqual(backup.read_text(encoding="utf-8"), "old\n")

    def test_update_preview_is_permission_checked_and_does_not_audit_content(self) -> None:
        target = self.workspace / "preview.txt"
        target.write_text("secret old content\n", encoding="utf-8")
        call = ToolCall(
            "update_file",
            {"path": str(target), "content": "secret new content\n"},
        )
        preview = self.manager.preview(call)
        self.assertTrue(preview.success)
        self.assertIn("-secret old content", preview.content)
        event = self.audit.recent()[-1]
        self.assertEqual(event["action"], "preview")
        self.assertNotIn("secret old content", event["detail"])

        external = self.external / "external.txt"
        external.write_text("external secret", encoding="utf-8")
        denied = self.manager.preview(
            ToolCall(
                "update_file",
                {"path": str(external), "content": "changed"},
            )
        )
        self.assertFalse(denied.success)
        self.assertIn("权限拒绝", denied.content)

    def test_delete_moves_to_trash_and_restore_is_confirmed(self) -> None:
        target = self.workspace / "recover.txt"
        target.write_text("recover me", encoding="utf-8")
        call = ToolCall("delete_file", {"path": str(target)})
        denied = self.manager.execute(call)
        self.assertFalse(denied.success)
        self.assertTrue(target.exists())

        deleted = self.manager.execute(call, user_confirmed=True)
        self.assertTrue(deleted.success)
        self.assertFalse(target.exists())
        trash_id = str(deleted.metadata["trash_id"])

        restore_call = ToolCall("restore_file", {"trash_id": trash_id})
        restore_denied = self.manager.execute(restore_call)
        self.assertFalse(restore_denied.success)
        restored = self.manager.execute(
            restore_call,
            user_confirmed=True,
        )
        self.assertTrue(restored.success)
        self.assertEqual(target.read_text(encoding="utf-8"), "recover me")

    def test_conversion_checks_both_source_and_target_permissions(self) -> None:
        source = self.workspace / "source.md"
        target = self.workspace / "target.html"
        source.write_text("# 标题\n内容", encoding="utf-8")
        converted = self.manager.execute(
            ToolCall(
                "convert_file",
                {"source": str(source), "target": str(target)},
            )
        )
        self.assertTrue(converted.success)
        self.assertIn("<h1>标题</h1>", target.read_text(encoding="utf-8"))

        external_target = self.external / "leak.html"
        denied = self.manager.execute(
            ToolCall(
                "convert_file",
                {"source": str(source), "target": str(external_target)},
            )
        )
        self.assertFalse(denied.success)
        self.assertFalse(external_target.exists())

    def test_audit_records_success_denial_and_unknown_tool(self) -> None:
        path = self.workspace / "audit.txt"
        self.manager.execute(
            ToolCall(
                "create_file",
                {"path": str(path), "content": "logged"},
            )
        )
        self.manager.execute(
            ToolCall(
                "create_file",
                {
                    "path": str(self.external / "denied.txt"),
                    "content": "no",
                },
            )
        )
        self.manager.execute(ToolCall("missing_tool"))

        events = self.audit.recent()
        self.assertEqual(len(events), 3)
        self.assertEqual(events[0]["result"], "success")
        self.assertFalse(events[1]["allowed"])
        self.assertEqual(events[2]["tool"], "missing_tool")
        for line in self.audit.path.read_text(encoding="utf-8").splitlines():
            self.assertIsInstance(json.loads(line), dict)

    def test_cli_lists_tools_and_reads_quoted_path(self) -> None:
        target = self.workspace / "file with spaces.txt"
        target.write_text("quoted path works", encoding="utf-8")
        cli = LocalCLI.__new__(LocalCLI)
        cli.tool_manager = self.manager
        cli.tool_permission = self.permission
        cli.tool_audit = self.audit

        output = io.StringIO()
        with redirect_stdout(output):
            cli._tool_command("list")
            cli._tool_command(f'read "{target}"')

        self.assertIn("read_file", output.getvalue())
        self.assertIn("quoted path works", output.getvalue())


if __name__ == "__main__":
    unittest.main()
