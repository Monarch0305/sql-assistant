# SQL Agent Benchmark — Gold Set v1

This repository contains a small evaluation benchmark built on the Chinook sample music-store SQLite database. It contains 40 tasks: 8 lookups, 10 aggregations, 10 joins, 6 multi-step questions, and 6 traps. The questions and hand-checked reference queries live in `tasks/drafts.txt`; `eval/build_gold.py` compiles reviewed tasks into `tasks/tasks.jsonl`.

## Run the assistant

The project uses Groq by default. Put `GROQ_API_KEY` in `.env` (never commit or share
that file), then activate the virtual environment and run:

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

The assistant gives the model one `run_sql` tool. Python executes the requested
statement against SQLite in read-only mode, gives the model the database's table
and column names, and sends bounded results back for a short explanation. The SQL
runner denies database writes and schema changes, blocks file/extension functions,
limits SQL size and SQLite work, caps output to 100 rows and 256 KiB, and the agent
allows at most four SQL tool calls per question. These are safeguards for this
local demo, not a complete security review for hosting an untrusted public service.
`LLM_PROVIDER` currently
supports `groq`; `GROQ_MODEL` can override the default model.

## Run the web version

The FastAPI app serves a small browser chat page and a JSON API. For local use,
activate the virtual environment, install dependencies, and run:

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn web:app --reload
```

Open `http://127.0.0.1:8000` for the project introduction, then choose **Try the
Chinook demo** to open the assistant at `/assistant`. The API endpoint is
`POST /api/ask`; FastAPI's interactive API page is at
`http://127.0.0.1:8000/docs`.

After an answer, the **Reports** panel appears. Each successful question is added
to the active report in this browser tab. Choose **Print current report** to save
a snapshot and open the browser print dialog (choose **Save as PDF** there).
Later questions continue adding to that same report; printing again creates a
new version while keeping earlier versions available in the panel. Choose
**New report** to start a separate collection of questions. Each report includes
its questions, answers, SQL, and returned result tables, with CSV downloads for
each query result. Report contents stay in browser memory and are cleared when
the tab is refreshed or closed; they are not sent to the server or saved in the
database. The session accepts up to 20 questions to limit browser memory use.

The browser sends only the question. The server reads `GROQ_API_KEY` from the
environment and calls Groq; it never sends the key to the browser. `.env.example`
shows the variable names without containing a real credential. For a hosting
service, add `GROQ_API_KEY` in its server-side environment/secrets settings and
use a start command such as `uvicorn web:app --host 0.0.0.0 --port $PORT` (adapt
the port syntax to the selected host). Do not use `--reload` for deployment.

## Deploy on Vercel

Vercel can run this FastAPI app together with its two pages and bundled SQLite
database. The `main.py`, `vercel.json`, and `.python-version` files provide the
Vercel entry point, file bundle, and Python version. Import the GitHub
repository in Vercel and deploy it with the FastAPI framework preset. Netlify's
drag-and-drop publishing is for static files; it would not run this Python API.

In Vercel, set `GROQ_API_KEY` under **Project Settings → Environment Variables**
for **Production**. Put the value directly into Vercel's secret field; do not
put it in HTML, GitHub, screenshots, or chat. Add `GROQ_MODEL` only to override
the default. Redeploy after adding or changing variables. The local `.env` file
is ignored by Git.

Before sharing the URL, open **Firewall → Configure → New Rule** and create a
rate limit for request path `/api/ask`, counted by IP. Start with 3 requests per
minute per IP and the default 429 response. This platform rule runs before the
Python function; an in-memory counter in a serverless app would not be a
reliable global limit. Watch Vercel Firewall traffic and Groq usage after
sharing. IP limits reduce casual abuse but cannot guarantee a maximum bill if
requests come from many IP addresses.

The app also limits questions to 2,000 characters, rejects unexpected JSON
fields, allows at most two SQL tool calls per web request, caps generated
completion tokens, disables automatic SDK retries, and keeps database queries
read-only with bounded work and output. These controls reduce risk but cannot
make a public LLM app abuse-proof. Check Groq's current account and model limits
in the Groq console before and after sharing.

## Measure the agent

Run the labeled benchmark with:

```powershell
python eval/run_eval.py
```

The default runs all 40 tasks, which can use multiple model calls per question.
Start with a small run to limit usage:

```powershell
python eval/run_eval.py --ids look_01,join_05
```

List available IDs without calling the model with `python eval/run_eval.py --list`.
You can also use `--category lookup --limit 2` to run a small category sample.
Each run writes a timestamped JSON report in `results/`.
`answer_value_accuracy` checks whether the final answer
states the required gold values. `answerable_tasks_with_sql_result` counts tasks
where at least one query returned rows. `trap_policy_accuracy` applies simple
checks to refusal/clarification text. The trap metric is a first-pass heuristic
and should be reviewed alongside the detailed report; it is not a semantic judge.
Numeric answer values use an absolute tolerance of 0.011, and text matching
ignores case and accents.

To apply updated scoring rules to an old report without calling the model again,
run:

```powershell
python eval/rescore_report.py results/eval_YYYYMMDD_HHMMSS.json
```

This writes a separate `_rescored.json` file and preserves the original report.

## Review or rebuild the gold set

From the project root, with the virtual environment active:

```powershell
python eval/build_gold.py
python eval/run_gold.py
```

`build_gold.py` rewrites `tasks/tasks.jsonl` from `tasks/drafts.txt`; inspect the
drafts before running it. `run_gold.py` only displays the reference answers.

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
