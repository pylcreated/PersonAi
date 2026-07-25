# Personal Agent 项目报告

## 一、报告信息

| 项目 | 内容 |
| --- | --- |
| 项目名称 | Personal Agent |
| 当前版本定位 | V0.35 Reliable Personal Agent |
| 产品阶段 | 完成核心闭环，进入长期自用可靠性验证阶段 |
| 运行方式 | Windows 本地单用户 CLI |
| 默认模型 | Ollama `gemma3:12b` |
| 数据库 | 本地 SQLite |
| 报告日期 | 2026-07-24 |
| 自动化测试 | 80 passed，0 failed |

## 二、项目概述

Personal Agent 是一款本地、单用户、隐私优先的个人 AI 助手。它围绕用户
长期目标、每周任务和每日行动建立连续的信息闭环，而不是只提供一次性问答。

核心流程：

```text
长期目标
    ↓
每周任务
    ↓
当天实时对话
    ↓
次日结构化日报
    ↓
真实消息 Evidence
    ↓
待审核长期记忆
    ↓
用户确认
    ↓
可追踪正式记忆
```

项目默认使用本地 Ollama，不依赖付费 API，不接入邮件、Telegram 或云端
数据库。原始聊天只用于当天对话和次日分析；日报成功保存后，原始聊天自动
删除，长期保留结构化日报、最小证据、目标、任务和用户确认的记忆。

当前版本已经不只是代码演示。它具备完整业务闭环、分层架构、安全工具系统、
数据库升级、备份恢复和自动化测试，适合进入 30 天真实自用验证。

## 三、产品目标与设计原则

### 3.1 产品目标

- 通过实时对话降低每日记录成本。
- 将零散聊天转化为可回顾的结构化日报。
- 使用目标和任务维持行动方向。
- 只在用户确认后形成长期个人记忆。
- 让日报和长期记忆能够追溯到真实来源。
- 让本地数据能够升级、备份和恢复。
- 在增加智能能力时保留用户审核和权限边界。

### 3.2 当前设计原则

- 本地优先，免费优先，隐私优先。
- 核心业务不依赖具体模型、数据库或界面。
- 模型不能直接写入正式长期记忆。
- Agent 不能绕过 ToolManager 和 Permission。
- 高风险操作必须经过用户确认。
- 日报没有可靠保存前不得删除原始聊天。
- 模型输出格式正确不等于事实正确，事实必须绑定 Evidence。
- 不引入微服务、多 Agent、向量数据库或复杂动态规划。

## 四、当前功能

### 4.1 本地实时对话

用户直接在 CLI 中输入普通文字即可对话。

每轮处理流程：

1. 获取或创建当天会话。
2. 保存用户消息。
3. 加载当天聊天、活跃目标、本周任务、近期日报和相关正式记忆。
4. 调用配置的模型生成回复。
5. 保存助手回复。
6. 在终端显示结果。

实时上下文会限制历史长度，避免聊天无限增长。Ollama 不可用或返回异常时，
程序向用户显示明确错误，不让整个进程直接崩溃。

### 4.2 长期目标与每周任务

支持：

- 首次运行创建多个长期目标。
- 查看当前活跃目标。
- 为指定目标创建本周任务。
- 查看本周任务。
- 标记任务完成。
- 将已完成任务重新打开。
- 在周报中统计任务进度。

主要命令：

```text
/goals
/tasks
/task-add 目标ID 任务内容
/task-done 任务ID
/task-reopen 任务ID
```

### 4.3 每日聊天生命周期

原始聊天按照北京时间自然日划分。

```text
当天聊天
    ↓
次日 00:05 分析
    ↓
校验日报 JSON
    ↓
校验 Evidence
    ↓
同一事务保存：
日报 + Evidence + 候选记忆
    ↓
删除对应原始会话和消息
    ↓
生成数据库备份
```

如果模型调用、JSON 解析、Evidence 校验或数据库写入失败：

- 不删除原始聊天。
- 不保存半成品日报。
- 不保存半成品候选记忆。
- 会话标记为失败并记录错误。
- 程序运行期间每 30 分钟重试。
- 下次启动时补做历史未完成分析。

### 4.4 可信日报与 Evidence

