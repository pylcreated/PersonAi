from __future__ import annotations

import sqlite3
from typing import List

from personal_agent.memory import database


def list_suspicious_goals() -> List[dict]:
    suspicious = []
    with database.connect_db() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        rows = cur.execute("SELECT id, title, created_at FROM goals ORDER BY id ASC").fetchall()
        for r in rows:
            title = r["title"] or ""
            if "\n" in title or "\r" in title or "/done" in title or "/" in title:
                suspicious.append({"id": r["id"], "title": title, "created_at": r["created_at"]})
    return suspicious


def delete_goals(ids: List[int]) -> None:
    if not ids:
        return
    with database.connect_db() as conn:
        cur = conn.cursor()
        cur.executemany("DELETE FROM goals WHERE id = ?", [(i,) for i in ids])
        conn.commit()


def main() -> None:
    sus = list_suspicious_goals()
    if not sus:
        print("未发现可疑目标。")
        return

    print("检测到以下可疑目标（可能由非交互输入或控制字符引入）：")
    for item in sus:
        print(f"- id={item['id']} created_at={item['created_at']} title={repr(item['title'])}")

    ans = input("是否删除这些目标？ (y/N): ").strip().lower()
    if ans == "y":
        delete_goals([item["id"] for item in sus])
        print("已删除可疑目标。")
    else:
        print("未作任何修改。")


if __name__ == "__main__":
    main()
