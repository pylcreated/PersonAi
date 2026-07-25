from __future__ import annotations

import ast
import unittest
from pathlib import Path

from personal_agent.security import DenyByDefaultPermissionChecker
from personal_agent.tools import ToolRegistry

PACKAGE_ROOT = Path(__file__).resolve().parents[2] / "personal_agent"


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


class ArchitectureTests(unittest.TestCase):
    def test_core_does_not_import_concrete_adapters(self) -> None:
        forbidden_prefixes = (
            "personal_agent.memory.database",
            "personal_agent.memory.repository",
            "personal_agent.llm.ollama",
            "personal_agent.llm.openai_compatible",
            "personal_agent.interfaces",
            "personal_agent.config",
        )
        violations: list[str] = []
        for path in (PACKAGE_ROOT / "core").glob("*.py"):
            for module in imported_modules(path):
                if module.startswith(forbidden_prefixes):
                    violations.append(f"{path.name}: {module}")
        self.assertEqual(violations, [])

    def test_analysis_depends_only_on_llm_and_repository_boundaries(self) -> None:
        forbidden = {
            "personal_agent.memory.database",
            "personal_agent.llm.ollama",
            "personal_agent.llm.openai_compatible",
            "personal_agent.interfaces.cli",
        }
        violations: list[str] = []
        for path in (PACKAGE_ROOT / "analysis").glob("*.py"):
            for module in imported_modules(path):
                if module in forbidden:
                    violations.append(f"{path.name}: {module}")
        self.assertEqual(violations, [])

    def test_future_tool_and_permission_defaults_are_safe(self) -> None:
        self.assertEqual(ToolRegistry().descriptions(), [])
        decision = DenyByDefaultPermissionChecker().check(
            actor="agent",
            action="delete",
            target="file",
        )
        self.assertFalse(decision.allowed)

    def test_orchestrator_does_not_import_ui_or_concrete_adapters(self) -> None:
        forbidden_prefixes = (
            "personal_agent.interfaces",
            "personal_agent.memory.database",
            "personal_agent.llm.ollama",
            "personal_agent.llm.openai_compatible",
            "personal_agent.tools.file_tool",
        )
        violations: list[str] = []
        for path in (PACKAGE_ROOT / "agent").glob("*.py"):
            for module in imported_modules(path):
                if module.startswith(forbidden_prefixes):
                    violations.append(f"{path.name}: {module}")
        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
