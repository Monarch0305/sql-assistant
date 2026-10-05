import json, sqlite3, sys

CATS = ["lookup", "aggregation", "join", "multi_step", "trap"]
con = sqlite3.connect("file:data/Chinook_Sqlite.sqlite?mode=ro", uri=True)
tid = input("id (e.g. agg_03): ").strip()
cat = input(f"category {CATS}: ").strip()
question = input("question: ").strip()

if cat == "trap":
    notes = input("correct behavior and accepted alternatives: ").strip()
    task = {"id": tid, "category": cat, "question": question, "gold_sql": None,
            "gold_answer": None, "gold_columns": [], "answer_keys": [],
            "answerable": False, "notes": notes}
else:
    sql = input("gold_sql (one line): ").strip()
    cur = con.execute(sql)
    rows = cur.fetchall()
    columns = [d[0] for d in (cur.description or [])]
    print("\nRESULT COLUMNS:", columns)
    print(f"RESULT ({len(rows)} rows):")
    for r in rows[:15]:
        print("  ", r)
    if input("\nCorrect by eye? [y/N]: ").lower() != "y":
        sys.exit("not saved")
    raw_keys = input("Required answer column indices as JSON (e.g. [0]; blank means all): ").strip()
    answer_keys = json.loads(raw_keys) if raw_keys else list(range(len(columns)))
    if not isinstance(answer_keys, list) or any(type(i) is not int or i < 0 or i >= len(columns) for i in answer_keys):
        sys.exit(f"answer_keys must be a JSON list of valid zero-based indices; columns={columns}")
    notes = input("notes (metric definitions, tie status, accepted variants; optional): ").strip()
    task = {"id": tid, "category": cat, "question": question, "gold_sql": sql,
            "gold_answer": rows, "gold_columns": columns, "answer_keys": answer_keys,
            "answerable": True, "notes": notes}

with open("tasks/tasks.jsonl", "a", encoding="utf-8") as f:
    f.write(json.dumps(task, ensure_ascii=False) + "\n")
print("saved", tid)
