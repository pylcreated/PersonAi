# Personal Agent Orchestrator v1.0

## 目标

Orchestrator 将现有 Memory、LLM、Tools 和 Permission 连接为一个透明、
有限、可审核的任务执行闭环：

```text
用户明确提交任务
    ↓
Planner 使用 LLM 生成 JSON 计划
    ↓
本地白名单与参数 Schema 校验
    ↓
RiskAnalyzer 重新计算风险
    ↓
用户查看完整计划并输入 yes
    ↓
Executor 逐步调用 ToolManager
    ↓
Permission 再次检查每个真实操作
    ↓
执行结果、审计和任务状态持久化
    ↓
完成，或在第一处失败停止
```

核心原则：

- LLM 只能规划，不能直接执行工具。
- 模型给出的风险值不可信，必须由本地规则覆盖。
- 用户审核的是确切工具、参数、风险和修改 diff。
- 审核计划不等于提升权限，ToolManager 仍会拒绝越权路径。
- Agent 不能通过文件工具修改 `.personal_agent` 内部状态和审计记录。
- 计划最多 8 步，不循环、不递归、不自动重规划。
- 任一步失败立即停止，未执行步骤保持 `pending`。

## 模块

```text
personal_agent/agent/
├── __init__.py
├── context.py
├── orchestrator.py
├── planner.py
├── executor.py
├── reviewer.py
├── state.py
├── task.py
├── risk.py
└── prompt.py
```

| 模块 | 职责 |
| --- | --- |
| `task.py` | TaskPlan、TaskStep 和合法状态 |
| `state.py` | 可替换状态接口及 JSON 原子持久化 |
| `prompt.py` | 受约束的规划提示词 |
| `planner.py` | 调用 LLM、解析 JSON、验证工具和参数 |
| `risk.py` | 本地确定性风险评分 |
| `reviewer.py` | 可替换审核接口及 CLI 实现 |
| `executor.py` | 将已审核步骤交给 ToolManager |
| `orchestrator.py` | 有限状态流和失败停止 |
| `context.py` | 通过 Memory 抽象提供只读规划上下文 |

## Task 模型

每个步骤保存：

```text
id
tool
description
arguments
risk
status
result
```

步骤状态：

```text
pending
running
completed
failed
skipped
```

任务状态：

```text
pending_review
cancelled
approved
running
completed
failed
```

任务还保存 `task_id`、原始用户需求、当前步骤、创建时间和更新时间。

## Planner 安全边界

Planner 的提示词只包含 `ToolRegistry` 中已经注册的工具及输入 Schema。
模型输出经过以下校验：

- 根节点必须是 JSON 对象。
- `goal` 必须非空。
- 必须有 1～8 个步骤。
- 每一步必须使用已注册工具。
- 每一步必须包含描述和参数对象。
- 必填参数不能缺失。
- 未声明参数会被拒绝。
- 字符串和整数参数进行基础类型校验。

Planner 提示词禁止生成：

- 权限提升。
- Shell 或 Python 执行。
- 浏览器和邮件操作。
- 系统控制。
- 永久删除。
- 循环或递归计划。

即使模型忽略提示词，解析器的工具白名单仍会阻止未知工具。

## Memory 上下文

规划时通过 `ConversationMemory` 抽象读取：

- 长期目标。
- 本周任务。
- 用户已经确认的相关长期记忆。
- 最近三条每日摘要。

候选记忆不会进入计划上下文。规划请求不会被当成普通聊天消息重复写入。

## 风险规则

| 工具 | 风险 |
| --- | ---: |
| `read_file` | 1 |
| `search_file` | 1 |
| `create_file` | 3 |
| `convert_file` | 3 |
| `update_file` | 5 |
| `restore_file` | 5 |
| `delete_file` | 9 |
| 未知或未来代码执行 | 10 |

```text
0～3：低风险
4～7：中风险
8～10：高风险
```

第一版中所有计划都必须由用户整体审核，不因低风险而跳过计划审核。
`update_file` 会额外展示经过权限检查的 unified diff。计划批准后，
ToolManager 仍会逐步验证工作区、操作类型和路径范围。

## Reviewer

CLI Reviewer 展示：

- 任务 ID。
- 目标。
- 每一步描述。
- 工具名称。
- 本地风险值和等级。
- 完整参数。
- 更新文件的 diff。

只有输入完整的 `yes` 才批准。其他输入都视为取消，且不会执行任何工具。

`PlanReviewer` 是协议，未来 Web UI 可以实现该协议，不需要修改 Planner、
Executor 或 Orchestrator。

## 执行与失败处理

Executor 不访问文件实现和权限策略，只调用：

```text
ToolManager.execute(ToolCall)
```

每一步执行前后都会保存状态。成功后继续下一个已经审核的固定步骤。
失败时：

1. 当前步骤标记为 `failed`。
2. 任务标记为 `failed`。
3. 后续步骤不执行。
4. 状态和错误信息保存。
5. 返回用户处理，不自动重新规划。

这种策略避免部分执行后 LLM 自动生成新计划并重复修改文件。

## 状态持久化

任务状态保存在：

```text
.personal_agent/tasks/<task_id>.json
```

状态写入采用同目录临时文件加原子替换。`TaskStateStore` 是协议，未来可以
替换为 SQLite 或其他数据库，不修改 Orchestrator。

工具操作本身继续记录在：

```text
.personal_agent/audit/tool_audit.jsonl
```

因此任务状态回答“进行到哪一步”，工具审计回答“实际操作了什么”。

## CLI

```text
/agent run 任务描述
/agent tasks
/agent show 任务ID
```

示例：

```text
/agent run 在项目内搜索 Agent 文档并创建一份索引文件
```

执行过程：

1. 本地模型生成计划。
2. CLI 显示计划。
3. 用户输入 `yes`。
4. 工具逐步执行。
5. CLI 显示各步骤状态和结果。

## 当前边界

- 只有显式 `/agent run` 才进入规划流程，普通聊天不会自动执行。
- 不支持计划编辑；用户可以拒绝后重新描述任务。
- 不支持基于工具结果自动追加新步骤。
- 不支持自动重试和自动重规划。
- 不支持步骤并行、分支、循环和长期自主任务。
- 不支持多 Agent。
- 状态文件不包含跨机器同步和锁机制，面向本地单进程。

这些限制是 v1 的安全边界，不是遗漏。

## 验证

```powershell
.\.venv\Scripts\python.exe -m unittest -v test_orchestrator test_tools test_architecture
```

测试覆盖：

- JSON 模式规划和 Memory 上下文传递。
- 工具白名单和参数 Schema 拒绝。
- 模型风险值被本地规则覆盖。
- 用户拒绝时零工具执行。
- 审核后按顺序执行并保存完成状态。
- 第一步失败时停止后续步骤，且不会重新规划。
- 高风险删除仍通过 ToolManager 并进入回收区。
- JSON 状态重新加载。
- CLI 运行和历史查询。
- Orchestrator 不依赖 UI、具体模型或具体文件工具。
