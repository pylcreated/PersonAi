# Personal Agent Test Report

## Report Metadata

```text
Date: 2026-07-24
Platform: Windows
Python: 3.14.2
Test runner: pytest 9.1.1
Total: 80 passed
Failed: 0
Duration: 以当前测试运行输出为准
```

执行命令：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

结果：

```text
80 passed
```

## Test Architecture

测试体系保留原有 42 项回归测试，并持续增加 pytest 分层测试。

```text
tests/
├── conftest.py
├── database/
├── backup/
├── analysis/
├── memory/
├── unit/
├── module/
├── integration/
├── behavior/
├── security/
├── scenarios/
└── fixtures/
```

数据库可靠性测试额外覆盖：

- 新数据库通过 migration 初始化。
- 没有版本表的旧数据库原地升级且数据不丢失。
- migration 中途失败时当前版本完整回滚，并可修复后重试。
- migration 重复执行不会重复改表或破坏数据。
- SQLite 在线备份、30 份保留策略和备份完整性校验。
- 删除数据库后可以恢复目标、聊天和正式记忆。
- 日报成功提交后生成的备份包含日报且不包含已清理聊天。
- 损坏备份不会替换当前正常数据库。
- 固定 `00:30` 兜底备份会在配置后注册。

日报可信和记忆来源测试额外覆盖：

- Evidence 只能引用真实用户消息。
- quote 与原消息不一致时拒绝日报并保留聊天。
- Evidence 写入失败时日报、候选和聊天清理全部回滚。
- Mock 日报只复制真实用户原文。
- 正式记忆继承来源日报、创建原因和 Evidence。

分层结果：

| 层级 | 标记 | 新增测试 | 结果 |
| --- | --- | ---: | --- |
| Layer 1 单元测试 | `unit` | 2 | PASS |
| Layer 2 模块测试 | `module` | 4 | PASS |
| Layer 3 集成测试 | `integration` | 1 | PASS |
| Layer 4 Agent 行为测试 | `behavior` | 5 | PASS |
| Layer 5 安全测试 | `security` | 6 | PASS |
| 完整用户场景 | `scenario` | 3 | PASS |

按层运行：

```powershell
.\.venv\Scripts\python.exe -m pytest -q -m unit
.\.venv\Scripts\python.exe -m pytest -q -m module
.\.venv\Scripts\python.exe -m pytest -q -m integration
.\.venv\Scripts\python.exe -m pytest -q -m behavior
.\.venv\Scripts\python.exe -m pytest -q -m security
.\.venv\Scripts\python.exe -m pytest -q -m scenario
```

## Memory

PASS

验证内容：

- 每日分析可以生成 `project` 类型候选记忆。
- 候选记忆与正式记忆物理分离。
- 用户接受后才进入正式 `memories`。
- 正式记忆删除是状态变为 `deleted`，不是物理删除。
- 非法记忆类型不能进入候选池。
- 分析失败时日报、候选均不落库，原始聊天继续保留。
- “我的 Agent 下一步怎么办”只检索 Agent 项目记忆，不返回 Python
  学习记忆。
- 候选记忆不会进入对话上下文。

## Tools

PASS

验证内容：

- 文件读取返回真实内容。
- 新文件创建后可以从文件系统读取。
- 更新前生成 unified diff。
- 未确认更新不会修改文件。
- 确认更新后保存旧版本备份。
- 删除操作移动到工具回收区，不做永久删除。
- Markdown 可以转换为 HTML。
- 源路径和目标路径分别进行权限检查。
- 工具调用顺序、结果和元数据能够进入 Agent 状态。

## Permission

PASS

验证内容：

- Workspace 允许读取和创建。
- External 默认禁止写入。
- `C:\Windows\System32` 访问被拒绝。
- `../../password.txt` 路径穿越在规范化后被拒绝。
- 删除没有逐次确认时被拒绝。
- execute 即使获得范围授权，也必须逐次确认。
- `.personal_agent` 内部任务、审计、备份和回收数据不能被普通工具修改。
- Agent 审核计划后仍不能绕过 ToolManager 的路径权限。

## Agent Orchestrator

PASS

验证内容：

- 简单读取任务遵循 Planner → Review → Executor → ToolManager。
- 多步骤任务按照搜索、读取、创建、转换的顺序执行。
- 模型只能选择注册工具。
- 参数必须符合 Tool input schema。
- 超过 8 步的计划被拒绝。
- 模型提供的风险值会被本地规则覆盖。
- 高风险删除明确显示风险等级。
- 用户输入 `no` 后任务为 `cancelled`，工具审计为空。
- 用户批准后任务状态依次保存。
- 第一步失败会停止后续步骤。
- 失败后不会自动重新规划。
- JSON 任务状态可以重新加载。

## LLM Failure Handling

PASS

验证内容：

