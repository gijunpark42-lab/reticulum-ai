### Workflow 2c — US companies via Alpha Vantage (`enrich us`)

US-listed names (NASDAQ/NYSE ticker in `company_metadata.json`, 102 companies) get their full
earnings-call transcript from Alpha Vantage instead of a hand-found Motley Fool URL. `av.py` mirrors
`dart.py`: `sync` → `pending` → enrich → `graph_build.py --sync` → `done`.

**Trigger: the user says `enrich us`.** That means run the whole loop for every new call:
1. `python av.py sync` — reads the earnings calendar, finds OUR companies that reported since the
   last sync, and pulls each transcript that Alpha Vantage has posted. Prints `saved` / `waiting`
   (reported, transcript not up yet — retried next sync, usually the next morning) / `skip`
   (already in `transcripts/` from the Motley Fool days) / `QUOTA` (25 requests/day spent — the
   rest carries over to tomorrow). If a call is `waiting` and the user needs it today, fall back to
   the Motley Fool paste (Workflow 2) under the same label.
2. `python av.py pending` — the queue. Enrich every row (Workflow 2, all four jobs + JOB 5 tags),
   reading the whole file. Never re-enrich a file that is not in the queue.
3. `python graph_build.py --sync` (runs `verify_graph.py` on the labels just applied — read its
   `[fail]`/`[warn]` lines), then `python av.py done`.
4. Report per company: label, what was added, verify result.
If the queue is empty after `sync`, say so and stop.

File format `transcripts/av/<slug>_q<N>_<year>.txt`: `SOURCE:` / `CALL DATE:` / `QUARTER:` /
`# source label:` header (use that label verbatim), then one paragraph per speaker turn,
`Speaker (Title): text`. It is the whole call — prepared remarks and every analyst question.
The quarter in the label is the company's FISCAL quarter, derived from the company's latest label
already in the graph (+1), so labels stay consistent with history (`NVIDIA Q3 FY2027 (…)`).
Manual pull: `python av.py fetch NVDA 2027Q3 --date 2026-11-19`; `python av.py calendar` lists
upcoming calls for our companies.

