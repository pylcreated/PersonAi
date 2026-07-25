# Personal Agent 文档索引

最后更新：2026-07-25

## 当前状态

Personal Agent 当前是一个 Windows 本地、单用户、隐私优先的个人 AI
助手，提供 CLI 与 Web UI 两种入口。Web UI 和 Python API 由同一个本地
服务提供，默认地址为：

```text
http://127.0.0.1:8765
```

当前主要能力：

- 与 Ollama `gemma3:12b` 实时对话。
- 管理长期目标以及独立的今天/本周任务清单。
- 让聊天模型通过受控 Tool 查询和修改目标、任务。
- 次日自动生成带 Evidence 的每日摘要。
- 由用户审核候选记忆，并查看已确认的长期记忆。
- 生成周回顾、配置提醒时间并管理 SQLite 备份。
- 通过两个 Windows 脚本一键启动服务和打开 UI。

当前自动化测试结果为 `84 passed`。

## 文档导航

| 文档 | 内容 |
| --- | --- |
| [web_ui.md](web_ui.md) | Web UI、API、端口和启动方式 |
| [architecture.md](architecture.md) | 分层架构与依赖方向 |
| [directory_tree.md](directory_tree.md) | 当前项目目录 |
| [memory.md](memory.md) | 日报、Evidence、候选记忆与审核 |
| [tools.md](tools.md) | 文件 Tool、应用 Tool、权限和审计 |
| [orchestrator.md](orchestrator.md) | 有限 Agent 规划与执行 |
| [test_report.md](test_report.md) | 自动化测试结果与已知缺口 |
| [project_report.md](project_report.md) | 当前项目综合报告 |
| [development_log.md](development_log.md) | 开发变更记录 |

## 历史材料

`gpt_project_brief.md`、`gpt_review_request.md` 和 `ai_collaboration/`
记录了早期设计及评审过程，其中可能保留当时尚未实现的能力描述。它们用于
追溯决策，不作为当前运行方式的权威说明。

当前运行和接口信息以本索引、`web_ui.md`、根目录 `README.md` 及源码为准。
