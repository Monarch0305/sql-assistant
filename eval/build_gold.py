import json, re, sqlite3

con = sqlite3.connect("file:data/Chinook_Sqlite.sqlite?mode=ro", uri=True)
KEYS = ["id", "category", "question", "sql", "answer_keys", "notes", "ok"]

def parse(text):
    tasks = []
    for block in re.split(r"^---\s*$", text, flags=re.M):
        if not block.strip():
            continue
        t, key = {}, None
        for line in block.strip().splitlines():
            m = re.match(r"^(\w+):\s?(.*)$", line)
            if m and m.group(1) in KEYS and not line.startswith(" "):
                key = m.group(1)
                t[key] = m.group(2).strip()
            elif key:
                t[key] += " " + line.strip()
        tasks.append(t)
    return tasks

built, pending, errors = [], [], []
for t in parse(open("tasks/drafts.txt", encoding="utf-8").read()):
    tid, trap = t["id"], t.get("category") == "trap"
    print(f"\n[{tid}] {t['question']}")
    if trap:
        print("  TRAP:", t.get("notes", ""))
        rows, columns = None, []
    else:
        if not t.get("sql"):
            print("  (no SQL yet)")
            pending.append(tid)
            continue
        try:
            cur = con.execute(t["sql"])
            columns = [d[0] for d in (cur.description or [])]
            rows = cur.fetchall()
            answer_keys = json.loads(t.get("answer_keys", "[]"))
            if not isinstance(answer_keys, list) or any(type(i) is not int or i < 0 or i >= len(columns) for i in answer_keys):
                raise ValueError(f"answer_keys must be a JSON list of zero-based result column indices; columns={columns}")
        except Exception as e:
            print("  ERROR:", e)
            errors.append(tid)
            continue
        print("  SQL:", t["sql"])
        print("  result columns:", columns, "required answer columns:", [columns[i] for i in answer_keys])
        print(f"  -> {len(rows)} rows:", rows[:10])
    if t.get("ok", "").lower() != "yes":
        print("  (pending: not marked ok)")
        pending.append(tid)
        continue
    built.append({
        "id": tid, "category": t["category"], "question": t["question"],
        "gold_sql": None if trap else t["sql"],
        "gold_answer": rows, "gold_columns": columns,
        "answer_keys": [] if trap else answer_keys,
        "answerable": not trap, "notes": t.get("notes", ""),
    })

with open("tasks/tasks.jsonl", "w", encoding="utf-8") as f:
    for b in built:
        f.write(json.dumps(b, ensure_ascii=False) + "\n")

print(f"\nBUILT {len(built)} | PENDING {len(pending)} | ERRORS {len(errors)} {errors}")
