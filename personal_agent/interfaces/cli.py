from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path
import shlex

from personal_agent.agent import AgentOrchestrator, TaskStateStore
from personal_agent.analysis import DailyAnalysisService, WeeklyReviewService
from personal_agent.application import WorkflowScheduler
from personal_agent.config import get_config, save_runtime_config
from personal_agent.core.agent import Agent, week_start
from personal_agent.core.clock import local_now
from personal_agent.memory.repository import AgentRepository
from personal_agent.memory.backup import DatabaseBackupManager
from personal_agent.memory.candidate import (
    CandidateMemoryService,
    MemoryConflictError,
)
from personal_agent.memory.lifecycle import MemoryLifecycleManager
from personal_agent.security import JsonlAuditSink, ScopedPermissionManager
from personal_agent.tools import ToolCall, ToolManager

logger = logging.getLogger(__name__)


def build_help_message() -> str:
    return (
        "可用命令：\n"
        "- /goals：查看长期目标\n"
        "- /tasks：查看本周任务\n"
        "- /task-add [目标ID] [任务内容]：新增本周任务\n"
        "- /task-done [任务ID]：完成任务\n"
        "- /task-reopen [任务ID]：重新打开任务\n"
        "- /today：查看今天保留的原始聊天\n"
        "- /daily [日期]：查看最近或指定日期的每日分析\n"
        "- /memory candidates：查看待审核候选记忆\n"
        "- /memory accept ID：确认候选记忆\n"
        "- /memory edit ID [类型] [内容]：修改候选\n"
        "- /memory reject ID：拒绝候选\n"
        "- /memory list：查看正式记忆\n"
        "- /memory show ID：查看记忆来源与证据\n"
        "- /tool list：查看可用文件工具\n"
        "- /tool scopes：查看文件授权范围\n"
        "- /tool audit：查看最近工具操作\n"
        "- /tool help：查看工具命令\n"
        "- /agent run 任务：生成计划、审核并执行\n"
        "- /agent tasks：查看最近 Agent 任务\n"
        "- /weekly：生成本周报告\n"
        "- /settings [0-23]：查看或修改提醒时间\n"
        "- /help：查看帮助\n"
        "- /exit：退出\n\n"
        "直接输入文字即可与助手实时对话；原始消息在每日分析成功后删除。"
    )


