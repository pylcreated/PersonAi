# Development Log

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
