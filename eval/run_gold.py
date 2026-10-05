import json, sqlite3

con = sqlite3.connect("file:data/Chinook_Sqlite.sqlite?mode=ro", uri=True)
for line in open("tasks/tasks.jsonl", encoding="utf-8"):
    t = json.loads(line)
    print(f"\n[{t['id']}] {t['question']}")
    if not t["answerable"]:
        print("  TRAP:", t["notes"])
        continue
    rows = con.execute(t["gold_sql"]).fetchall()
    print("  SQL:", t["gold_sql"])
    print("  ->", rows[:10])