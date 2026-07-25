from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import difflib
import html
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any, Mapping
from uuid import uuid4

from personal_agent.tools.base import ToolAuthorization, ToolResult

MAX_READ_BYTES = 2 * 1024 * 1024


def _path(arguments: dict[str, Any], key: str) -> Path:
    value = str(arguments.get(key, "")).strip()
    if not value:
        raise ValueError(f"缺少参数：{key}")
    return Path(value).resolve()


def _content(arguments: dict[str, Any]) -> str:
    value = arguments.get("content")
    if not isinstance(value, str):
        raise ValueError("content 必须是字符串")
    return value


@dataclass
class ReadFileTool:
    name: str = "read_file"
    description: str = "读取授权范围内的 UTF-8 文本文件"
    required_permission: str = "read"
    input_schema: Mapping[str, object] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.input_schema = {"path": "string"}

    def authorizations(self, arguments: dict[str, Any]) -> list[ToolAuthorization]:
        return [ToolAuthorization("read", str(_path(arguments, "path")))]

    def execute(self, arguments: dict[str, Any]) -> ToolResult:
        path = _path(arguments, "path")
        if not path.is_file():
            return ToolResult(False, f"文件不存在：{path}")
        if path.stat().st_size > MAX_READ_BYTES:
            return ToolResult(False, "文件超过 2 MiB，拒绝一次性读取")
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return ToolResult(False, "当前版本只读取 UTF-8 文本文件")
        return ToolResult(
            True,
            content,
            {"path": str(path), "bytes": path.stat().st_size},
        )


@dataclass
class SearchFileTool:
    default_root: Path
    name: str = "search_file"
    description: str = "按文件名在授权目录中递归搜索"
    required_permission: str = "read"
    input_schema: Mapping[str, object] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.default_root = self.default_root.resolve()
        self.input_schema = {
            "keyword": "string",
            "root": "string (optional)",
            "limit": "integer (optional)",
        }

    def _root(self, arguments: dict[str, Any]) -> Path:
        raw = str(arguments.get("root", "")).strip()
        return Path(raw).resolve() if raw else self.default_root

    def authorizations(self, arguments: dict[str, Any]) -> list[ToolAuthorization]:
        keyword = str(arguments.get("keyword", "")).strip()
        if not keyword:
            raise ValueError("keyword 不能为空")
        return [ToolAuthorization("read", str(self._root(arguments)))]

    def execute(self, arguments: dict[str, Any]) -> ToolResult:
        root = self._root(arguments)
        keyword = str(arguments["keyword"]).strip().casefold()
        limit = min(200, max(1, int(arguments.get("limit", 50))))
        if not root.is_dir():
            return ToolResult(False, f"搜索目录不存在：{root}")
        ignored = {".venv", "__pycache__", ".git", ".personal_agent"}
        matches: list[str] = []
        for current_root, directories, files in os.walk(root):
            directories[:] = [
                item for item in directories if item not in ignored
            ]
            for filename in files:
                if keyword in filename.casefold():
                    matches.append(str(Path(current_root, filename)))
                    if len(matches) >= limit:
                        break
            if len(matches) >= limit:
                break
        return ToolResult(
            True,
            "\n".join(matches) if matches else "未找到匹配文件。",
            {"matches": matches, "root": str(root)},
        )


