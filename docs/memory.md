# Personal Agent Memory 系统说明

## 设计目标

Memory 系统用于从每日聊天中提取可能长期有用的信息，同时确保：

- 模型只能提出候选，不能自行写入正式长期记忆。
- 用户可以查看、修改、接受或拒绝每条候选。
- 只有用户确认且状态为 `active` 的记忆可以进入聊天上下文。
- 冲突不会静默覆盖，必须由用户明确确认。
- 原始聊天仅在日报和候选记忆都成功写入后删除。

当前版本保持本地、单用户和 SQLite，不引入向量数据库或多 Agent。用户可
通过 CLI 或本地 Web UI 查看日报、审核候选记忆和浏览已保存记忆。

## 数据流

```text
当天实时聊天
    ↓
次日 DailyMemoryAnalyzer 结构化分析
    ├─ daily_analyses：每日摘要
    ├─ daily_report_evidence：经过原文校验的最小证据
    └─ candidate_memories：待审核候选
              ↓
        用户通过 CLI 或 Web UI 查看 / 编辑 / 拒绝
              ↓
       冲突检测后明确接受
              ↓
          memories：正式记忆
              ├─ memory_sources：创建来源和原因
              └─ memory_evidence：继承的日报证据
              ↓
     相关问题触发关键词检索
              ↓
       最多 5 条注入聊天上下文
```

保存日报、校验证据、保存候选和删除前一天原始聊天位于同一个 SQLite
事务中。Evidence 的 `message_id` 必须指向当天真实用户消息，`quote`
必须逐字包含在原消息中。原始聊天删除后，只保留必要的证据片段。模型调用、
证据校验或数据库写入失败时事务回滚，原始聊天继续保留。

## 日报 Evidence

每条 Evidence 保存：

- 对应日报和事实类型。
- 被支持的日报结论。
- 原始消息 ID 和消息时间。
- 从用户消息中逐字复制的最小原文。

`progress`、`obstacles` 和 `next_actions` 的每一项都必须至少有一条证据。
CLI 使用 `/daily 日期` 查看日报时会同时显示证据、原消息 ID 和整份日报
可信度。Mock 模式也只引用真实用户消息，不生成通用虚构事实。

## 两类记忆

### candidate_memories

模型从日报分析中提出的候选信息。主要字段：

- `type`：`profile`、`preference`、`goal`、`project`、`skill` 或 `experience`
- `content`：候选内容
- `importance`：模型给出的重要度，范围 0～1
- `confidence`：模型判断置信度，范围 0～1
- `source_conversation`、`source_date`：来源会话和日期
- `source_report_id`、`created_reason`：来源日报和提出原因
- `status`：`pending`、`accepted` 或 `rejected`
- `created_at`、`reviewed_at`：创建和审核时间

候选不会进入模型上下文，也不会被当作用户事实使用。

### memories

用户确认后的正式长期记忆。主要字段：

- `type`、`content`、`importance`
- `confidence`：用户接受后固定为 `0.9`
- `source`
- `status`：`active`、`expired`、`archived` 或 `deleted`
- `use_count`、`last_used_at`
- `created_at`、`updated_at`

只有 `active` 记忆参与检索。归档、过期或删除是状态变更，不会由后台任务自动永久擦除。

正式记忆的来源独立保存在 `memory_sources`，相关日报证据保存在
`memory_evidence`。接受候选时，来源和证据在同一事务内继承到正式记忆。
即使原始聊天已经清理，用户仍可执行 `/memory show ID` 查看来源日期、
创建原因和最小原文依据。

## 用户命令

```text
/memory candidates
/memory edit ID 类型 新内容
/memory accept ID
/memory reject ID
/memory list
/memory show ID
/memory archive ID
/memory expire ID
/memory delete ID
```

如果接受时检测到潜在冲突，系统展示旧记忆、新候选和冲突原因，并停止写入。用户确认两条信息应同时保留时，可以显式执行：

```text
/memory accept ID force
```

`force` 只跳过本次冲突拦截，不会修改或删除旧记忆。

