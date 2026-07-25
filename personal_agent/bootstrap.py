from __future__ import annotations

from pathlib import Path

from personal_agent.agent import (
    AgentOrchestrator,
    CLIReviewer,
    Executor,
    JsonTaskStateStore,
    Planner,
    PlanningContextProvider,
    RiskAnalyzer,
)
from personal_agent.analysis import DailyAnalysisService, WeeklyReviewService
from personal_agent.application import WorkflowScheduler
from personal_agent.config import get_config
from personal_agent.core import Agent, ContextBuilder
from personal_agent.core.clock import local_now
from personal_agent.core.tool_runner import ChatToolRunner
from personal_agent.interfaces.channel import LocalChannel
from personal_agent.interfaces.cli import LocalCLI
from personal_agent.llm import create_llm_client
from personal_agent.memory import (
    DatabaseBackupManager,
    DailyMemoryAnalyzer,
    MemoryManager,
    SQLiteAgentRepository,
)
from personal_agent.memory import database
from personal_agent.memory.retriever import MemoryRetriever
from personal_agent.memory.candidate import CandidateMemoryService
from personal_agent.memory.conflict import MemoryConflictDetector
from personal_agent.memory.lifecycle import MemoryLifecycleManager
from personal_agent.security import JsonlAuditSink, ScopedPermissionManager
from personal_agent.tools import ToolManager, ToolRegistry
from personal_agent.tools import ToolCall
from personal_agent.tools.app_tool import register_app_tools
from personal_agent.tools.file_tool import register_file_tools


def create_application() -> LocalCLI:
    """Composition root: the only place that selects concrete implementations."""
    config = get_config()
    repository = SQLiteAgentRepository()
    memory = MemoryManager(
        repository,
        MemoryRetriever(repository),
    )
    llm = create_llm_client(config)
    context_builder = ContextBuilder()
    backup_manager = DatabaseBackupManager(
        database.DB_PATH,
        Path(__file__).resolve().parents[1] / "data" / "backups",
    )
    daily_analysis = DailyAnalysisService(
        repository,
        DailyMemoryAnalyzer(llm),
        backup_after_success=backup_manager.create_backup,
    )
    weekly_review = WeeklyReviewService(repository, llm)
    channel = LocalChannel()
    scheduler = WorkflowScheduler(
        repository=repository,
        daily_analysis=daily_analysis,
        weekly_review=weekly_review,
        channel=channel,
        backup_database=backup_manager.create_backup,
    )
    candidate_memories = CandidateMemoryService(
        repository,
        MemoryConflictDetector(),
    )
    memory_lifecycle = MemoryLifecycleManager(repository)
    workspace_root = Path(__file__).resolve().parents[1]
    tool_state_root = workspace_root / ".personal_agent"
    tool_registry = ToolRegistry()
    register_file_tools(tool_registry, workspace_root, tool_state_root)
    tool_permission = ScopedPermissionManager(workspace_root)
    tool_audit = JsonlAuditSink(tool_state_root / "audit" / "tool_audit.jsonl")
    tool_manager = ToolManager(
        tool_registry,
        tool_permission,
        tool_audit,
    )
    chat_tool_registry = ToolRegistry()
    register_app_tools(
        chat_tool_registry,
        repository,
        database.DB_PATH,
        local_now().date(),
    )
    chat_tool_manager = ToolManager(
        chat_tool_registry,
        tool_permission,
        tool_audit,
    )
    agent = Agent(
        memory=memory,
        llm=llm,
        context_builder=context_builder,
        tool_runner=ChatToolRunner(
            Planner(
                llm,
                chat_tool_registry,
                PlanningContextProvider(memory),
            ),
            chat_tool_manager,
        ),
    )
    task_state = JsonTaskStateStore(tool_state_root / "tasks")
    orchestrator = AgentOrchestrator(
        planner=Planner(
            llm,
            tool_registry,
            PlanningContextProvider(memory),
        ),
        risk=RiskAnalyzer(),
        reviewer=CLIReviewer(
            preview_fn=lambda step: (
                tool_manager.preview(
                    ToolCall(step.tool, step.arguments),
                    actor="agent",
                ).content
                if step.tool == "update_file"
                else None
            )
        ),
        executor=Executor(tool_manager),
        state=task_state,
    )
    return LocalCLI(
        agent=agent,
        repository=repository,
        daily_analysis=daily_analysis,
        weekly_review=weekly_review,
        scheduler=scheduler,
        candidate_memories=candidate_memories,
        memory_lifecycle=memory_lifecycle,
        tool_manager=tool_manager,
        tool_permission=tool_permission,
        tool_audit=tool_audit,
        orchestrator=orchestrator,
        task_state=task_state,
        backup_manager=backup_manager,
    )
