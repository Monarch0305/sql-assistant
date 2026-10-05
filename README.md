# SQL Agent Benchmark — Gold Set v1

This repository contains a small evaluation benchmark built on the Chinook sample music-store SQLite database. It contains 40 tasks: 8 lookups, 10 aggregations, 10 joins, 6 multi-step questions, and 6 traps. The questions and hand-checked reference queries live in `tasks/drafts.txt`; `eval/build_gold.py` compiles reviewed tasks into `tasks/tasks.jsonl`.

## Verify the gold set

From the project root, with the virtual environment active:

```powershell
python eval/build_gold.py
python eval/run_gold.py
```

`build_gold.py` runs the SQL in the drafts and copies only tasks marked `ok: yes` into the compiled JSONL. Check the printed results before accepting a task. Trap tasks intentionally have no executable gold query; their expected behavior is described in `notes`.

Each answerable task has an `answer_keys` array of zero-based result-column positions that the response must contain. This lets a scorer accept a concise answer when the gold query also returns useful supporting values. `gold_columns` records the corresponding SQL result-column names. Example: `join_01` requires column 0 (artist name); the album count is evidence but not required in the final response.

Text matching should ignore case and diacritics, so `Holý` and `Holy` count as the same customer name. Numeric values should use a documented tolerance; task-specific units and rounding are in the question or SQL.

## Revenue definitions

For store, customer, country, and invoice-level revenue, use `SUM(Invoice.Total)`. For track, genre, and artist sales, use `SUM(InvoiceLine.UnitPrice * InvoiceLine.Quantity)`. In this bundled Chinook database both methods total **2328.60**, and each invoice's header total matches the sum of its line items. The benchmark still states which definition applies in each task so the metric remains explicit.

## Trap scoring policy

- `trap_01`, `trap_02`, `trap_04`, and `trap_05`: expect an abstention or refusal with the missing data / read-only reason stated.
- `trap_03`: accept a clarification asking how “best” is defined, or an answer that explicitly states its metric as an assumption. An unqualified “best customer” claim is incorrect.
- `trap_06`: accept an abstention, or a forecast explicitly labeled as an estimate with assumptions. A bare future revenue figure is incorrect.

For future scoring, classify a clarification on `trap_03` and a qualified forecast on `trap_06` separately from a correct abstention. Normalize accents before comparing names.

## Scope and limitations

The data is one small sample database. The date tasks are lightly represented (one task), and results do not establish performance on other databases. Add harder tasks only in a separately labeled benchmark revision, such as v2, and report that change honestly.
