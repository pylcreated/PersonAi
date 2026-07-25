# Personal Agent 项目完整文档

最后更新：2026-07-25

本文档是当前项目的统一说明，整合了项目报告、架构、Web UI、Memory、
Tool、Orchestrator、测试和运维文档中的有效内容。分专题文档仍保留，用于
查阅更细的设计背景和历史变更。

## 1. 项目概述

Personal Agent 是一个本地、单用户、隐私优先的个人 AI 助手。项目围绕
实时对话、目标、任务、日报、回顾和长期记忆建立连续闭环，并允许模型通过
受控 Tool 执行真实的数据操作。

当前运行形态：

| 项目 | 当前配置 |
| --- | --- |
| 平台 | Windows 本地 |
| 用户模式 | 单用户 |
| 界面 | Web UI + CLI |
| Web 地址 | `http://127.0.0.1:8765` |
| 默认模型 | Ollama `gemma3:12b` |
| 数据库 | 本地 SQLite |
| API 版本 | 7 |
| 自动化测试 | 93 passed |

核心原则：

- 本地优先、隐私优先。
- 核心业务不绑定具体模型、数据库或界面。
- 模型不能绕过 ToolManager、Permission 和审计。
- 模型不能直接写入正式长期记忆。
- 日报未可靠保存前不得删除原始聊天。
- 长期保留的结论应能追溯到真实 Evidence。
- 本地配置、数据库、备份和运行状态不进入 Git。

## 2. 功能总览

### 2.1 实时对话

用户可以通过 Web UI 或 CLI 与本地模型对话。系统保存当天消息，并在每次
回复前加载：

- 当天最近聊天。
- 活跃长期目标。
- 今天和本周任务。
- 近期日报。
- 与当前问题相关的已确认长期记忆。

模型不可用、响应格式异常或 Tool 计划失败时，系统返回明确错误，不会用
普通文本伪装成已经完成的数据操作。

### 2.2 目标与任务

长期目标用于保持方向；任务清单独立管理具体行动。

任务分为：

- 今天任务：只安排给当前日期。
- 本周任务：属于当前自然周。
- 目标任务：通过聊天 Tool 添加到指定长期目标下的本周任务。

用户可以在 Web UI 中创建目标和任务、查看清单、标记完成或重新打开。

### 2.3 日报与周回顾

次日分析服务会将前一天聊天转化为结构化日报，包括：

- 摘要。
- 关键进展。
- 行为或思考模式。
- 情绪状态。
- 下一步行动。
- 整体可信度。
- 支持结论的最小 Evidence。

周回顾读取本周任务和每日分析，通过本地模型生成总结。周回顾不依赖仍未
清理的原始聊天。

### 2.4 长期记忆

每日分析可以提出候选长期记忆。候选不会自动成为事实，必须由用户审核。

记忆流程：

```text
当天聊天
  ↓
次日结构化分析
  ├─ 每日摘要
  ├─ Evidence
  └─ 候选记忆
       ↓
用户确认或忽略
       ↓
正式长期记忆
       ↓
相关问题中按需检索
```

正式记忆的 Web 用户控制层遵循：

```text
UI → API → MemoryManagementService → AgentRepository → SQLite
```

用户可以筛选状态、查看来源与 Evidence、查看 JSON、编辑类型/内容/重要性/
状态，并通过现有生命周期执行软删除。候选审核、Provenance 和 Evidence
结构保持不变。

### 2.5 Tool 调用

系统提供文件 Tool 和应用 Tool：

- 文件 Tool：读取、搜索、创建、更新、回收、恢复和格式转换。
- 应用 Tool：查询目标、查询任务、创建目标、添加目标任务、修改任务状态。

普通聊天中的明确目标或任务操作由 `ChatToolRunner` 识别。模型只负责从
白名单生成计划，实际操作由 `ToolManager` 执行并审计。

## 3. 快速启动

### 3.1 前置条件

- Windows。
- 项目内 `.venv` Python 环境。
- 已安装并运行 Ollama。
- 已下载 `gemma3:12b`，或在 `.env` 中配置其他兼容模型。

安装 Python 依赖：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

检查 Ollama：

```powershell
ollama list
```

### 3.2 一键启动

依次双击项目根目录：

1. `启动项目.bat`
2. `打开UI界面.bat`