@dataclass
class CreateFileTool:
    name: str = "create_file"
    description: str = "在授权工作区创建新 UTF-8 文本文件，不覆盖已有文件"
    required_permission: str = "write"
    input_schema: Mapping[str, object] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.input_schema = {"path": "string", "content": "string"}

    def authorizations(self, arguments: dict[str, Any]) -> list[ToolAuthorization]:
        _content(arguments)
        return [ToolAuthorization("write", str(_path(arguments, "path")))]

    def execute(self, arguments: dict[str, Any]) -> ToolResult:
        path = _path(arguments, "path")
        if path.exists():
            return ToolResult(False, f"文件已存在，create_file 不会覆盖：{path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_content(arguments), encoding="utf-8")
        return ToolResult(True, f"已创建：{path}", {"path": str(path)})


@dataclass
class UpdateFileTool:
    versions_root: Path
    name: str = "update_file"
    description: str = "确认 diff 后更新文本文件，并保存旧版本"
    required_permission: str = "write"
    input_schema: Mapping[str, object] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.versions_root = self.versions_root.resolve()
        self.input_schema = {"path": "string", "content": "string"}

    @staticmethod
    def preview(path: str | Path, content: str) -> str:
        resolved = Path(path).resolve()
        old = resolved.read_text(encoding="utf-8")
        return "".join(
            difflib.unified_diff(
                old.splitlines(keepends=True),
                content.splitlines(keepends=True),
                fromfile=str(resolved),
                tofile=str(resolved),
            )
        )

    def preview_call(self, arguments: dict[str, Any]) -> ToolResult:
        path = _path(arguments, "path")
        if not path.is_file():
            return ToolResult(False, f"文件不存在：{path}")
        diff = self.preview(path, _content(arguments))
        return ToolResult(
            True,
            diff or "内容没有变化。",
            {"path": str(path)},
        )

    def authorizations(self, arguments: dict[str, Any]) -> list[ToolAuthorization]:
        _content(arguments)
        return [
            ToolAuthorization(
                "write",
                str(_path(arguments, "path")),
                requires_confirmation=True,
            )
        ]

    def execute(self, arguments: dict[str, Any]) -> ToolResult:
        path = _path(arguments, "path")
        if not path.is_file():
            return ToolResult(False, f"文件不存在：{path}")
        old = path.read_text(encoding="utf-8")
        new = _content(arguments)
        if old == new:
            return ToolResult(True, "文件内容没有变化。", {"path": str(path)})
        version_id = uuid4().hex
        backup = self.versions_root / version_id / path.name
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup)
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            delete=False,
        ) as stream:
            stream.write(new)
            temporary = Path(stream.name)
        os.replace(temporary, path)
        return ToolResult(
            True,
            f"已更新：{path}",
            {
                "path": str(path),
                "version_id": version_id,
                "backup": str(backup),
            },
        )


@dataclass
class DeleteFileTool:
    trash_root: Path
    name: str = "delete_file"
    description: str = "经确认后把文件移动到可恢复回收区"
    required_permission: str = "delete"
    input_schema: Mapping[str, object] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.trash_root = self.trash_root.resolve()
        self.input_schema = {"path": "string"}

    def authorizations(self, arguments: dict[str, Any]) -> list[ToolAuthorization]:
        return [
            ToolAuthorization(
                "delete",
                str(_path(arguments, "path")),
                requires_confirmation=True,
            )
        ]

    def execute(self, arguments: dict[str, Any]) -> ToolResult:
        path = _path(arguments, "path")
        if not path.is_file():
            return ToolResult(False, f"只支持回收普通文件：{path}")
        trash_id = uuid4().hex
        container = self.trash_root / trash_id
        container.mkdir(parents=True, exist_ok=False)
        trashed = container / path.name
        shutil.move(str(path), str(trashed))
        metadata = {
            "trash_id": trash_id,
            "original_path": str(path),
            "trashed_path": str(trashed),
            "deleted_at": datetime.now().astimezone().isoformat(),
        }
        (container / "metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return ToolResult(
            True,
            f"已移入回收区：{path}",
            metadata,
        )


@dataclass
class RestoreFileTool:
    trash_root: Path
    name: str = "restore_file"
    description: str = "经确认后从工具回收区恢复文件"
    required_permission: str = "write"
    input_schema: Mapping[str, object] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.trash_root = self.trash_root.resolve()
        self.input_schema = {"trash_id": "string"}

    def _metadata(self, arguments: dict[str, Any]) -> dict[str, str]:
        trash_id = str(arguments.get("trash_id", "")).strip()
        if not re.fullmatch(r"[0-9a-f]{32}", trash_id):
            raise ValueError("trash_id 无效")
        metadata_path = self.trash_root / trash_id / "metadata.json"
        data = json.loads(metadata_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("回收元数据损坏")
        return {str(key): str(value) for key, value in data.items()}

    def authorizations(self, arguments: dict[str, Any]) -> list[ToolAuthorization]:
        metadata = self._metadata(arguments)
        return [
            ToolAuthorization(
                "write",
                metadata["original_path"],
                requires_confirmation=True,
            )
        ]

    def execute(self, arguments: dict[str, Any]) -> ToolResult:
        metadata = self._metadata(arguments)
        original = Path(metadata["original_path"])
        trashed = Path(metadata["trashed_path"])
        if original.exists():
            return ToolResult(False, f"原路径已存在，拒绝覆盖：{original}")
        if not trashed.is_file():
            return ToolResult(False, "回收区文件不存在")
        original.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(trashed), str(original))
        return ToolResult(
            True,
            f"已恢复：{original}",
            {"path": str(original), "trash_id": metadata["trash_id"]},
        )


