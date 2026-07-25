# Personal Agent Web UI 与 API

## 运行模型

Web UI 不是独立静态站点。Python 服务同时提供：

```text
浏览器
  ├─ GET /、/app.js、/styles.css → ui/ 静态资源
  └─ /api/*                      → Personal Agent 业务服务
                                           ↓
                                     SQLite / Ollama
```

前端统一使用同源相对路径 `/api/*`，不在 JavaScript 中写死端口。因此只要
页面由 Personal Agent Web 服务打开，前后端就会连接到同一个进程。

## 启动

推荐直接双击：

1. `启动项目.bat`
2. `打开UI界面.bat`

第二个脚本也能在检测到后端未运行时自动启动服务。

手动启动：

```powershell
.\.venv\Scripts\python.exe -m personal_agent web
```

默认访问地址：

```text
http://127.0.0.1:8765
```

需要临时使用其他端口时：

```powershell
.\.venv\Scripts\python.exe -m personal_agent web --port 9000
```

也可以在运行批处理脚本前设置 `PA_PORT`。不要使用
`python -m http.server` 启动 UI；静态服务器不会提供 `/api`，页面功能将
无法使用。

## 页面与数据

| 页面 | 主要数据或操作 |
| --- | --- |
| 今日 | 日期、任务、进度、昨日回顾、记忆候选 |
| 对话 | 当天消息、模型回复、聊天 Tool 调用 |
| 目标与任务 | 长期目标、今天任务、本周任务、完成状态 |
| 回顾 | 每日摘要与模型生成的周回顾 |
| 记忆 | 待审核候选、来源信息、已保存长期记忆 |
| 设置 | 模型名称、每日提醒、数据库备份 |

## API

### 读取接口

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/health` | 服务与 API 版本检查 |
| GET | `/api/dashboard` | UI 所需的聚合数据 |
| GET | `/api/daily?date=YYYY-MM-DD` | 最近或指定日期的日报 |
| GET | `/api/backups` | 本地备份列表 |
| GET | `/api/memory?status=active|all|archived|expired|deleted` | 正式长期记忆列表 |
| GET | `/api/memory/{id}` | 正式记忆、Provenance 与 Evidence |

### 操作接口

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| POST | `/api/chat` | 发送消息并取得模型回复 |
| POST | `/api/goals` | 新增长期目标 |
| POST | `/api/tasks` | 新增今天或本周任务 |
| POST | `/api/tasks/{id}` | 更新任务完成状态 |
| POST | `/api/weekly` | 生成本周回顾 |
| POST | `/api/memory/analyze` | 补做未处理聊天分析 |
| POST | `/api/memories/{id}/accept` | 确认候选记忆 |
| POST | `/api/memories/{id}/reject` | 忽略候选记忆 |
| POST | `/api/settings/model` | 保存模型名称，重启后生效 |
| POST | `/api/settings/reminder` | 修改每日提醒小时 |
| POST | `/api/backups` | 立即创建数据库备份 |
| PUT | `/api/memory/{id}` | 修改正式记忆的类型、内容、重要性和状态 |
| DELETE | `/api/memory/{id}` | 将正式记忆软删除为 `deleted` |

所有响应使用 UTF-8 JSON。业务输入错误返回 `400`，未知接口返回 `404`，
未处理异常返回 `500`。

正式记忆管理不直接从 Web 层写数据库，调用链固定为：

```text
UI → API → MemoryManagementService → AgentRepository → SQLite
```

`DELETE` 接口调用现有生命周期管理器，只改变状态，不删除 Provenance 或
Evidence。

## 聊天 Tool 联动

当消息包含明确的目标、任务或清单操作意图时，`ChatToolRunner` 会让模型
从应用 Tool 白名单生成计划，然后通过 `ToolManager` 执行。当前支持：

- 查询长期目标。
- 查询当前任务。
- 创建长期目标。
- 向指定目标添加本周任务。
- 按任务 ID 修改完成状态。

执行结果写入聊天回复和 Tool 审计日志。无法生成合法计划时不会修改数据，
也不会只凭模型文字宣称已经执行。

## 本地边界

- 服务默认只监听 `127.0.0.1`，同一局域网或互联网中的其他设备不能直接
  访问。
- `.env`、SQLite 数据库、备份和运行状态不会提交到 Git。
- 当前没有登录、用户隔离、HTTPS 或公网部署配置。
- 如果以后开放到局域网或公网，必须先增加认证、CSRF 防护、访问控制及
  安全的密钥管理。

## 联调检查

```powershell
Invoke-RestMethod http://127.0.0.1:8765/api/health
Invoke-RestMethod http://127.0.0.1:8765/api/dashboard
```

健康响应应包含：

```json
{
  "ok": true,
  "service": "personal-agent",
  "api_version": 7
}
```
