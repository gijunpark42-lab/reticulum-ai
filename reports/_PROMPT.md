# Stock report authoring — prompt & rules

How a stock report gets created and wired into the web app. One JSON file per
company in this `reports/` folder; the **Stock Report** button on each graph node
renders it, and **Download PDF** prints it as a brokerage-style document.

> Trigger: the user types `report:<company>` (e.g. `report:NVIDIA`).

## The exact authoring prompt

Substitute the company for `[COMPANY]`:

> Act like a senior equity research analyst. Create a beginner-friendly research
> report on **[COMPANY]**. Cover: business model, revenue streams, industry trends,
> competitors, financial performance, valuation, growth drivers, risks,
> bull/base/bear cases, and final research summary. Use recent public sources,
> cite dates, separate facts from assumptions, and do not give a buy/sell
> recommendation. With this result, make a JSON file under the `reports/` folder,
> following **`reports/_TEMPLATE.json`** exactly; the file name must match the
> company's node name in the website.

## Output rules (so the app can integrate it)

- **Format:** one valid JSON file, same key structure as `_TEMPLATE.json`. Output
  pure JSON — no markdown code fences, no prose around it.
- **File name = canonical NODE name** from `company_metadata.json` (the name the
  graph uses), not the legal name. E.g. `reports/Applied Optoelectronics.json`.
  Put the full legal name inside as `"company"`, and set `"node_name"` to the
  exact node name (this is the join key the app matches on).
- **Sources:** check `transcripts/` for an existing earnings-call transcript and
  anchor on it; then web-search the latest earnings / FY results / price /
  market cap / shares / analyst targets / competitors / trends. Put a date on
  every figure. List sources in `report_meta.sources`.
- **Cross-check** key numbers for consistency before writing (e.g.
  TTM ≈ FY − oldest quarter + newest quarter).
- **Separate** dated FACTS from ASSUMPTIONS/opinion (`analyst_view`) and from the
  company's own forward-looking `company_guidance`. NO buy/sell/hold call.
- **English only** (the report renders in the web app).
- **Validate** the JSON parses. Do NOT run `graph_build.py` — reports don't touch
  the supply-chain graph.

## How the app reads it

`app.py` loads every `reports/*.json` (skipping files that start with `_`, like
this prompt's `_TEMPLATE.json`), keyed by `node_name` (else the file name). The
node-click panel shows a **Stock Report** button that renders the JSON, and a
**Download PDF** button that opens a print-ready version. A flat
`{ "Company": "plain text" }` map in `reports.json` also still works for quick
notes.
