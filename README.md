# Personal Agent

本地、单用户、隐私优先的个人 Agent。项目提供 Web UI 与 CLI、实时聊天、
目标和任务清单、带原文证据的每日分析、可追溯且由用户审核的长期记忆、
受权限保护的文件/应用工具，以及“LLM 规划 → Tool 执行 → 状态保存”的
有限 Agent 工作流。

## 项目结构

```text
personal_agent/        唯一业务源码
ui/                    本地响应式 Web UI
tests/                 分层自动化测试
docs/                  架构、模块说明和项目报告
data/database/         本地 SQLite 数据
scripts/               运维与诊断脚本
legacy/                迁移期兼容代码，只读备份
```

## 启动

先确保 Ollama 已运行。Windows 下推荐依次双击：

1. `启动项目.bat`
2. `打开UI界面.bat`

浏览器默认打开：

```text
http://127.0.0.1:8765
```

也可以手动启动完整的 Web UI 和 API：

```powershell
.\.venv\Scripts\python.exe -m personal_agent web
```

启动 CLI：

```powershell
.\.venv\Scripts\python.exe -m personal_agent
```

## 测试

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## 数据库备份与恢复

程序在日报成功保存并清理原始聊天后创建 SQLite 备份，并在每天 `00:30`
执行一次兜底备份，默认保留最近 30 份。也可以手动执行：

```powershell
.\.venv\Scripts\python.exe -m personal_agent backup
.\.venv\Scripts\python.exe -m personal_agent backups
.\.venv\Scripts\python.exe -m personal_agent restore backup_20260724_000500_000000.db
```

恢复操作只接受 `data/backups/` 中的 `.db` 文件，并要求输入
`RESTORE` 确认。自动化环境可以显式添加 `--yes`。

## 运维脚本

```powershell
.\.venv\Scripts\python.exe -m scripts.verify_run
.\.venv\Scripts\python.exe -m scripts.clean_goals
```

`clean_goals` 会在删除前要求人工确认。

## 文档

- [项目完整文档](docs/Personal_Agent_项目完整文档.md)
- [AI 协作与项目演进全记录](docs/Personal_Agent_AI协作与项目演进全记录.md)
- [AI 协作与项目演进全记录（Word）](docs/Personal_Agent_AI协作与项目演进全记录.docx)
- [文档索引与当前状态](docs/README.md)
- [Web UI 与 API](docs/web_ui.md)
- [架构说明](docs/architecture.md)
- [Memory 系统](docs/memory.md)
- [Tool 系统](docs/tools.md)
- [Agent Orchestrator](docs/orchestrator.md)
- [项目报告](docs/project_report.md)
- [GPT 项目评审请求](docs/gpt_review_request.md)
- [测试报告](docs/test_report.md)
- [开发记录](docs/development_log.md)
- [最新目录树](docs/directory_tree.md)

## 数据与隐私

- 真实数据库位于 `data/database/goals_assistant.db`。
- 数据库备份位于 `data/backups/`，默认保留最近 30 份。
- 启动时会自动执行尚未应用的 SQLite schema migration。
- `.env`、数据库、运行状态、日志和缓存均不进入版本控制。
- 测试使用内存数据库和隔离文件目录，不修改真实数据。