日报包含：

- 总结 `summary`
- 进展 `progress`
- 阻碍 `obstacles`
- 模式 `patterns`
- 状态 `mood`
- 下一步行动 `next_actions`
- 整体可信度 `confidence`

Evidence 至少记录：

- 对应日报。
- 被支持的结论。
- Evidence 类型。
- 原始消息 ID。
- 原始消息时间。
- 从用户消息中逐字复制的最小原文。

系统在删除聊天前执行双重校验：

- `message_id` 必须属于当天真实用户消息。
- `quote` 必须逐字存在于该消息正文。

`progress`、`obstacles` 和 `next_actions` 中的每一项必须有 Evidence。
Evidence 保存失败时，日报、候选记忆和聊天清理全部回滚。

查看日报：

```text
/daily
/daily 2026-07-24
```

输出会同时显示事实、可信度、消息 ID、时间和原文依据。

### 4.5 用户可控 Memory

记忆分为候选和正式两层。

```text
每日分析提出候选
    ↓
用户查看或编辑
    ↓
冲突检测
    ↓
用户接受或拒绝
    ↓
正式长期记忆
```

候选记忆类型：

- `profile`
- `preference`
- `goal`
- `project`
- `skill`
- `experience`

规则：

- 模型不能直接写入正式记忆。
- 候选记忆不会进入聊天上下文。
- 接受前进行保守冲突检测。
- 冲突不会静默覆盖旧记忆。
- 只有用户确认且状态为 `active` 的正式记忆可以被检索。
- 删除采用软删除，不立即物理擦除。

主要命令：

```text
/memory candidates
/memory edit ID 类型 内容
/memory accept ID
/memory accept ID force
/memory reject ID
/memory list
/memory show ID
/memory archive ID
/memory expire ID
/memory delete ID
```

### 4.6 Memory Provenance

用户接受候选后，系统在同一事务中保存：

- 来源类型。
- 来源日报。
- 形成该记忆的原因。
- 关联 Evidence。
- 原始消息 ID、时间和最小原文。

因此原始聊天删除后，用户仍可执行：

```text
/memory show 记忆ID
```

查看“这条记忆来自哪里、为什么存在、依据是什么”。旧版本中没有结构化来源
的数据仍然兼容，但会显示为旧版本记忆。

### 4.7 每周复盘

命令：

```text
/weekly
```

周报读取：

- 本周每日结构化分析。
- 本周任务及完成状态。
- 对应长期目标。
- 兼容保留的旧版复盘记录。

模型提示要求只使用数据库事实；信息不足时明确说明，不能补充通用或虚构阻碍。
Mock 模式同样只整理真实数据。

### 4.8 定时工作流

程序运行期间注册：

| 时间或周期 | 工作 |
| --- | --- |
| 用户设置时间 | 每日复盘提醒 |
| 每周日用户设置时间 | 生成周报 |
| 每天 00:05 | 分析历史未处理聊天 |
| 每 30 分钟 | 重试失败日报 |
| 每天 00:30 | 数据库兜底备份 |

日报成功提交后还会立即生成一次数据库快照。修改提醒时间后，调度任务会立即
重新注册。

程序关闭时普通定时任务不会运行，但重新启动后会补做历史日报。固定备份和
提醒仍要求程序处于运行状态。

### 4.9 本地文件 Tool

当前工具能力：

- 读取文件。
- 搜索文件和内容。
- 创建文件。
- 预览 diff 后更新文件。
- 更新前保存旧版本。
- 将删除文件移动到工具回收区。
- 恢复回收文件。
- 转换部分文本格式。

所有工具统一经过：

```text
ToolRegistry
    ↓
ToolManager
    ↓
PermissionChecker
    ↓
真实文件操作
    ↓
AuditSink
```

工作区外默认拒绝写入，路径穿越会在规范化后拦截。删除和执行等危险权限要求
逐次确认。Agent 内部任务、审计、备份和回收目录不能由普通工具修改。

### 4.10 有限 Agent Orchestrator

执行流程：

```text
用户任务
    ↓
LLM Planner 生成 JSON 计划
    ↓
本地白名单、Schema 和风险校验
    ↓
用户审核计划
    ↓
Executor 顺序调用 ToolManager
    ↓
保存任务及步骤状态
```