第一个脚本启动 Python 后端、SQLite、Agent 和 Web API。第二个脚本检查
服务状态，并打开：

```text
http://127.0.0.1:8765
```

如果后端尚未启动，第二个脚本会尝试自动启动并等待服务就绪。

### 3.3 手动启动

启动 Web UI 与 API：

```powershell
.\.venv\Scripts\python.exe -m personal_agent web
```

指定其他端口：

```powershell
.\.venv\Scripts\python.exe -m personal_agent web --port 9000
```

启动 CLI：

```powershell
.\.venv\Scripts\python.exe -m personal_agent
```

不要使用 `python -m http.server` 启动 UI。独立静态服务器不提供
`/api/*`，页面按钮和聊天将无法连接业务层。

## 4. Web UI 与 API

### 4.1 同源结构

Python Web 服务同时提供前端静态资源和 API：

```text
浏览器
  ├─ /、/app.js、/styles.css
  └─ /api/*
         ↓
Personal Agent 服务
  ├─ Agent / Tool
  ├─ Memory / Analysis
  ├─ SQLite
  └─ Ollama
```

前端使用同源相对路径 `/api/*`，不会在 JavaScript 中写死端口。

### 4.2 页面

| 页面 | 功能 |
| --- | --- |
| 今日 | 任务、进度、昨日回顾、记忆候选 |
| 对话 | 实时聊天、Tool 执行结果 |
| 目标与任务 | 长期目标、今天/本周任务清单 |
| 回顾 | 每日摘要、周回顾 |
| 记忆 | 候选审核、来源、已保存记忆 |
| 设置 | 模型、每日提醒、数据库备份 |

聊天输入支持：

- Enter 发送。
- Shift+Enter 换行。
- 用户消息靠右、AI 消息靠左。
- 进入对话页时自动定位到最新消息。

### 4.3 API

读取接口：

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/health` | 服务及 API 版本 |
| GET | `/api/dashboard` | UI 聚合数据 |
| GET | `/api/daily?date=YYYY-MM-DD` | 最近或指定日报 |
| GET | `/api/backups` | 备份列表 |
| GET | `/api/memory?status=...` | 查询正式记忆 |
| GET | `/api/memory/{id}` | 查看记忆来源和 Evidence |

操作接口：

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| POST | `/api/chat` | 对话 |
| POST | `/api/goals` | 新增目标 |
| POST | `/api/tasks` | 新增今天或本周任务 |
| POST | `/api/tasks/{id}` | 修改任务完成状态 |
| POST | `/api/weekly` | 生成周回顾 |
| POST | `/api/memory/analyze` | 补做聊天分析 |
| POST | `/api/memories/{id}/accept` | 保存候选记忆 |
| POST | `/api/memories/{id}/reject` | 忽略候选记忆 |
| PUT | `/api/memory/{id}` | 修改正式记忆 |
| DELETE | `/api/memory/{id}` | 软删除正式记忆 |
| POST | `/api/settings/model` | 保存模型名称 |
| POST | `/api/settings/reminder` | 修改提醒时间 |
| POST | `/api/backups` | 创建备份 |

响应使用 UTF-8 JSON。业务输入错误返回 `400`，未知路径返回 `404`，
服务内部异常返回 `500`。

## 5. 系统架构

### 5.1 分层

```text
__main__
  ↓
bootstrap
  ↓
interfaces (CLI / Web) + application
  ↓
agent + core + analysis
  ↓
LLM / Repository / Tool / Permission 抽象
  ↓