@dataclass
class ConvertFileTool:
    name: str = "convert_file"
    description: str = "转换 txt、md 和 html 文本格式，不覆盖已有目标"
    required_permission: str = "read+write"
    input_schema: Mapping[str, object] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.input_schema = {"source": "string", "target": "string"}

    def authorizations(self, arguments: dict[str, Any]) -> list[ToolAuthorization]:
        return [
            ToolAuthorization("read", str(_path(arguments, "source"))),
            ToolAuthorization("write", str(_path(arguments, "target"))),
        ]

    def execute(self, arguments: dict[str, Any]) -> ToolResult:
        source = _path(arguments, "source")
        target = _path(arguments, "target")
        if not source.is_file():
            return ToolResult(False, f"源文件不存在：{source}")
        if target.exists():
            return ToolResult(False, f"目标文件已存在，拒绝覆盖：{target}")
        source_suffix = source.suffix.casefold()
        target_suffix = target.suffix.casefold()
        if source_suffix not in {".txt", ".md"}:
            return ToolResult(False, "当前源格式只支持 .txt 和 .md")
        text = source.read_text(encoding="utf-8")
        if target_suffix in {".txt", ".md"}:
            converted = (
                self._markdown_to_text(text)
                if source_suffix == ".md" and target_suffix == ".txt"
                else text
            )
        elif target_suffix == ".html":
            converted = self._to_html(text, source_suffix == ".md")
        else:
            return ToolResult(
                False,
                "当前目标格式只支持 .txt、.md 和 .html；PDF/DOCX 需要后续转换适配器",
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(converted, encoding="utf-8")
        return ToolResult(
            True,
            f"已转换：{source} → {target}",
            {"source": str(source), "target": str(target)},
        )

    @staticmethod
    def _markdown_to_text(value: str) -> str:
        value = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", value)
        value = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", value)
        value = re.sub(r"^\s{0,3}#{1,6}\s*", "", value, flags=re.MULTILINE)
        return re.sub(r"[*_`>~-]", "", value)

    @staticmethod
    def _to_html(value: str, markdown: bool) -> str:
        escaped = html.escape(value)
        if markdown:
            escaped = re.sub(
                r"^#{1}\s+(.+)$",
                r"<h1>\1</h1>",
                escaped,
                flags=re.MULTILINE,
            )
            escaped = re.sub(
                r"^#{2}\s+(.+)$",
                r"<h2>\1</h2>",
                escaped,
                flags=re.MULTILINE,
            )
        paragraphs = "\n".join(
            line if line.startswith("<h") else f"<p>{line}</p>"
            for line in escaped.splitlines()
            if line.strip()
        )
        return (
            "<!doctype html><html><head><meta charset=\"utf-8\"></head>"
            f"<body>{paragraphs}</body></html>"
        )


def register_file_tools(
    registry: Any,
    workspace_root: str | Path,
    state_root: str | Path,
) -> None:
    workspace = Path(workspace_root).resolve()
    state = Path(state_root).resolve()
    for tool in (
        ReadFileTool(),
        SearchFileTool(workspace),
        CreateFileTool(),
        UpdateFileTool(state / "versions"),
        DeleteFileTool(state / "trash"),
        RestoreFileTool(state / "trash"),
        ConvertFileTool(),
    ):
        registry.register(tool)