## Web UI

“记忆”页面同时展示：

- 待审核候选数量和候选内容。
- 候选类型、置信度及来源日期。
- 确认保存与忽略操作。
- 用户已经确认的活跃长期记忆及使用次数。
- 尚未执行每日分析的聊天日期。

如果存在未处理聊天，页面提供“立即分析未处理聊天”入口。分析在服务端
通过锁串行执行，UI 在分析期间轮询 `/api/dashboard`，完成后刷新日报、
候选和长期记忆。没有候选不一定是错误：当日报已生成但模型没有发现适合
跨天保留的信息时，候选列表应为空。

当前 Web UI 支持接受和拒绝候选；候选编辑、强制接受冲突、归档、过期和
软删除仍通过 CLI 完成。

## 候选生成规则

每日分析提示词要求模型只提取可能跨天仍有价值的信息，例如：

- 相对稳定的个人资料。
- 持续性的偏好。
- 已明确的长期目标。
- 正在推进的项目。
- 能力或技能状态。
- 值得长期参考的经验。

临时情绪、一次性安排、模型推测和没有聊天证据的内容不应成为候选。Mock 模式不会生成候选，避免测试或演示时虚构长期事实。

## 冲突处理

当前冲突检测是保守的规则实现，只拦截高信号矛盾，例如同类型记忆中出现“考研/就业”“喜欢/不喜欢”等明确对立表达。

系统不会：

- 自动覆盖旧记忆。
- 自动把旧记忆设为过期。
- 根据模糊语义自行决定哪条为真。

更复杂的语义冲突可以在未来新增检测器实现，但仍必须保留用户确认步骤。

## 检索与上下文注入

MemoryRetriever 会先判断问题是否需要个人记忆，再按问题内容选择记忆类型、提取中英文关键词，并从 SQLite 搜索正式记忆。候选排序综合考虑：

- 与当前问题的关键词相关度。
- 重要度。
- 置信度。
- 最近更新时间。

每次最多注入 5 条，并更新 `use_count` 和 `last_used_at`。一般知识问题不会无条件加载个人记忆，减少无关上下文和隐私暴露。

`MemorySearchBackend` 是检索边界。未来如果增加 embedding 或向量数据库，应新增该接口的实现，不修改 Agent、候选审核流程和正式记忆表的控制规则。

## 关键模块

| 模块 | 职责 |
| --- | --- |
| `memory/analyzer.py` | 将每日聊天分析为日报和候选记忆 |
| `memory/models.py` | 记忆类型、状态和候选数据校验 |
| `memory/candidate.py` | 候选查看、编辑、拒绝和接受用例 |
| `memory/conflict.py` | 接受前的保守冲突检测 |
| `memory/retriever.py` | 查询判断、关键词检索、排序和使用记录 |
| `memory/lifecycle.py` | 正式记忆的归档、过期和删除状态管理 |
| `memory/repository.py` | 业务持久化接口及 SQLite 适配器 |
| `memory/database.py` | 表结构、SQL 和事务 |
| `memory/migrations/` | Schema 版本升级 |
| `memory/backup.py` | SQLite 在线备份、校验和恢复 |
| `core/context.py` | 将已确认的相关记忆组装进模型上下文 |

## 当前边界

- 检索是关键词和启发式排序，不是语义向量检索。
- 冲突检测只覆盖少量高置信度规则。
- 尚无批量审核和数据导入导出。
- Web UI 尚未覆盖候选编辑、冲突强制接受和完整生命周期管理。
- CLI 的删除是软删除状态，不是不可恢复的物理删除。
- 每日分析仍可能受本地模型上下文长度和 JSON 输出质量影响。

## 验证

运行全部自动化测试：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

测试使用共享内存 SQLite，不修改真实的
`data/database/goals_assistant.db`。覆盖日报事务、候选审批、编辑与拒绝、
Evidence 原文校验、事务回滚、Memory Provenance、冲突确认、检索注入、
无关问题跳过记忆、软删除排除和 CLI 审批入口。