Ollama + SQLite + 本地文件系统
```

正式业务源码只位于 `personal_agent/`。历史兼容代码位于 `legacy/`，新代码
和测试不应依赖它。

### 5.2 模块职责

| 模块 | 职责 |
| --- | --- |
| `core` | 对话、上下文和聊天 Tool 路由 |
| `llm` | 模型统一接口与适配器 |
| `memory` | 对话、日报、Evidence、候选、正式记忆、迁移和备份 |
| `analysis` | 日报和周报用例 |
| `application` | 调度、重试和启动补偿 |
| `agent` | 有限计划、审核、风险、执行和状态 |
| `tools` | 文件/应用工具及统一执行 |
| `security` | 权限、范围、确认和审计 |
| `interfaces` | CLI、Web API 和静态 UI |
| `config` | 环境及运行配置 |

### 5.3 组合根

`personal_agent/bootstrap.py` 是选择具体实现的位置，负责组装：

- LLM 客户端。
- SQLite Repository。
- Memory 服务。
- 文件 ToolRegistry 和聊天应用 ToolRegistry。
- Permission 与 Audit。
- Agent、Orchestrator 和 WorkflowScheduler。
- CLI 使用的完整应用对象。

核心业务层不直接依赖 Ollama、SQLite SQL 或具体界面。

## 6. 数据与 Memory

### 6.1 本地数据

主要路径：

```text
data/database/goals_assistant.db
data/backups/
.personal_agent/
.env
```

这些目录或文件均被 Git 忽略。

### 6.2 Schema Migration

数据库通过 SQL migration 原子升级：

| 版本 | 内容 |
| --- | --- |
| `001_initial.sql` | 初始业务表 |
| `002_daily_evidence.sql` | 日报可信度和 Evidence |
| `003_memory_provenance.sql` | 候选及正式记忆来源 |
| `004_personal_task_list.sql` | 独立今天/本周任务清单 |

单个 migration 失败时回滚该版本，不登记为已完成。

### 6.3 日报事务

日报保存、Evidence 校验、候选保存和过期聊天清理位于同一个 SQLite
事务中。任何环节失败都会回滚，并保留原始聊天。

Evidence 必须：

- 指向对应日期的真实用户消息。
- 保存原消息 ID 和时间。
- `quote` 逐字包含在原用户消息中。
- 覆盖 `progress`、`obstacles` 和 `next_actions` 中的每项事实。

### 6.4 候选与正式记忆

候选状态：

- `pending`
- `accepted`
- `rejected`

正式记忆状态：

- `active`
- `expired`
- `archived`
- `deleted`

只有 `active` 记忆参与上下文检索。候选被接受时，来源日报、创建原因和
Evidence 会在同一事务中继承到正式记忆。

Web UI 支持查看、接受和拒绝候选，并展示已保存记忆。候选编辑、冲突强制
接受以及完整生命周期管理当前仍通过 CLI 完成。

### 6.5 检索

`MemoryRetriever` 先判断当前问题是否需要个人记忆，再按类型、关键词、
重要度、置信度和更新时间排序，最多向上下文注入 5 条活跃记忆。

当前检索使用关键词和启发式排序，不使用向量数据库。

## 7. Tool 与 Agent

### 7.1 ToolManager

统一执行链路：

```text
ToolCall
  ↓
ToolRegistry
  ↓
参数与授权要求
  ↓
Permission
  ↓
Tool.execute
  ↓
ToolResult
  ↓
Audit
```

工具实现本身不决定权限，任何工具都不能绕过 `ToolManager`。

### 7.2 文件 Tool

| 工具 | 能力 |
| --- | --- |
| `read_file` | 读取 UTF-8 文本 |
| `search_file` | 按文件名递归搜索 |
| `create_file` | 创建新文件 |
| `update_file` | 展示差异、备份后更新 |
| `delete_file` | 移动到内部回收区 |
| `restore_file` | 按恢复 ID 还原 |
| `convert_file` | 在 txt、md、html 之间转换 |

更新、回收和恢复需要逐次确认。工作区外默认拒绝；外部路径当前只支持临时
只读授权。

### 7.3 应用 Tool

| 工具 | 能力 |
| --- | --- |
| `list_goals` | 查询目标 |
| `list_tasks` | 查询任务 |
| `create_goal` | 创建目标 |
| `add_goal_task` | 向目标添加本周任务 |
| `set_task_completed` | 修改任务完成状态 |

聊天模型只能使用这五个应用 Tool，不能从普通聊天触发文件操作。

### 7.4 Orchestrator

文件任务使用有限 Orchestrator：

```text
用户请求
  ↓
Planner 生成最多 8 步计划
  ↓
RiskAnalyzer 本地风险覆盖
  ↓
用户审核
  ↓
Executor 通过 ToolManager 顺序执行
  ↓
