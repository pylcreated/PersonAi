# chat-agent/chat.py
import sys
import uuid
import json
from datetime import datetime

from openai import OpenAI

from config import (
    API_KEY, BASE_URL, MODEL_NAME, SYSTEM_PROMPT,
    PROCESSED_DIR, CHUNKS_DIR, INBOX_DIR, SLICE_POLICIES_DIR,
)
from storage import save_raw, load_raw, save_processed
from agent.tool_registry import TOOLS
from tools.organize_knowledge import organize_conversation
from tools.vector_store import (
    index_file_with_policy,
    search as vs_search,
    stats as vs_stats,
    reset as vs_reset,
)


client = OpenAI(api_key=API_KEY, base_url=BASE_URL)


# ================= 会话状态 =================
class ChatSession:
    def __init__(self):
        self.conversation_id = self._gen_id()
        self.created_at = datetime.now().isoformat(timespec="seconds")
        self.updated_at = self.created_at
        self.title = ""
        self.messages = []
        self.policy_id = None
        self._add_system()

    @staticmethod
    def _gen_id():
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        return f"local-{ts}-{uuid.uuid4().hex[:6]}"

    def _add_system(self):
        self.messages.append({
            "role": "system",
            "content": SYSTEM_PROMPT,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        })

    def add_user(self, content: str):
        self.messages.append({
            "role": "user",
            "content": content,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        })
        self.updated_at = datetime.now().isoformat(timespec="seconds")
        if not self.title:
            self.title = content[:30]

    def add_assistant(self, content: str):
        self.messages.append({
            "role": "assistant",
            "content": content,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        })
        self.updated_at = datetime.now().isoformat(timespec="seconds")

    def to_dict(self):
        return {
            "source": "local",
            "conversation_id": self.conversation_id,
            "title": self.title or "未命名对话",
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "policy_id": self.policy_id,
            "messages": self.messages,
        }


# ================= 帮助 =================
def print_help():
    print("""
可用命令：
  /help               显示帮助
  /id                 显示当前会话 ID
  /save               保存当前会话到 data/inbox/
  /clean [id]         清洗指定会话，存入 data/processed/
  /negotiate          进入协商，让 AI 引导你定义模板和策略（用户决定何时结束）
  /organize [id]      使用当前协商策略整理
  /index [id]         向量化入库指定会话
  /sync               一键 save → clean → organize → index
  /search <查询>      手动检索向量库
  /rag <问题>         基于知识库回答问题
  /vstats             查看向量库条目数
  /vreset             清空向量库（慎用）
  /list               列出 data/inbox/ 中所有会话 ID
  quit / exit         退出
""")


# ================= 保存 =================
def do_save(session: ChatSession):
    try:
        save_raw(session.to_dict())
        print(f"✅ 已保存到 data/inbox/：{session.conversation_id}")
    except Exception as e:
        print(f"❌ 保存失败：{e}")


# ================= 清洗 =================
def do_clean(conv_id: str) -> bool:
    try:
        raw = load_raw(conv_id)
        cleaned = TOOLS["clean_conversation"]["function"](raw)
        # 把 policy_id 透传到清洗结果里
        cleaned["policy_id"] = raw.get("policy_id")
        save_processed(cleaned)
        turns = cleaned.get("turns", [])
        print(f"✅ 已清洗：{conv_id}（{len(turns)} 轮）")
        return True
    except FileNotFoundError:
        print(f"❌ 找不到原始对话：{conv_id}")
        return False
    except Exception as e:
        print(f"❌ 清洗失败：{e}")
        return False


