# Personal Agent 分层架构说明

## 目标

本架构的首要目标是让核心业务依赖抽象能力，而不是依赖 Ollama、SQLite、命令行或未来的具体工具。

核心原则：

```text
核心逻辑不知道具体模型。
核心逻辑不知道具体数据库。
分析逻辑不知道终端界面。
工具实现不自行决定权限。
具体实现只在 bootstrap.py 中组装。
```

## 当前目录

```text
personal_agent/
├── bootstrap.py
├── agent/
│   ├── context.py
│   ├── orchestrator.py
│   ├── planner.py
│   ├── executor.py
│   ├── reviewer.py
│   ├── state.py
│   ├── task.py
│   ├── risk.py
│   └── prompt.py
├── application/
│   └── workflow.py
├── core/
│   ├── agent.py
│   ├── context.py
│   ├── ports.py
│   └── clock.py
├── llm/
│   ├── base.py
│   ├── factory.py
│   ├── ollama.py
│   ├── openai_compatible.py
│   ├── generic_http.py
│   └── mock.py
├── memory/
│   ├── analyzer.py
│   ├── backup.py
│   ├── candidate.py
│   ├── conflict.py
│   ├── lifecycle.py
│   ├── manager.py
│   ├── models.py
│   ├── repository.py
│   ├── retriever.py
│   ├── migrations/
│   │   ├── 001_initial.sql
│   │   └── manager.py
│   └── database.py
├── analysis/
│   ├── daily.py
│   └── weekly.py
├── interfaces/
│   ├── cli.py
│   └── channel.py
├── tools/
│   ├── base.py
│   ├── file_tool.py
│   ├── manager.py
│   └── registry.py
├── security/
│   ├── permission.py
│   └── audit.py
└── config/
    └── settings.py
```

正式源码只位于 `personal_agent/`，入口是
`personal_agent/__main__.py`。迁移前的根目录兼容门面已移入
`legacy/`，新代码和测试禁止依赖它们。

## 分层职责

### agent

有限、可审核的任务调度层。

- `Planner` 只从已注册工具生成最多 8 步 JSON 计划。
- `RiskAnalyzer` 使用本地规则覆盖模型风险。
- `PlanReviewer` 隔离 CLI 与未来 Web 审核界面。
- `Executor` 只通过 ToolManager 执行。
- `AgentOrchestrator` 保存状态、顺序执行并在首次失败停止。
- 不自动重规划、不提升权限、不引入无限循环。

完整规则见 `orchestrator.md`。

### core

纯核心层。

- `Agent` 协调一次聊天。
- `ContextBuilder` 纯粹组装模型提示词。
- `ConversationMemory` 定义核心所需的记忆能力。
- 不允许导入 SQLite、Ollama、配置或 CLI。

### llm

模型适配层。

所有模型统一实现：

```python
complete(prompt: str, json_mode: bool = False) -> str
```

更换模型只需要新增客户端并修改 `factory.py`，不修改 `Agent`。

### memory

记忆与持久化层。

- `MemoryManager` 向核心提供会话记忆。
- `DailyMemoryAnalyzer` 从每日聊天生成日报和待审核候选。
- 日报事实在删除聊天前校验并保存最小 Evidence。
- `CandidateMemoryService` 管理用户审核，模型不能直接写入正式记忆。
- `MemoryConflictDetector` 在接受候选前提示潜在冲突。
- `MemoryRetriever` 只检索用户确认的活跃记忆。
- `MemoryLifecycleManager` 管理归档、过期和软删除。
- 候选接受时将日报来源、创建原因和 Evidence 继承到正式记忆。
- `AgentRepository` 是业务使用的持久化边界。
- `SQLiteAgentRepository` 是当前实现。
- `database.py` 只负责 SQL 和事务。
- `migrations/` 按版本原子升级 SQLite schema，失败时回滚当前版本。
- `backup.py` 使用 SQLite 在线备份接口生成、校验和恢复本地备份。

未来增加向量数据库时，实现 `MemorySearchBackend` 即可，不应修改
`Agent`、候选审核或正式记忆的用户控制规则。完整说明见
`memory.md`。

### analysis

独立分析用例。

- 日报读取过期聊天，通过 Memory Analyzer 生成日报和候选记忆，并在
  两者成功落库后原子清理原始消息。
- 周报只读取持久化的每日分析和任务。
- 不依赖具体模型提供商或 CLI。

### application

应用工作流。

- 注册定时任务。
- 调用日报和周报用例。
- 记录运行失败。
- 不负责 SQL 或模型请求。

### interfaces

用户接口层。

- 读取命令行输入。
- 显示结果。
- 将业务操作委托给 Agent、分析服务和仓储。

未来增加桌面界面时，可复用同一套核心和服务。

### tools

受控的本地工具能力。

- `Tool` 描述名称、用途、输入 Schema、所需权限和执行接口。
- `ToolRegistry` 只注册工具，不判断权限。
- `ToolManager` 是查找、授权、执行和审计的唯一入口。
- `file_tool.py` 提供读取、搜索、创建、差异更新、回收、恢复和格式转换。

LLM 当前不会自动调用工具，用户只能通过 CLI 显式操作。完整规则见
`tools.md`。

### security

权限和审计边界。

- `PermissionChecker` 在每个工具操作前检查动作、路径范围和用户确认。
- `ScopedPermissionManager` 默认只授权工作区，外部范围需用户显式授予。
- `DenyByDefaultPermissionChecker` 仍作为未配置场景的安全默认实现。
- `JsonlAuditSink` 记录允许、拒绝和执行结果。

## 依赖方向

```text
main
  ↓
bootstrap
  ↓
interfaces / application
  ↓
agent / core / analysis
  ↓
LLM接口 / Memory接口
  ↓
Ollama / SQLite
```

禁止：

```text
core → Ollama
core → SQLite
core → CLI
analysis → Ollama
analysis → SQLite SQL
memory → conversation
```

## 组合根

`personal_agent/bootstrap.py` 是唯一选择具体实现的位置：

```text
AppConfig
    ↓
OllamaClient

SQLiteAgentRepository
    ↓
MemoryManager

MemoryManager + LLMClient + ContextBuilder
    ↓
Agent
```

测试可以注入内存 SQLite 和 Fake LLM，不需要启动 Ollama，也不会触碰真实数据库。

## 架构保护测试

`tests/unit/test_architecture.py` 会检查：

- core 不导入具体数据库、模型、配置或 CLI。
- analysis 不导入具体 Ollama 或 SQLite 实现。
- 工具注册表初始为空。
- 权限系统默认拒绝未配置操作。

项目现在以 pytest 作为统一入口。`tests/` 按 unit、module、integration、
behavior、security 和 scenario 标记组织，同时继续收集原有 unittest
回归测试。

后续每次重构都应运行：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

完整结果和已知缺口见 `test_report.md`。

## 扩展指南

### 新增模型

1. 在 `llm/` 新增实现。
2. 实现 `complete()`。
3. 在 `factory.py` 注册。
4. 不修改 `Agent`。

### 新增记忆后端

1. 实现 `AgentRepository`。
2. 在 `bootstrap.py` 替换具体仓储。
3. 不修改 `Agent` 和日报服务。

### 新增工具

1. 实现 `Tool`。
2. 声明 `required_permission`。
3. 注册到 `ToolRegistry`。
4. 在执行前调用 `PermissionChecker`。
5. 通过 `AuditSink` 记录结果。

### 新增界面

1. 在 `interfaces/` 新增适配器。
2. 注入现有 Agent 和服务。
3. 不复制聊天、记忆或分析逻辑。
