# Development Log

## 2026-07-25：正式记忆管理 UI

- 保留候选审核、Provenance、Evidence 和生命周期设计。
- 新增 `MemoryManagementService`，补齐正式记忆查询、详情、编辑和软删除。
- Web UI 增加状态筛选、来源与 Evidence 详情、JSON 查看和编辑表单。
- 新增正式记忆 Service 与 HTTP API 测试；自动化测试增加到 93 项。

## 2026-07-25：本地 Web UI、应用 Tool 与 GitHub 发布

- 增加由 Python 同源服务提供的响应式 Web UI 和 `/api/*` 接口。
- Web UI 覆盖今日、对话、目标与任务、回顾、记忆审核和设置。
- 默认 Web 地址统一为 `http://127.0.0.1:8765`。
- 增加 `启动项目.bat` 与 `打开UI界面.bat`，支持服务检查、自动启动和打开页面。
- 将任务设计为独立于长期目标的今天/本周清单，并增加
  `004_personal_task_list.sql`。
- 增加 `ChatToolRunner` 与五个应用 Tool，使聊天模型可以查询、创建和
  更新目标及任务，所有执行仍经过 `ToolManager` 和审计。
- 增加每日摘要、候选记忆审核、已保存记忆及补做分析的 UI 联动。
- 聊天支持 Enter 发送、用户/AI 气泡分列以及返回页面自动定位到最新消息。
- 模型、提醒和备份设置按钮连接真实后端服务。
- 完成前后端路由与实时服务联调；自动化测试增加到 84 项。
- 初始化 Git 仓库，并通过草稿 PR 发布完整项目源码。

## 2026-07-24：V0.35 日报可信与记忆追踪

- 增加 `002_daily_evidence.sql` 和 `003_memory_provenance.sql`。
- 日报增加整体 confidence 和逐条 Evidence。
- Evidence 在原始聊天删除前校验消息 ID、用户角色和原文片段。
- progress、obstacles、next_actions 要求完整证据覆盖。
- 日报、Evidence、候选和聊天清理保持同一事务。
- 候选记忆记录来源日报、创建原因和证据消息。
- 用户接受候选时，来源和 Evidence 自动继承到正式记忆。
- 增加 `/memory show ID` 来源查询。
- 除日报后备份外，增加每天 `00:30` 固定兜底备份。
- 自动化测试增加到 80 项。

## 2026-07-24：数据可靠性 Phase 1

- 增加基于 SQL 文件的 SQLite schema migration。
- 当前完整 schema 登记为 `001_initial.sql`。
- 新库与没有版本表的旧库统一通过 migration 初始化和升级。
- 每个 migration 独立事务执行，失败回滚且不登记版本。
- 增加 SQLite 在线备份、完整性检查和最近 30 份保留策略。
- 日报成功提交并清理聊天后自动创建数据库备份。
- 增加 `backup`、`backups`、`restore` 命令。
- 恢复只允许使用备份目录内文件，替换前保留当前数据库。
- 增加数据库连接上下文退出时的显式关闭，避免 Windows 文件锁残留。
- 自动化测试由 63 项增加到 73 项。

## 2026-07-24：第二阶段工程迁移

- 确认 `personal_agent/` 已包含全部业务逻辑。
- 将根目录兼容入口迁入 `legacy/`。
- 将正式启动入口改为 `python -m personal_agent`。
- 将运维脚本迁入 `scripts/`。
- 将技术文档和 AI 协作记录迁入 `docs/`。
- 将真实 SQLite 数据迁入 `data/database/`。
- 将测试按 unit、module、integration、behavior、security、scenarios
  分层整理。
- 确认原 `messaging/` 只是兼容门面，迁入 `legacy/messaging/`；正式本地
  消息实现继续位于 `personal_agent/interfaces/channel.py`。
- 沿用现有职责边界，没有创建重复的 conversation、database、permission
  或 utils 空目录。
- 保持业务行为不变并运行完整测试。