# ================= 协商 =================
def handle_negotiation(session: ChatSession):
    from agent.state import init_state
    from agent.nodes import (
        goal_node, template_node, slice_node,
        update_node, confirm_node, finalize_node,
    )

    # 取最近一条 user 消息作为需求起点
    last_user = None
    for m in reversed(session.messages):
        if m["role"] == "user":
            last_user = m["content"]
            break
    if not last_user:
        print("❌ 请先输入一条需求，例如：我要写小说")
        return

    state = init_state(last_user, session.conversation_id)
    state["history"].append({"role": "user", "content": last_user})

    nodes = {
        "goal": goal_node.run,
        "template": template_node.run,
        "slice": slice_node.run,
        "update": update_node.run,
        "confirm": confirm_node.run,
        "finalize": finalize_node.run,
    }

    print("\n=== 协商开始（输入 取消 可终止） ===")
    while state["phase"] != "done":
        phase = state["phase"]
        if phase not in nodes:
            break

        # 记录执行前的阶段，用于疑问句回退判定
        phase_before = state["phase"]

        # 执行当前节点
        state = nodes[phase](state)

        if state["phase"] == "done":
            break

        last = state["history"][-1] if state["history"] else None
        if last and last["role"] == "assistant":
            print(f"\nAI：{last['content']}")
            try:
                answer = input("你：").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n协商已取消")
                return
            if answer.lower() in ("取消", "quit", "exit"):
                print("协商已取消")
                return
            state["history"].append({"role": "user", "content": answer})

            # ================= 核心防御机制 =================
            # 如果用户输入是一个疑问句，而 AI 自作主张推进了阶段
            # 强制把状态退回到之前，直到用户明确说“确认”为止
            is_question = any(q in answer for q in ["?", "？", "什么是", "怎么", "为什么", "多久"])
            if is_question and state["phase"] != phase_before:
                state["phase"] = phase_before  # 强制回退！
                state["history"].append({
                    "role": "user",
                    "content": "（系统提示：用户刚才是在提问，并未确认结束。请先解释清楚，不得直接进入下一步。）"
                })
            # =================================================

    if state.get("policy_id"):
        session.policy_id = state["policy_id"]
        print(f"\n✅ 协商完成，策略 ID：{state['policy_id']}")
        print("接下来可以使用 /sync 一键保存并整理。")
    else:
        print("\n⚠️  未生成策略")


# ================= 整理 =================
def do_organize(conv_id: str, policy_id: str = None) -> bool:
    if not policy_id:
        print("❌ 缺少 policy_id，请先 /negotiate")
        return False

    processed_path = PROCESSED_DIR / f"{conv_id}.json"
    if not processed_path.exists():
        print(f"❌ 找不到清洗后的文件，请先 /clean：{conv_id}")
        return False

    try:
        cleaned = json.loads(processed_path.read_text(encoding="utf-8"))
        results = organize_conversation(cleaned, policy_id)
        CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
        out_path = CHUNKS_DIR / f"{conv_id}.json"
        out_path.write_text(
            json.dumps(results, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"✅ 已整理：{conv_id}（{len(results)} 条）")
        return True
    except Exception as e:
        print(f"❌ 整理失败：{e}")
        return False


# ================= 入库 =================
def do_index(conv_id: str, policy_id: str = None) -> bool:
    if not policy_id:
        print("❌ 缺少 policy_id")
        return False
    try:
        path = CHUNKS_DIR / f"{conv_id}.json"
        n = index_file_with_policy(path, policy_id)
        print(f"✅ 入库 {n} 条，当前向量库共 {vs_stats()} 条")
        return True
    except FileNotFoundError:
        print(f"❌ 找不到 chunks 文件：{conv_id}")
        return False
    except Exception as e:
        print(f"❌ 入库失败：{e}")
        return False


# ================= 一键流水线 =================
def do_sync(session: ChatSession):
    if not session.policy_id:
        print("❌ 当前会话没有绑定策略，请先 /negotiate")
        return
    conv_id = session.conversation_id
    print("▶ 1/4 保存...")
    do_save(session)
    print("▶ 2/4 清洗...")
    if not do_clean(conv_id):
        return
    print("▶ 3/4 整理...")
    if not do_organize(conv_id, session.policy_id):
        return
    print("▶ 4/4 入库...")
    do_index(conv_id, session.policy_id)
    print("\n✅ /sync 完成")


# ================= 检索 =================
def do_search(query: str, top_k: int = 5, policy_id: str = None):
    try:
        hits = vs_search(query, top_k=top_k, policy_id=policy_id)
        if not hits:
            print("（没有命中）")
            return
        print(f"命中 {len(hits)} 条：\n")
        for i, h in enumerate(hits, 1):
            meta = h["metadata"]
            print(f"[{i}] type={meta.get('type')} topic={meta.get('topic')} "
                  f"layer={meta.get('layer')} dist={h['distance']:.4f}")
            print(f"    {h['text'][:120]}\n")
    except Exception as e:
        print(f"❌ 检索失败：{e}")


# ================= RAG 问答 =================
RAG_PROMPT_TEMPLATE = """你是一个知识库助手。请严格基于下面【知识库】的内容回答用户问题。

规则：
1. 只使用【知识库】中的信息，不要补充外部知识。
2. 如果【知识库】中没有相关内容，直接回答："知识库中没有相关信息。"
3. 回答要简洁清晰，不要编造。

【知识库】
{context}

【用户问题】
{question}
"""


def do_rag(query: str, top_k: int = 5, policy_id: str = None):
    try:
        hits = vs_search(query, top_k=top_k, min_score=0, policy_id=policy_id)
        if not hits:
            print("AI：知识库中没有相关信息。\n")
            return

        context_parts = []
        for i, h in enumerate(hits, 1):
            topic = h["metadata"].get("topic", "")
            context_parts.append(f"[{i}] [{topic}] {h['text']}")
        context = "\n".join(context_parts)

        prompt = RAG_PROMPT_TEMPLATE.format(context=context, question=query)

        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            stream=True,
        )

        print("AI：", end="", flush=True)
        full = ""
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                piece = chunk.choices[0].delta.content
                full += piece
                print(piece, end="", flush=True)
        print("\n")

        print("── 来源 ──")
        for i, h in enumerate(hits, 1):
            meta = h["metadata"]
            print(f"[{i}] topic={meta.get('topic')} conv={meta.get('conversation_id')} "
                  f"policy={meta.get('policy_id')}")
    except Exception as e:
        print(f"❌ RAG 失败：{e}")