class LocalCLI:
    """Console adapter. Business behavior is delegated to injected services."""

    def __init__(
        self,
        agent: Agent,
        repository: AgentRepository,
        daily_analysis: DailyAnalysisService,
        weekly_review: WeeklyReviewService,
        scheduler: WorkflowScheduler,
        candidate_memories: CandidateMemoryService,
        memory_lifecycle: MemoryLifecycleManager,
        tool_manager: ToolManager | None = None,
        tool_permission: ScopedPermissionManager | None = None,
        tool_audit: JsonlAuditSink | None = None,
        orchestrator: AgentOrchestrator | None = None,
        task_state: TaskStateStore | None = None,
        backup_manager: DatabaseBackupManager | None = None,
    ) -> None:
        self.agent = agent
        self.repository = repository
        self.daily_analysis = daily_analysis
        self.weekly_review = weekly_review
        self.scheduler = scheduler
        self.candidate_memories = candidate_memories
        self.memory_lifecycle = memory_lifecycle
        self.tool_manager = tool_manager
        self.tool_permission = tool_permission
        self.tool_audit = tool_audit
        self.orchestrator = orchestrator
        self.task_state = task_state
        self.backup_manager = backup_manager

    def run(self) -> None:
        self.repository.initialize()
        self.scheduler.run_startup_catchup()
        settings = self.repository.settings()
        if not settings.get("setup_complete") or not self.repository.active_goals():
            reminder_hour = self._initial_setup()
        else:
            reminder_hour = int(
                settings.get("reminder_hour") or get_config().default_ask_hour
            )

        self.scheduler.configure(reminder_hour)
        self.scheduler.start()
        print("本地个人 Agent 已启动。输入 /help 查看命令，输入 /exit 退出。")
        try:
            while True:
                try:
                    user_input = input("你: ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("\n退出程序。")
                    break
                if not user_input:
                    continue
                if user_input.startswith("/"):
                    if not self.handle_command(user_input):
                        break
                    continue
                try:
                    print(f"助手: {self.agent.chat(user_input)}")
                except Exception as exc:
                    logger.exception("实时对话失败")
                    print(f"助手暂时无法回复：{exc}")
        finally:
            self.scheduler.stop()

    def handle_command(self, command: str) -> bool:
        command_name, _, argument = command.strip().partition(" ")
        normalized = command_name.lower().rstrip("/")

        if normalized in {"/goals", "goals"}:
            self._list_goals()
        elif normalized in {"/tasks", "tasks"}:
            self._list_tasks()
        elif normalized in {"/task-add", "task-add"}:
            self._add_task(argument)
        elif normalized in {"/task-done", "task-done"}:
            self._set_task(argument, True)
        elif normalized in {"/task-reopen", "task-reopen"}:
            self._set_task(argument, False)
        elif normalized in {"/today", "today"}:
            self._show_today()
        elif normalized in {"/daily", "daily"}:
            self._show_daily(argument)
        elif normalized in {"/memory", "memory"}:
            self._memory_command(argument)
        elif normalized in {"/tool", "tool"}:
            self._tool_command(argument)
        elif normalized in {"/agent", "agent"}:
            self._agent_command(argument)
        elif normalized in {"/weekly", "weekly"}:
            print("\n=== 本周复盘报告 ===")
            print(self.weekly_review.generate(week_start(local_now().date())))
        elif normalized in {"/settings", "settings"}:
            self._settings(argument)
        elif normalized in {"/help", "help"}:
            print(build_help_message())
        elif normalized in {"/exit", "exit"}:
            return False
        else:
            print("未知命令。输入 /help 查看可用命令。")
        return True

    def _initial_setup(self) -> int:
        print("开始初始化设置...")
        if not self.repository.active_goals():
            while True:
                raw = input("请输入长期目标，用逗号分隔：").strip()
                goals = [item.strip() for item in raw.split(",") if item.strip()]
                if goals:
                    for goal in goals:
                        self.repository.add_goal(goal)
                    break
                print("至少需要输入一个目标。")
        hour = self._prompt_hour("请输入每日提醒小时（0-23）：")
        save_runtime_config(hour)
        self.repository.save_settings(
            reminder_hour=hour,
            setup_complete=True,
        )
        print(f"初始化完成。每天 {hour:02d}:00 提醒。")
        return hour

    def _list_goals(self) -> None:
        goals = self.repository.active_goals()
        if not goals:
            print("当前还没有目标。")
            return
        print("当前目标：")
        for goal in goals:
            print(f"- [{goal['id']}] {goal['title']}")

    def _list_tasks(self) -> None:
        tasks = self.repository.tasks_for_week(week_start(local_now().date()))
        if not tasks:
            print("本周还没有任务。使用 /task-add 新增。")
            return
        print("本周任务：")
        for task in tasks:
            marker = "x" if task["completed"] else " "
            print(
                f"- [{marker}] #{task['id']} {task['description']}"
                f"（{task['goal_title']}）"
            )

    def _add_task(self, argument: str) -> None:
        if not self.repository.active_goals():
            print("请先设置长期目标。")
            return
        parts = argument.strip().split(maxsplit=1)
        if len(parts) == 2:
            goal_text, description = parts
        else:
            self._list_goals()
            goal_text = input("目标 ID：").strip()
            description = input("任务内容：").strip()
        try:
            task_id = self.repository.add_task(
                int(goal_text),
                description,
                week_start(local_now().date()),
            )
        except ValueError as exc:
            print(f"新增失败：{exc}")
            return
        print(f"已新增任务 #{task_id}。")

    def _set_task(self, argument: str, completed: bool) -> None:
        try:
            task_id = int(argument.strip())
        except ValueError:
            print("请提供有效任务 ID，例如 /task-done 3")
            return
        if self.repository.set_task_completed(task_id, completed):
            state = "已完成" if completed else "已重新打开"
            print(f"任务 #{task_id} {state}。")
        else:
            print(f"没有找到任务 #{task_id}。")

    def _show_today(self) -> None:
        today = local_now().date()
        messages = self.repository.messages_for_date(today)
        if not messages:
            print("今天还没有聊天记录。")
            return
        print(f"=== {today.isoformat()} 今日聊天 ===")
        for message in messages:
            speaker = "你" if message["role"] == "user" else "助手"
            print(f"{speaker}: {message['content']}")

    def _show_daily(self, argument: str) -> None:
        if argument.strip():
            try:
                analysis_date = date.fromisoformat(argument.strip())
            except ValueError:
                print("日期格式应为 YYYY-MM-DD，例如 /daily 2026-07-23")
                return
        else:
            analysis_date = local_now().date() - timedelta(days=1)
        report = self.daily_analysis.formatted_analysis(analysis_date)
        if report is None:
            print(f"{analysis_date.isoformat()} 暂无每日分析。")
            return
        print("\n=== 每日分析 ===")
        print(report)

    def _memory_command(self, argument: str) -> None:
        parts = argument.strip().split(maxsplit=3)
        action = parts[0].lower() if parts else "help"

        if action in {"candidates", "pending"}:
            candidates = self.candidate_memories.pending()
            if not candidates:
                print("当前没有待审核候选记忆。")
                return
            print("=== 待审核候选记忆 ===")
            for item in candidates:
                print(
                    f"#{item['id']} [{item['type']}] {item['content']}\n"
                    f"  置信度: {float(item['confidence']):.2f}  "
                    f"重要度: {float(item['importance']):.2f}  "
                    f"来源日期: {item.get('source_date') or '未知'}\n"
                    f"  创建原因: {item.get('created_reason') or '未记录'}"
                )
            return

        if action == "list":
            memories = self.memory_lifecycle.list("active")
            if not memories:
                print("当前没有正式长期记忆。")
                return
            print("=== 正式长期记忆 ===")
            for item in memories:
                print(
                    f"#{item['id']} [{item['type']}] {item['content']} "
                    f"(重要度 {float(item['importance']):.2f}, "
                    f"置信度 {float(item['confidence']):.2f})"
                )
            return

        if action == "show":
            if len(parts) < 2:
                print("请提供 ID，例如 /memory show 1")
                return
            try:
                memory_id = int(parts[1])
            except ValueError:
                print("ID 必须是整数。")
                return
            memory = next(
                (
                    item
                    for status in ("active", "archived", "expired", "deleted")
                    for item in self.repository.memories(status)
                    if int(item["id"]) == memory_id
                ),
                None,
            )
            if memory is None:
                print(f"没有找到正式记忆 #{memory_id}。")
                return
            print(
                f"=== 正式记忆 #{memory_id} ===\n"
                f"[{memory['type']}] {memory['content']}\n"
                f"状态：{memory['status']}"
            )
            sources = self.repository.memory_provenance(memory_id)
            if not sources:
                print("来源：旧版本记忆，未记录结构化来源。")
                return
            for source in sources:
                print(
                    f"来源：{source['source_type']} #{source.get('source_id')}\n"
                    f"原因：{source['created_reason']}"
                )
                evidence = source.get("evidence")
                if isinstance(evidence, list):
                    for item in evidence:
                        print(
                            f"- 消息 #{item['message_id']} "
                            f"{item['message_created_at']}\n"
                            f"  {item['quote']}"
                        )
            return

        if action in {"accept", "reject", "edit", "archive", "expire", "delete"}:
            if len(parts) < 2:
                print(f"请提供 ID，例如 /memory {action} 1")
                return
            try:
                item_id = int(parts[1])
            except ValueError:
                print("ID 必须是整数。")
                return

            if action == "accept":
                force = len(parts) >= 3 and parts[2].lower() == "force"
                try:
                    memory_id = self.candidate_memories.accept(
                        item_id,
                        force=force,
                    )
                    print(f"候选 #{item_id} 已保存为正式记忆 #{memory_id}。")
                except MemoryConflictError as exc:
                    print("检测到可能冲突，未自动保存：")
                    for conflict in exc.conflicts:
                        print(
                            f"- 现有 #{conflict.old_memory_id}: "
                            f"{conflict.old_content}\n"
                            f"  新候选: {conflict.new_content}\n"
                            f"  原因: {conflict.reason}"
                        )
                    print(f"确认仍需保存时使用 /memory accept {item_id} force")
                except ValueError as exc:
                    print(str(exc))
                return

            if action == "reject":
                print(
                    "候选已拒绝。"
                    if self.candidate_memories.reject(item_id)
                    else "候选不存在或已处理。"
                )
                return

            if action == "edit":
                if len(parts) >= 4:
                    memory_type, content = parts[2], parts[3]
                else:
                    memory_type = input(
                        "新类型（profile/preference/goal/project/skill/experience）："
                    ).strip()
                    content = input("新内容：").strip()
                try:
                    updated = self.candidate_memories.edit(
                        item_id,
                        memory_type=memory_type,
                        content=content,
                    )
                    print("候选已修改。" if updated else "候选不存在或已处理。")
                except ValueError as exc:
                    print(f"修改失败：{exc}")
                return

            lifecycle_action = {
                "archive": self.memory_lifecycle.archive,
                "expire": self.memory_lifecycle.expire,
                "delete": self.memory_lifecycle.delete,
            }[action]
            print(
                f"正式记忆 #{item_id} 状态已更新。"
                if lifecycle_action(item_id)
                else f"没有找到正式记忆 #{item_id}。"
            )
            return

        print(
            "Memory 命令：\n"
            "/memory candidates\n"
            "/memory accept ID [force]\n"
            "/memory edit ID [类型] [内容]\n"
            "/memory reject ID\n"
            "/memory list\n"
            "/memory show ID\n"
            "/memory archive|expire|delete ID"
        )

    def _tool_command(self, argument: str) -> None:
        if (
            self.tool_manager is None
            or self.tool_permission is None
            or self.tool_audit is None
        ):
            print("工具系统未配置。")
            return
        try:
            parts = shlex.split(argument, posix=False)
        except ValueError as exc:
            print(f"命令格式错误：{exc}")
            return
        parts = [self._unquote_cli_token(item) for item in parts]
        action = parts[0].lower() if parts else "help"

        if action == "list":
            print("=== 可用工具 ===")
            for item in self.tool_manager.registry.descriptions():
                print(
                    f"- {item['name']} [{item['required_permission']}]："
                    f"{item['description']}"
                )
            return

        if action == "scopes":
            print("=== 已授权文件范围 ===")
            for scope in self.tool_permission.scopes():
                print(
                    f"- {scope.name}: {scope.root} "
                    f"({', '.join(sorted(scope.actions))})"
                )
            return

        if action == "grant-read":
            if len(parts) < 3:
                print("/tool grant-read 范围名 路径")
                return
            self.tool_permission.grant(parts[1], Path(parts[2]), {"read"})
            print(f"已授权只读范围 {parts[1]}：{Path(parts[2]).resolve()}")
            return

        if action == "revoke":
            if len(parts) < 2:
                print("/tool revoke 范围名")
                return
            print(
                "授权已撤销。"
                if self.tool_permission.revoke(parts[1])
                else "范围不存在，或属于不可撤销的基础范围。"
            )
            return

        if action == "audit":
            events = self.tool_audit.recent(20)
            if not events:
                print("还没有工具审计记录。")
                return
            print("=== 最近工具操作 ===")
            for event in events:
                print(
                    f"- {event.get('time')} {event.get('tool')} "
                    f"{event.get('action')} {event.get('result')}\n"
                    f"  {event.get('target')}"
                )
            return

        tool_name = {
            "read": "read_file",
            "search": "search_file",
            "create": "create_file",
            "update": "update_file",
            "delete": "delete_file",
            "restore": "restore_file",
            "convert": "convert_file",
        }.get(action)
        if tool_name is None:
            self._show_tool_help()
            return

        try:
            call, requires_prompt = self._build_tool_call(action, parts[1:])
        except (ValueError, OSError) as exc:
            print(f"工具参数错误：{exc}")
            return

        confirmed = False
        if requires_prompt:
            if action == "update":
                preview = self.tool_manager.preview(call, actor="user")
                if not preview.success:
                    print(preview.content)
                    return
                print("=== 修改预览 ===")
                print(preview.content)
            answer = input("确认执行？请输入 yes：").strip().casefold()
            if answer != "yes":
                print("已取消，未执行。")
                return
            confirmed = True
        result = self.tool_manager.execute(
            call,
            actor="user",
            user_confirmed=confirmed,
        )
        print(result.content)
        if result.metadata.get("trash_id"):
            print(f"恢复 ID：{result.metadata['trash_id']}")

    def _agent_command(self, argument: str) -> None:
        if self.orchestrator is None or self.task_state is None:
            print("Agent Orchestrator 未配置。")
            return
        action, _, value = argument.strip().partition(" ")
        action = action.casefold() or "help"
        if action == "run":
            if not value.strip():
                print("/agent run 任务描述")
                return
            try:
                result = self.orchestrator.run(value.strip())
            except Exception as exc:
                logger.exception("Agent 计划或执行失败")
                print(f"Agent 无法启动任务：{exc}")
                return
            print(f"{result.message}\n任务 ID：{result.task_id}")
            for step in result.plan.steps:
                result_text = (
                    str(step.result.get("content", ""))
                    if step.result
                    else "未执行"
                )
                print(
                    f"- 步骤 {step.id} [{step.status}] {step.description}\n"
                    f"  {result_text[:500]}"
                )
            return
        if action == "tasks":
            plans = self.task_state.list(20)
            if not plans:
                print("还没有 Agent 任务记录。")
                return
            print("=== 最近 Agent 任务 ===")
            for plan in plans:
                print(
                    f"- {plan.task_id} [{plan.status}] {plan.goal} "
                    f"({plan.updated_at})"
                )
            return
        if action == "show":
            if not value.strip():
                print("/agent show 任务ID")
                return
            try:
                plan = self.task_state.load(value.strip())
            except ValueError as exc:
                print(str(exc))
                return
            if plan is None:
                print("没有找到该任务。")
                return
            print(
                f"任务：{plan.goal}\n"
                f"ID：{plan.task_id}\n"
                f"状态：{plan.status}\n"
                f"当前步骤：{plan.current_step or '-'}"
            )
            for step in plan.steps:
                print(
                    f"- {step.id} [{step.status}] {step.description} "
                    f"(风险 {step.risk}/10)"
                )
            return
        print(
            "Agent 命令：\n"
            "/agent run 任务描述\n"
            "/agent tasks\n"
            "/agent show 任务ID"
        )

    @staticmethod
    def _unquote_cli_token(value: str) -> str:
        if (
            len(value) >= 2
            and value[0] == value[-1]
            and value[0] in {'"', "'"}
        ):
            return value[1:-1]
        return value

    @staticmethod
    def _build_tool_call(
        action: str,
        arguments: list[str],
    ) -> tuple[ToolCall, bool]:
        if action == "read":
            if not arguments:
                raise ValueError("/tool read 路径")
            return ToolCall("read_file", {"path": arguments[0]}), False
        if action == "search":
            if not arguments:
                raise ValueError("/tool search 关键词 [目录]")
            values: dict[str, object] = {"keyword": arguments[0]}
            if len(arguments) >= 2:
                values["root"] = arguments[1]
            return ToolCall("search_file", values), False
        if action in {"create", "update"}:
            if not arguments:
                raise ValueError(f"/tool {action} 路径 [内容]")
            content = (
                " ".join(arguments[1:])
                if len(arguments) >= 2
                else input("文件内容：")
            )
            return (
                ToolCall(
                    f"{action}_file",
                    {"path": arguments[0], "content": content},
                ),
                action == "update",
            )
        if action == "delete":
            if not arguments:
                raise ValueError("/tool delete 路径")
            return ToolCall("delete_file", {"path": arguments[0]}), True
        if action == "restore":
            if not arguments:
                raise ValueError("/tool restore 恢复ID")
            return ToolCall("restore_file", {"trash_id": arguments[0]}), True
        if action == "convert":
            if len(arguments) < 2:
                raise ValueError("/tool convert 源路径 目标路径")
            return (
                ToolCall(
                    "convert_file",
                    {"source": arguments[0], "target": arguments[1]},
                ),
                False,
            )
        raise ValueError("未知工具操作")

    @staticmethod
    def _show_tool_help() -> None:
        print(
            "Tool 命令（包含空格的路径请加引号）：\n"
            "/tool list\n"
            "/tool scopes\n"
            "/tool grant-read 范围名 外部目录\n"
            "/tool revoke 范围名\n"
            "/tool read 路径\n"
            "/tool search 关键词 [目录]\n"
            "/tool create 路径 [内容]\n"
            "/tool update 路径 [新内容]\n"
            "/tool delete 路径\n"
            "/tool restore 恢复ID\n"
            "/tool convert 源路径 目标路径\n"
            "/tool audit"
        )

    def _settings(self, argument: str) -> None:
        if not argument:
            print(f"当前提醒时间：{self.repository.settings().get('reminder_hour')} 点")
            argument = input("输入新的提醒小时，或回车取消：").strip()
        if not argument:
            return
        try:
            hour = int(argument)
            if not 0 <= hour <= 23:
                raise ValueError
        except ValueError:
            print("提醒时间必须是 0-23 之间的整数。")
            return
        save_runtime_config(hour)
        self.repository.save_settings(reminder_hour=hour)
        self.scheduler.configure(hour)
        print(f"提醒时间已更新为 {hour:02d}:00，调度已立即生效。")

    @staticmethod
    def _prompt_hour(prompt: str) -> int:
        while True:
            raw = input(prompt).strip()
            try:
                hour = int(raw)
            except ValueError:
                print("请输入一个 0-23 之间的整数。")
                continue
            if 0 <= hour <= 23:
                return hour
            print("请输入一个 0-23 之间的整数。")