安全边界：

- 计划最多 8 步。
- Planner 只能选择已注册工具。
- 参数必须符合工具 Schema。
- 风险等级由本地规则最终决定。
- 用户拒绝后不执行任何步骤。
- 第一个步骤失败后停止。
- 不自动重新规划。
- 不自动扩大已经审核的计划。
- 不允许绕过工具权限和审计。

## 五、系统架构

### 5.1 目录结构

```text
personal_agent/
├── __main__.py          # 模块入口和备份恢复命令
├── bootstrap.py         # 唯一依赖组装位置
├── agent/               # Planner、审核、执行、风险和状态
├── analysis/            # 日报与周报用例
├── application/         # 调度、重试和启动补偿
├── config/              # 环境和运行配置
├── core/                # 对话 Agent、上下文和抽象端口
├── interfaces/          # CLI 与本地消息输出
├── llm/                 # LLM 接口和适配器
├── memory/              # Memory、Evidence、SQLite、Migration 和备份
├── security/            # Permission 与 Audit
└── tools/               # 工具协议、注册和统一执行
```

### 5.2 依赖方向

```text
__main__
    ↓
bootstrap
    ↓
interfaces / application
    ↓
core / analysis / agent
    ↓
抽象 LLM / Repository / Tool / Permission
    ↓
Ollama / SQLite / 本地文件系统
```

核心层不知道：

- 当前使用 Ollama 还是其他模型。
- 数据是否具体存储在 SQLite。
- 用户通过 CLI 还是未来其他界面操作。
- 文件工具如何实现。

具体实现只在 `bootstrap.py` 中选择和组装。

### 5.3 模块职责

| 模块 | 职责 |
| --- | --- |
| `core` | 单轮对话协调和上下文构建 |
| `llm` | 统一模型接口与不同提供商适配 |
| `memory` | 对话存储、日报、Evidence、候选、正式记忆和检索 |
| `analysis` | 日报及周报业务用例 |
| `application` | 定时调度、失败重试和启动补偿 |
| `agent` | 有限计划、审核、风险、执行和状态 |
| `tools` | 工具定义、注册、预览和真实副作用 |
| `security` | 路径权限、危险操作确认和审计 |
| `interfaces` | CLI 输入、命令解析和结果展示 |

## 六、数据库与数据可靠性

### 6.1 数据库位置

```text
data/database/goals_assistant.db
```

### 6.2 主要数据表

| 表 | 用途 |
| --- | --- |
| `schema_version` | 已执行 Migration 版本 |
| `goals` | 长期目标 |
| `tasks` | 每周任务 |
| `settings` | 本地提醒和初始化设置 |
| `error_log` | 定时任务错误 |
| `chat_sessions` | 按自然日组织的临时会话 |
| `chat_messages` | 临时用户及助手原始消息 |
| `daily_analyses` | 长期结构化日报和可信度 |
| `daily_report_evidence` | 日报事实的最小原文依据 |
| `candidate_memories` | 待用户审核的候选记忆 |
| `candidate_memory_evidence` | 候选与 Evidence 关系 |
| `memories` | 用户确认的正式长期记忆 |
| `memory_sources` | 正式记忆来源和创建原因 |
| `memory_evidence` | 正式记忆与 Evidence 关系 |
| `reflections` | 旧版复盘兼容数据 |

### 6.3 Schema Migration

当前 Migration：

```text
001_initial.sql
002_daily_evidence.sql
003_memory_provenance.sql
```

启动时：

1. 读取 `schema_version`。
2. 按版本排序查找未执行 SQL。
3. 每个版本使用独立事务执行。
4. 成功后记录版本和时间。
5. 失败时回滚当前版本。

新数据库和没有版本信息的旧数据库使用同一升级入口。Migration 重复执行不会
重复修改已经升级的数据。

### 6.4 自动备份

备份目录：

```text
data/backups/
├── backup_YYYYMMDD_HHMMSS_microseconds.db
└── pre_restore_YYYYMMDD_HHMMSS_microseconds.db
```

备份特点：

