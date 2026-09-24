# chat-agent/tools/vector_store.py
import json
from pathlib import Path

import chromadb
from openai import OpenAI

from config import API_KEY, BASE_URL, EMBED_MODEL, VECTORS_DIR, CHUNKS_DIR
from tools.slice_knowledge import load_slice_policy, split_chunk


_client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

_chroma = chromadb.PersistentClient(path=str(VECTORS_DIR))
_collection = _chroma.get_or_create_collection(
    name="knowledge",
    metadata={"hnsw:space": "cosine"},
)


def embed(text: str) -> list:
    resp = _client.embeddings.create(model=EMBED_MODEL, input=text)
    return resp.data[0].embedding


def index_chunks_with_policy(chunks: list, policy_id: str) -> int:
    slice_policy = load_slice_policy(policy_id)
    ids, documents, metadatas, embeddings = [], [], [], []

    for item in chunks:
        if not isinstance(item, dict) or "error" in item:
            continue

        source_ref = item.get("source_ref") or {}
        conv_id = source_ref.get("conversation_id", "unknown")
        turn_index = source_ref.get("turn_index", 0)
        topic = item.get("topic", "")

        base_meta = {
            "conversation_id": str(conv_id),
            "turn_index": int(turn_index),
            "topic": str(topic),
            "quality_score": int(item.get("quality_score", 0) or 0),
            "policy_id": str(policy_id),
            "status": "current",
            "knowledge_type": str(item.get("knowledge_type", "unknown")),
            "entity_key": str(item.get("entity_key") or ""),
        }

        for suffix, text, type_, layer in split_chunk(item, slice_policy):
            uid = f"{conv_id}-{turn_index}-{suffix}"
            ids.append(uid)
            documents.append(text)
            metadatas.append({**base_meta, "type": type_, "layer": layer})
            embeddings.append(embed(text))

    if not ids:
        return 0

    _collection.upsert(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
        embeddings=embeddings,
    )
    return len(ids)


def index_file_with_policy(chunks_path: Path, policy_id: str) -> int:
    if not chunks_path.exists():
        raise FileNotFoundError(f"找不到 chunks 文件：{chunks_path}")
    chunks = json.loads(chunks_path.read_text(encoding="utf-8"))
    if isinstance(chunks, dict):
        chunks = [chunks]
    return index_chunks_with_policy(chunks, policy_id)


def search(query: str, top_k: int = 5, min_score: int = 0,
           policy_id: str = None, include_deprecated: bool = False) -> list:
    q_vec = embed(query)

    where = {}
    if min_score > 0:
        where["quality_score"] = {"$gte": min_score}
    if policy_id:
        where["policy_id"] = policy_id
    if not include_deprecated:
        where["status"] = "current"

    results = _collection.query(
        query_embeddings=[q_vec],
        n_results=top_k,
        where=where or None,
    )

    hits = []
    ids0 = results.get("ids", [[]])[0]
    docs0 = results.get("documents", [[]])[0]
    metas0 = results.get("metadatas", [[]])[0]
    dists0 = results.get("distances", [[]])[0]

    for i in range(len(ids0)):
        hits.append({
            "id": ids0[i],
            "text": docs0[i],
            "metadata": metas0[i],
            "distance": dists0[i],
        })
    return hits


def stats() -> int:
    return _collection.count()


def reset():
    global _collection
    _chroma.delete_collection("knowledge")
    _collection = _chroma.get_or_create_collection(
        name="knowledge",
        metadata={"hnsw:space": "cosine"},
    )


def update_metadata(ids: list, metadatas: list):
    if ids:
        _collection.update(ids=ids, metadatas=metadatas)


def get_by_entity_key(entity_key: str) -> list:
    results = _collection.get(where={"entity_key": entity_key})
    return results.get("ids", [])