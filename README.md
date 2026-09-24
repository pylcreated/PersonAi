# 协商式自适应 RAG 知识库系统 (PersonAi)

基于 LLM 与用户的**多轮协商**，动态生成知识库整理模板与切片策略，解决长对话场景下的高精度检索问题。

## 💡 项目背景

传统 RAG 系统采用固定的切片和整理策略，难以适应小说创作、学术讨论等长尾场景。本项目引入“人机协商”机制：大模型作为“知识库架构师”引导用户定义存储维度、切片策略和更新策略，并固化为可复用的 Policy，实现自适应知识管理。

## 🚀 核心特性

- **协商式状态机**：基于 LangGraph 实现多阶段协商（领域识别 → 模板定义 → 切片策略 → 更新策略 → 确认）。
- **可插拔的 Policy**：协商结果生成为 JSON 格式的 Policy，支持随时修改和版本管理。
- **动态切片与向量化**：根据协商出的策略，对 LLM 整理后的结构化知识进行细粒度切片并存入 ChromaDB。
- **用户主导的结束机制**：针对主观发散场景（如写小说），由用户决定协商何时结束；针对物理数学边界，由 AI 强制保证字段完整。
- **策略隔离检索**：RAG 检索时按 `policy_id` 和 `status` 过滤，支持历史版本回溯与复盘。

## 🛠️ 技术栈

- **大模型**：Qwen 2.5 / OpenAI 兼容接口 (Ollama / SiliconFlow)
- **编排框架**：LangGraph
- **向量库**：ChromaDB (持久化存储于 `data/vectors/`)
- **Embedding**：BGE-M3
- **解析校验**：JSON Schema (Pydantic)

## 📁 目录结构

```text
chat-agent/
├── agent/
│   ├── nodes/                # 协商状态机的各个节点 (goal, template, slice, update, confirm)
│   ├── negotiation_graph.py  # LangGraph 状态图构建
│   ├── state.py              # 协商状态定义 (NegotiationState)
│   └── tool_registry.py
├── tools/
│   ├── clean_conversation.py # 规则清洗
│   ├── organize_knowledge.py # 按模板整理
│   ├── slice_knowledge.py    # 按策略切片
│   ├── vector_store.py       # 向量入库与检索
│   └── knowledge_updater.py  # 按策略更新知识库
├── policies/                 # 协商生成的策略 (templates / slice_policies / update_policies)
├── data/                     # 运行时数据 (inbox / processed / chunks / vectors)
├── chat.py                   # 主交互程序 (REPL)
├── config.py                 # 全局配置与路径
├── storage.py                # 原始/清洗后文件的读写
└── requirements.txt
