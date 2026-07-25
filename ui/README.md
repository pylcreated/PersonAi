# 栖心 UI 原型

这是 Personal Agent 的响应式前端概念稿，覆盖：

- 今日总览
- 实时对话
- 目标与每周任务
- 日报 / 周报回顾
- 候选记忆审核
- 本地模型、分析与备份设置

## 本地预览

项目根目录提供两个启动入口：

- `启动项目.bat`：启动 Personal Agent 后端、数据库、Agent 与本地 Web API。
- `打开UI界面.bat`：检查后端连接并自动在浏览器中打开页面。

推荐先双击 `启动项目.bat`，再双击 `打开UI界面.bat`。

也可以在项目根目录手动启动完整的 Web UI 和 API：

```powershell
.\.venv\Scripts\python.exe -m personal_agent web
```

然后访问 `http://127.0.0.1:8765`。

页面通过同源 `/api` 接口连接现有 Python 业务层和 SQLite 数据库，无需额外安装前端依赖。

启动脚本统一使用 `http://127.0.0.1:8765`。直接运行 `打开UI界面.bat`
时，如果后端尚未启动，脚本会自动启动后端并等待连接。