- Ollama 连接失败转换为清晰的 `RuntimeError`。
- Ollama 返回无效 JSON 时被拒绝。
- Planner 返回普通文本而非 JSON 时不会执行工具。
- LLM 抛出不可用错误时 CLI 捕获并向用户反馈，进程不崩溃。
- 规划失败不会生成虚假的任务状态和工具审计。

## Security

PASS

验证内容：

- 未注册的 `run_shell` 工具无法进入计划。
- 系统文件和工作区外路径被拒绝。
- 相对路径穿越无法逃出 Workspace。
- 更新 diff 预览本身也经过权限检查。
- 读取内容和 diff 正文不会被复制进审计日志。
- Agent 无法篡改自己的状态和审计记录。
- 拒绝计划时文件系统保持不变。

## Complete User Scenarios

PASS

### 场景一：整理当天学习内容

验证流程：

```text
原始聊天
→ 每日分析
→ 删除原始聊天
→ 生成待审核 Skill 候选
→ Planner 读取近期日报
→ 用户审核
→ 创建 Markdown 学习总结
```

最终检查：

- 原始聊天已在分析成功后清理。
- 每日摘要存在。
- 长期记忆仍是待审核候选，没有自动生效。
- Markdown 总结真实生成。
- 任务状态为 `completed`。

### 场景二：询问 Agent 项目状态

验证流程：

```text
正式 Project Memory
→ MemoryRetriever
→ ContextBuilder
→ LLM 回复
```

最终检查：

- Agent 项目记忆进入“相关长期记忆”区段。
- Python 学习记忆没有被相关记忆检索器返回。
- LLM 回复使用了项目上下文。

### 场景三：修改项目代码

验证流程：

```text
Planner 生成 update_file
→ Reviewer 展示 diff
→ 用户拒绝
→ 文件保持不变
→ 用户重新明确批准
→ ToolManager 权限检查
→ 保存旧版本
→ 更新文件
```

最终检查：

- 拒绝时没有修改。
- diff 中包含真实旧行和新行。
- 批准后修改成功。
- 旧版本内容可以从备份读取。

## Storage Isolation

PASS

- SQLite 测试使用唯一共享内存 URI。
- 每个数据库测试保留独立 anchor 连接。
- 文件测试使用项目内 `.pytest_workspace/<uuid>`。
- 清理前校验隔离目录的直接父路径。
- pytest cache 插件已禁用，避免 Windows ACL 临时目录问题。
- 测试不要求 Ollama 实际运行。
- 测试不进行网络请求。
- 真实 `data/database/goals_assistant.db` 的大小和修改时间在测试前后保持不变。

## Failed Cases

无失败测试。

执行过程中曾发现并处理两个测试环境问题：

1. Windows 沙箱不能访问 pytest 默认临时目录。
2. pytest cache 插件创建的临时目录继承了不兼容 ACL。

解决方案：

- 使用项目内 UUID 隔离目录。
- 禁用 pytest cache provider。
- 忽略并验证清理测试工作区。

这些问题与 Personal Agent 业务逻辑无关。

## Known Gaps

### PDF / DOCX 转换

`convert_file` 当前只支持 txt、md、html。测试确认请求 PDF 时会明确失败且
不会生成伪 PDF。要满足 `md → pdf` 和 `docx → pdf`，需要增加独立转换
适配器以及相应依赖；调用外部程序时还必须通过 execute 权限。

### 工具结果驱动的动态计划

多步骤计划当前必须在审核前具有完整参数。不会根据搜索结果自动增加新
步骤，这是防止未审核计划扩张的 v1 安全边界。

### 并发与压力

当前面向本地单进程，尚未测试：

- 两个 Agent 任务同时修改同一文件。
- 超长聊天的分块日报。
- 超大目录搜索性能。
- SQLite 长时间并发写入。

### 真实模型质量

自动化测试使用确定性 Fake LLM，不评价 `gemma3:12b` 生成计划的实际质量。
真实模型验收应单独进行，不应让 CI 依赖本地 Ollama 状态。

## Suggestions

下一阶段建议：

1. 增加 Planner 真实输出的离线样本集和回归测试。
2. 增加数据库 schema 版本及迁移测试。
3. 为 PDF 转换建立独立适配器测试。
4. 增加文件并发修改检测，例如内容哈希或版本号。
5. 增加长聊天分块分析和上下文上限测试。
6. 后续接入 CI 时增加覆盖率报告，但不要把真实 Ollama 调用放入默认测试。

## Conclusion

```text
Memory: PASS
Tools: PASS
Permission: PASS
Agent: PASS
LLM Failure Handling: PASS
Security: PASS
User Scenarios: PASS
Failed Cases: none
```

当前测试结果证明项目不只是验证单个函数返回值，而是验证了：

- 数据生命周期。
- 模块连接关系。
- 用户审核语义。
- 工具真实副作用。
- 权限不可绕过。
- 异常停止与状态恢复。
- 完整用户操作场景。
