import sqlite3

con = sqlite3.connect("file:data/Chinook_Sqlite.sqlite?mode=ro", uri=True)
while True:
    q = input("sql> ").strip()
    if q in ("", "exit", "quit"):
        break
    try:
        cur = con.execute(q)
        print([d[0] for d in cur.description])
        for r in cur.fetchmany(20):
            print(r)
    except Exception as e:
        print("ERROR:", e)