- 使用 SQLite 在线备份接口。
- 不直接复制正在使用的数据库文件。
- 完成后执行 `PRAGMA quick_check`。
- 常规备份保留最近 30 份。
- 日报成功后立即备份。
- 每天 00:30 再生成兜底备份。

手动操作：

```powershell
.\.venv\Scripts\python.exe -m personal_agent backup
.\.venv\Scripts\python.exe -m personal_agent backups
.\.venv\Scripts\python.exe -m personal_agent restore 备份文件名.db
```

恢复只接受备份目录中的直接 `.db` 文件。恢复前校验备份，替换正式数据库前
将当前数据库暂存为 `pre_restore_*`；替换失败时自动恢复原数据库。

## 七、模型层

统一接口：

```python
complete(prompt: str, json_mode: bool = False) -> str
```

当前适配器：

- Ollama
- OpenAI 兼容接口
- 通用 HTTP 接口
- 确定性 Mock

默认配置：

```dotenv
LLM_PROVIDER=ollama
LLM_MODEL_NAME=gemma3:12b
OLLAMA_BASE_URL=http://127.0.0.1:11434
OPENAI_MOCK_MODE=false
```

Ollama 模式不需要 API Key，对话数据不会发送到云端。切换到外部模型时，
必要上下文会发送给用户配置的模型服务，使用者需要自行评估隐私风险。

## 八、安全与隐私

当前安全措施：

- 数据默认只保存在本地。
- 使用 Ollama 时不上传聊天。
- `.env`、数据库、备份、日志和运行状态不进入版本控制。
- `.env.example` 只包含占位符。
- SQL 使用参数化查询。
- 原始聊天仅保留到日报成功。
- Evidence 只保留最小必要原文。
- 模型不能直接写入正式记忆。
- 工具操作执行路径范围检查。
- 危险操作要求用户确认。
- 审计日志不记录完整文件正文。
- Agent 内部目录不能由普通工具修改。
- 测试数据库与真实数据库隔离。

仍未实现：

- SQLite 文件加密。
- 结构化数据导出。
- 用户按日期彻底遗忘所有衍生数据。
- 磁盘剩余空间告警。
- 操作系统级备份和异地备份。

## 九、测试体系

### 9.1 当前结果

```text
80 passed
0 failed
```

运行：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

测试同时保留历史 `unittest` 回归，并使用 pytest 组织新的分层测试。

### 9.2 测试目录

```text
tests/
├── database/       # Migration、升级、回滚和幂等
├── backup/         # 在线备份、恢复、保留和 CLI
├── analysis/       # Evidence、事实校验和事务回滚
├── memory/         # Memory Provenance
├── unit/
├── module/
├── integration/
├── behavior/
├── security/
├── scenarios/
└── fixtures/
```

### 9.3 已覆盖能力

- 新数据库初始化。
- 旧数据库原地升级。
- Migration 失败回滚和重复执行。
- 自动备份、30 份保留和损坏备份拒绝。
- 删除数据库后的目标、聊天和记忆恢复。
- 日报提交后的备份内容。
- 固定 `00:30` 备份调度。
- 实时聊天双方消息保存。
- 日报成功删除、失败保留。
- Evidence 真实消息及原文校验。
- Evidence 写入失败时完整事务回滚。
- Mock 不编造 Evidence。
- 候选审核、冲突检测和生命周期。
- 正式记忆来源和 Evidence 继承。
- Tool 路径权限、版本备份、回收和恢复。
- Planner 白名单、Schema 和本地风险覆盖。
- 用户拒绝时零执行。
- 执行失败后停止。
- Ollama 不可用和无效 JSON。
- 完整用户使用场景。

### 9.4 测试隔离

- SQLite 测试使用共享内存或隔离文件数据库。
- 文件工具测试使用独立工作目录。
- 测试不调用真实 Ollama。
- 测试不进行网络请求。
- 真实数据库大小和修改时间不受测试影响。

## 十、安装与运行

### 10.1 安装依赖

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 10.2 启动 Ollama

```powershell
ollama serve
ollama list
```

如果 Ollama 桌面程序已经运行，不需要重复启动服务。

### 10.3 启动 Personal Agent

```powershell
.\.venv\Scripts\python.exe -m personal_agent
```