# ================= 会话列表 =================
def do_list():
    files = sorted(INBOX_DIR.glob("**/*.json"))
    if not files:
        print("（data/inbox/ 为空）")
        return
    print(f"共 {len(files)} 个会话：")
    for f in files:
        print(f"  - {f.stem}")


# ================= 命令分发 =================
def handle_command(user_input: str, session: ChatSession) -> bool:
    parts = user_input.split(maxsplit=1)
    cmd = parts[0].lower()

    if cmd == "/help":
        print_help()
    elif cmd == "/id":
        print(f"当前会话 ID：{session.conversation_id}")
    elif cmd == "/save":
        do_save(session)
    elif cmd == "/clean":
        conv_id = parts[1].strip() if len(parts) > 1 else session.conversation_id
        do_clean(conv_id)
    elif cmd == "/negotiate":
        handle_negotiation(session)
    elif cmd == "/organize":
        conv_id = parts[1].strip() if len(parts) > 1 else session.conversation_id
        do_organize(conv_id, session.policy_id)
    elif cmd == "/index":
        conv_id = parts[1].strip() if len(parts) > 1 else session.conversation_id
        do_index(conv_id, session.policy_id)
    elif cmd == "/sync":
        do_sync(session)
    elif cmd == "/search":
        if len(parts) < 2:
            print("用法：/search <查询>")
        else:
            do_search(parts[1].strip(), policy_id=session.policy_id)
    elif cmd == "/rag":
        if len(parts) < 2:
            print("用法：/rag <问题>")
        else:
            do_rag(parts[1].strip(), policy_id=session.policy_id)
    elif cmd == "/vstats":
        print(f"向量库共 {vs_stats()} 条")
    elif cmd == "/vreset":
        confirm = input("确认清空向量库？输入 yes 继续：").strip().lower()
        if confirm == "yes":
            vs_reset()
            print("✅ 向量库已清空")
        else:
            print("已取消")
    elif cmd == "/list":
        do_list()
    else:
        print(f"未知命令：{cmd}，输入 /help 查看可用命令")
    return True


# ================= LLM 调用 =================
def call_llm(session: ChatSession) -> str:
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": m["role"], "content": m["content"]}
            for m in session.messages
        ],
        stream=True,
    )

    print("AI：", end="", flush=True)
    full_content = ""
    for chunk in response:
        if chunk.choices and chunk.choices[0].delta.content:
            piece = chunk.choices[0].delta.content
            full_content += piece
            print(piece, end="", flush=True)
    print("\n")
    return full_content


# ================= 主循环 =================
def main():
    print(f"聊天机器人已启动（模型：{MODEL_NAME}）")
    print(f"接口地址：{BASE_URL}")
    print("输入 'quit' 或 'exit' 退出，Ctrl+C 强制退出")
    print("输入 /help 查看命令")
    print("⚠️  手动保存模式：只有输入 /save 才会保存本次会话\n")

    session = ChatSession()
    print(f"当前会话 ID：{session.conversation_id}\n")

    while True:
        try:
            user_input = input("你：").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！（未保存，如需保存请用 /save）")
            sys.exit(0)

        if not user_input:
            continue

        clean_input = user_input.strip().lower()
        if clean_input in ("quit", "exit", "/quit", "/exit", "q"):
            if session.policy_id:
                print("检测到已协商策略，自动执行 /sync ...")
                do_sync(session)
            else:
                print("再见！（未保存，如需保存请用 /save）")
            break

        if user_input.startswith("/"):
            handle_command(user_input, session)
            continue

        session.add_user(user_input)

        try:
            answer = call_llm(session)
            session.add_assistant(answer)

            # 协商后自动保存
            if session.policy_id:
                do_save(session)
        except Exception as e:
            print(f"\n❌ 调用 LLM 失败：{e}\n")
            session.messages.pop()


if __name__ == "__main__":
    main()