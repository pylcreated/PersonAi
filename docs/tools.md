# Personal Agent Tool 系统说明

## 设计目标

Tool 系统为 Agent 提供有限、标准化、可审计、可恢复的本地文件操作能力。

三个模块的边界是：

```text
Memory：AI 知道什么
Tool：AI 能做什么
Permission：AI 被允许做什么
```

工具实现本身不决定权限。所有操作必须经过 `ToolManager`，依次完成工具
查找、参数解析、路径范围检查、用户确认、执行和审计。

当前已经接入 Orchestrator：LLM 可以在显式 `/agent run` 请求中生成
受白名单约束的工具计划，但仍不能直接执行。用户审核完整计划后，
Executor 才会逐步调用 ToolManager。普通聊天不会自动触发工具。

## 执行链路

```text
用户 CLI 请求
    ↓
ToolCall
    ↓
ToolRegistry 查找能力
    ↓
工具声明所需的全部授权
    ↓
ScopedPermissionManager
    ├─ 操作类型：read / write / delete / execute
    ├─ 文件来源：workspace / temporary / external
    ├─ 路径是否属于授权范围
    └─ 是否需要本次用户确认
    ↓
允许 → execute → ToolResult
拒绝 ───────────→ ToolResult
    ↓
JsonlAuditSink
```

`convert_file` 等涉及多个路径的工具会分别检查源文件读取权限和目标文件
写入权限，不会只检查其中一个路径。

## 当前工具

| 工具 | 能力 | 权限 |
| --- | --- | --- |
| `read_file` | 读取最大 2 MiB 的 UTF-8 文本文件 | read |
| `search_file` | 在授权目录按文件名递归搜索 | read |
| `create_file` | 创建新文本文件，不覆盖已有文件 | write |
| `update_file` | 展示 diff、确认后更新并备份旧版本 | write + confirm |
| `delete_file` | 确认后将普通文件移动到回收区 | delete + confirm |
| `restore_file` | 根据恢复 ID 将文件移回原路径 | write + confirm |
| `convert_file` | 在 txt、md、html 之间转换 | read + write |

当前 `convert_file` 不依赖外部程序，因此暂不支持 PDF 和 DOCX。后续可以
增加转换适配器，但调用外部程序时还必须通过 `execute` 权限。

## 权限模型

启动时只自动授予项目工作区：

```text
read
write
delete
```

工作区以外的路径默认全部拒绝。用户可以在当前运行期间增加一个外部
只读范围：

```text
/tool grant-read study "D:\Study"
```

该命令不会授予写入、删除或执行权限。查看和撤销范围：

```text
/tool scopes
/tool revoke study
```

基础 `workspace` 范围不能通过 CLI 撤销。外部范围只保存在当前进程中，
重启后失效，这符合第一版“任务范围授权”而非永久扩大权限的原则。

路径在检查前会规范化。符号链接或 `..` 指向授权根之外时，会按最终路径
判断并拒绝。

`.personal_agent` 是内部状态保护区。普通工具请求即使位于工作区、即使
计划已经获得确认，也不能读取、覆盖或删除其中的审计、任务状态、版本
备份和回收数据。只有负责这些数据的内部组件直接维护该目录。

## 用户确认

以下操作必须逐次输入 `yes`：

- 更新已有文件。
- 将文件移入回收区。
- 从回收区恢复文件。
- 未来可能加入的代码执行。

更新前 CLI 会展示 unified diff。用户取消时不会调用工具执行逻辑。

创建新文件不覆盖已有目标，因此只需要工作区写权限；如果目标已存在，
工具返回失败。

## 版本与恢复

运行时数据保存在项目下被 Git 忽略的目录：

```text
.personal_agent/
├── audit/
│   └── tool_audit.jsonl
├── versions/
│   └── <version_id>/
└── trash/
    └── <trash_id>/
        ├── metadata.json
        └── 原文件
```

`update_file` 在替换内容前复制旧版本，并在结果中返回 `version_id` 和
备份路径。新内容先写入同目录临时文件，再通过原子替换更新目标。

`delete_file` 不做物理删除，只移动到工具回收区并返回恢复 ID：

```text
/tool restore 恢复ID
```

如果原路径已经出现新文件，恢复操作会拒绝覆盖。

## 审计

允许、拒绝、参数错误、未知工具和执行失败都会写入追加式 JSONL 日志。

每条记录包含：

- 时间。
- 调用者。
- 工具名称。
- 操作类型。
- 目标路径。
- 是否通过权限检查。
- 执行结果。
- 授权来自策略还是本次用户确认。
- 简要结果信息。

查看最近 20 条：

```text
/tool audit
```

审计日志不保存待写入文件的完整内容，避免把正文再次复制到日志。

## CLI

```text
/tool list
/tool scopes
/tool grant-read 范围名 外部目录
/tool revoke 范围名
/tool read 路径
/tool search 关键词 [目录]
/tool create 路径 [内容]
/tool update 路径 [新内容]
/tool delete 路径
/tool restore 恢复ID
/tool convert 源路径 目标路径
/tool audit
```

包含空格的路径需要使用双引号。

## 模块职责

| 模块 | 职责 |
| --- | --- |
| `tools/base.py` | Tool、ToolCall、ToolAuthorization、ToolResult 协议 |
| `tools/registry.py` | 工具注册和能力描述 |
| `tools/manager.py` | 唯一安全执行入口 |
| `tools/file_tool.py` | 文件工具、备份、回收与转换实现 |
| `security/permission.py` | 操作类型、来源、范围和确认策略 |
| `security/audit.py` | 审计事件和 JSONL 持久化 |
| `bootstrap.py` | 注册工具并注入权限和审计实现 |
| `interfaces/cli.py` | 用户显式调用和确认界面 |

## 当前边界

- LLM 只能提出有限 ToolCall 计划，不能跳过用户审核或 ToolManager。
- 没有 Python、Shell 或其他代码执行工具。
- 没有浏览器、邮件、系统控制和多 Agent。
- 外部授权范围只支持只读，并且重启失效。
- 搜索第一版只匹配文件名，不建立内容索引。
- 格式转换当前仅支持 txt、md 和 html。
- 尚未提供旧版本列表和一键恢复命令；备份文件和版本 ID 已保存。
- 工具状态目录没有自动清理策略，避免后台永久删除用户数据。

## 验证

```powershell
.\.venv\Scripts\python.exe -m unittest -v test_tools test_architecture
```

测试使用项目内隔离临时目录，覆盖：

- 七种标准工具注册。
- 工作区内创建、读取和搜索。
- 外部路径默认拒绝及显式只读授权。
- 外部写入持续拒绝。
- 更新确认和旧版本备份。
- 回收删除和确认恢复。
- 转换的双路径权限检查。
- execute 范围即使存在也必须逐次确认。
- 成功、拒绝和未知工具审计。
- CLI 带空格路径解析。
