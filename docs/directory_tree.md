# Project Directory Tree

```text
PersonalAgent/
├── personal_agent/                 # 唯一业务源码
│   ├── __main__.py                 # python -m personal_agent
│   ├── bootstrap.py                # 组合根
│   ├── agent/                      # Planner / Reviewer / Executor
│   ├── analysis/                   # 日报与周报
│   ├── application/                # 调度工作流
│   ├── config/                     # 配置读取
│   ├── core/                       # 聊天 Agent、上下文、ToolRunner 和时钟
│   ├── interfaces/                 # CLI、LocalChannel 与 Web/API
│   ├── llm/                        # 模型接口和适配器
│   ├── memory/                     # 记忆、Evidence、Migration、备份和检索
│   ├── security/                   # Permission 与 Audit
│   └── tools/                      # ToolManager、文件工具和应用工具
├── ui/                             # 同源 Web 前端
│   ├── index.html
│   ├── app.js
│   ├── styles.css
│   └── README.md
├── tests/
│   ├── conftest.py
│   ├── database/
│   ├── backup/
│   ├── analysis/
│   ├── memory/
│   ├── unit/
│   ├── module/
│   ├── integration/
│   ├── behavior/
│   ├── security/
│   ├── scenarios/
│   └── fixtures/
├── docs/
│   ├── architecture.md
│   ├── README.md
│   ├── web_ui.md
│   ├── memory.md
│   ├── tools.md
│   ├── orchestrator.md
│   ├── project_report.md
│   ├── gpt_project_brief.md
│   ├── test_report.md
│   ├── development_log.md
│   ├── directory_tree.md
│   └── ai_collaboration/
├── data/
│   ├── README.md
│   ├── database/
│   │   └── goals_assistant.db
│   └── backups/
├── scripts/
│   ├── clean_goals.py
│   └── verify_run.py
├── legacy/                         # 临时兼容备份，不属于正式源码
│   ├── README.md
│   ├── main_old.py
│   ├── conversation_old.py
│   ├── database_old.py
│   ├── config_old.py
│   ├── time_utils_old.py
│   ├── weekly_review_old.py
│   └── messaging/
├── README.md
├── requirements.txt
├── pytest.ini
├── .env.example
├── .gitignore
├── 启动项目.bat
├── 打开UI界面.bat
└── .env                            # 本地私有配置，不提交
```

## Migration decisions

- 原 `messaging/` 只包含 `LocalChannel` 的兼容转发，已移入
  `legacy/messaging/`。正式实现是
  `personal_agent/interfaces/channel.py`。
- 没有创建重复的 `conversation/`、`database/`、`permission/` 和
  `utils/` 空目录：对应职责已经分别由 `core/ + interfaces/`、
  `memory/database.py`、`security/` 和 `core/clock.py` 承担。
- `legacy/` 只用于迁移期回溯。所有正式 import 必须以
  `personal_agent` 开头。
- Web UI 由 `personal_agent/interfaces/web.py` 与 API 同源提供，不能用
  独立静态服务器替代。
- `data/database/`、`data/backups/`、`.personal_agent/`、`.env` 和
  `.venv/` 都属于本地运行数据，不提交到 Git。