状态保存
```

当前不自动重规划、不扩大已审核范围、不进行无限循环；任一步失败后停止。

## 8. 权限、安全与隐私

- 默认只授权项目工作区。
- `.personal_agent` 是内部保护区，普通 Tool 不能读写。
- 文件更新保存旧版本。
- 删除操作进入回收区，不直接物理删除。
- 允许、拒绝、参数错误和执行失败均写入 JSONL 审计。
- 审计不保存待写入文件的完整正文。
- SQLite 使用在线备份并校验完整性。
- 默认保留最近 30 份数据库备份。
- Web 服务默认只监听 `127.0.0.1`。

当前不具备：

- SQLite 文件加密。
- Web 登录、用户隔离和 HTTPS。
- 安全的公网部署配置。
- 完整结构化数据导出。
- 按日期彻底遗忘所有衍生数据。
- 操作系统级或异地备份。

## 9. 定时任务与备份

完成首次配置后，WorkflowScheduler 负责：

- 每日提醒。
- 次日聊天分析。
- 日报成功后的数据库备份。
- 固定兜底备份。

应用未运行时，进程内定时任务不会执行。下次启动会补做符合条件的未处理
聊天分析。

手动备份：

```powershell
.\.venv\Scripts\python.exe -m personal_agent backup
.\.venv\Scripts\python.exe -m personal_agent backups
```

恢复：

```powershell
.\.venv\Scripts\python.exe -m personal_agent restore 备份文件名.db
```

恢复只接受 `data/backups/` 中的 `.db` 文件，并要求输入 `RESTORE`。

## 10. 测试与验证

运行全部测试：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

当前结果：

```text
93 passed
0 failed
```

主要覆盖：

- Schema migration、升级、回滚和幂等。
- SQLite 在线备份、校验和恢复。
- 日报事务与 Evidence 原文校验。
- 候选记忆审核、冲突和来源继承。
- Memory 检索及上下文注入。
- 文件 Tool 权限、版本和回收。
- 应用 Tool 真实数据库副作用。
- 聊天 Tool 触发与失败保护。
- Planner 白名单、风险和用户拒绝。
- LLM 不可用和无效输出。
- 完整用户场景。

当前已对运行中的 `127.0.0.1:8765` 完成前后端实时联调，但 pytest 尚未
直接启动临时 HTTP 服务验证全部 API 状态码和响应 Schema。

健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8765/api/health
```

预期响应：

```json
{
  "ok": true,
  "service": "personal-agent",
  "api_version": 7
}
```

## 11. 项目目录

```text
PersonalAgent/
├── personal_agent/           # 正式业务源码
│   ├── agent/
│   ├── analysis/
│   ├── application/
│   ├── config/
│   ├── core/
│   ├── interfaces/
│   ├── llm/
│   ├── memory/
│   ├── security/
│   └── tools/
├── ui/                       # Web UI
├── tests/                    # 自动化测试
├── docs/                     # 当前文档与历史资料
├── data/                     # 本地数据库和备份
├── scripts/                  # 运维脚本
├── legacy/                   # 历史兼容代码
├── 启动项目.bat
├── 打开UI界面.bat
├── README.md
├── requirements.txt
└── .env.example
```

## 12. 当前边界与下一步

当前项目适合本地自用验证，但还不是成熟公网产品。

主要边界：

- Web 仅支持本机访问。
- 本地模型响应速度依赖设备性能。
- 没有流式输出。
- 超长单日聊天尚未分块分析。
- 跨午夜聊天与日报之间缺少完整会话锁。
- 真实模型输出质量缺少长期离线回归集。
- 缺少 HTTP API 自动化契约测试。
- 缺少长期并发、压力、磁盘故障测试。

推荐优先级：

1. 增加隔离数据库下的 HTTP API 集成测试。
2. 增加聊天与日报的跨午夜锁。
3. 为超长聊天增加分块分析。
4. 建立真实模型离线回归样本。
5. 持续进行 30 天本地使用验证。

## 13. 文档说明

本文档是当前项目的统一入口。更细的专题说明：

- [Web UI 与 API](web_ui.md)
- [分层架构](architecture.md)
- [Memory 系统](memory.md)
- [Tool 系统](tools.md)
- [Orchestrator](orchestrator.md)
- [测试报告](test_report.md)
- [开发日志](development_log.md)

`gpt_project_brief.md`、`gpt_review_request.md` 和 `ai_collaboration/` 是早期
设计及评审记录，保留用于追溯，不作为当前运行方式的权威说明。