首次正式启动会自动执行尚未应用的数据库 Migration。

### 10.4 运行诊断

```powershell
.\.venv\Scripts\python.exe -m scripts.verify_run
```

### 10.5 查看帮助

程序启动后输入：

```text
/help
```

## 十一、当前项目成熟度

### 11.1 已经达到的水平

- 业务闭环完整。
- 正式源码和历史兼容代码已分离。
- 核心模块职责清楚。
- 数据库具备版本升级能力。
- 数据具备本地备份恢复能力。
- 日报事实可以追溯。
- 长期记忆可以解释来源。
- Tool 和 Agent 具备明确安全边界。
- 自动化测试覆盖关键数据生命周期和安全路径。

### 11.2 尚未达到的水平

项目还不能定义为成熟发布产品，主要原因：

- 仍然只有 CLI。
- 缺少连续 30 天真实使用数据。
- 超长单日聊天尚未分块分析。
- 跨午夜仍在生成的对话缺少会话级锁。
- 最早失败日期可能阻塞后续日报。
- 程序关闭后定时提醒和固定备份不会执行。
- 没有结构化导出和彻底遗忘命令。
- 真实 `gemma3:12b` 输出质量尚未形成离线回归样本集。
- 没有长期压力、并发和磁盘故障测试。

综合判断：

> 当前处于“可靠性基础完成、可以开始长期自用验证”的阶段，比普通 MVP
> 更可靠，但还没有经过真实时间和真实数据规模验证。

## 十二、后续建议

### P1：30 天使用前必须补强

1. 增加 Chat Session Lock，避免跨午夜回复与日报并发。
2. 增加独立日报任务状态，使单日失败不阻塞其他日期。
3. 增加超长聊天分块事实提取和最终汇总。
4. 建立真实模型离线样本和 Evidence 质量回归集。
5. 增加备份恢复演练记录和磁盘空间检查。

### P2：数据控制

1. 增加 JSON/Markdown 数据导出。
2. 增加按日期删除及衍生数据影响预览。
3. 增加删除二次确认和专用审计。
4. 增加日报及提示词版本。

### P3：使用体验

1. 增加 Ollama Streaming。
2. 将聊天、分析和规划模型通过 Model Router 解耦。
3. 增加每日行动面板。
4. 在 30 天实验成功后再决定是否开发 GUI。

### 暂时不建议开发

- 自动重新规划 Agent。
- 多 Agent 系统。
- 浏览器自动操作。
- 向量数据库。
- 云端同步。
- 复杂微服务。

## 十三、30 天验证建议

每天记录：

- 是否启动并使用。
- 对话轮数。
- 日报是否成功。
- 日报 Evidence 是否正确。
- 有多少候选记忆被接受、修改或拒绝。
- 自动备份是否生成。
- 是否出现恢复、迁移或调度错误。

每周抽查：

- 随机 10 条日报事实。
- 随机 10 条正式记忆。
- 检查原文依据、事实正确性和实际价值。

建议成功指标：

| 指标 | 目标 |
| --- | --- |
| 30 天使用天数 | ≥ 22 天 |
| 日报成功率 | ≥ 95% |
| Evidence 正确率 | ≥ 95% |
| Memory 正确率 | ≥ 90% |
| 无法恢复的数据丢失 | 0 次 |
| 越权工具操作 | 0 次 |
| 用户认为有价值的日报比例 | ≥ 70% |

## 十四、项目结论

Personal Agent 已经完成从“可运行 Agent MVP”到“具备可靠性基础的本地个人
助手”的升级。

当前最有价值的能力不是模型能说多少，而是：

- 对话能够转化为行动记录。
- 日报能够指向真实证据。
- 长期记忆由用户控制并可以解释来源。
- 数据库可以安全升级。
- 个人数据可以备份和恢复。
- Agent 和 Tool 始终受到权限与审核约束。

下一阶段不应继续扩张 Agent 自主能力，而应通过 30 天真实使用验证可靠性、
日报价值和记忆质量，并优先解决跨日并发、失败任务隔离、长聊天处理和数据
导出。只有这些基础经受真实使用后，Streaming、GUI 和更复杂的 Agent 能力
才值得进入开发计划。
