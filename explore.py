import sqlite3

con = sqlite3.connect("file:data/Chinook_Sqlite.sqlite?mode=ro", uri=True)
tables = [r[0] for r in con.execute(
    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]

print("=== TABLES, COLUMNS, LINKS, SAMPLE ROWS ===")
for t in tables:
    cols = con.execute(f"PRAGMA table_info({t})").fetchall()
    fks = con.execute(f"PRAGMA foreign_key_list({t})").fetchall()
    print(f"\n## {t}")
    print("columns:", ", ".join(f"{c[1]} ({c[2]})" for c in cols))
    for fk in fks:
        print(f"links:   {t}.{fk[3]} -> {fk[2]}.{fk[4]}")
    cur = con.execute(f"SELECT * FROM {t} LIMIT 3")
    for row in cur.fetchall():
        print("  ", row)

print("\n=== VALUE LISTS ===")
for label, sql in [
    ("Genres", "SELECT Name FROM Genre ORDER BY GenreId"),
    ("Media types", "SELECT Name FROM MediaType ORDER BY MediaTypeId"),
    ("Employee titles", "SELECT FirstName||' '||LastName||' - '||Title FROM Employee ORDER BY EmployeeId"),
]:
    print(f"\n{label}:", [r[0] for r in con.execute(sql)])