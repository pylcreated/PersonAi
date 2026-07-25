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

当前自动化测试结果为 `93 passed`。

## 文档导航

| 文档 | 内容 |
| --- | --- |
| [Personal_Agent_项目完整文档.md](Personal_Agent_项目完整文档.md) | 去重整合后的统一项目文档 |
| [Personal_Agent_AI协作与项目演进全记录.md](Personal_Agent_AI协作与项目演进全记录.md) | 根据历史 GPT/DeepSeek 对话、Agent 反馈、Codex 协作及当前源码整理的完整项目纪实 |
| [Personal_Agent_AI协作与项目演进全记录.docx](Personal_Agent_AI协作与项目演进全记录.docx) | 适合阅读、存档和分享的正式 Word 版 |
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
保留早期设计及评审原始材料，其中可能包含当时尚未实现的能力描述。
“AI 协作与项目演进全记录”已把这些资料与后续 Codex 协作、当前源码和测试
结果统一整理；原始材料继续用于追溯，不作为当前运行方式的权威说明。

当前运行和接口信息以“项目完整文档”、本索引、根目录 `README.md` 及源码
为准。分专题文档用于补充模块细节。
