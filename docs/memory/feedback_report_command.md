---
name: feedback-report-command
description: "\"report:<company>\" trigger — reproduce the exact AAOI equity-research-report workflow + write reports/<node-name>.json"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 751bd453-e938-45be-af7d-eb3811d9f077
---

When the user types `report:<company>` (e.g. `report:NVIDIA`), run the SAME workflow first used for AAOI on 2026-06-14, driven by this EXACT prompt (substitute the company name for `[AAOI]`):

> Act like a senior equity research analyst. Create a beginner-friendly research report on [AAOI]. Cover: business model, revenue streams, industry trends, competitors, financial performance, valuation, growth drivers, risks, bull/base/bear cases, and final research summary. Use recent public sources, cite dates, separate facts from assumptions, and do not give a buy/sell recommendation. with this result, make a json file that contains this under the reports folder, the name must match the company name in the website

**Why:** The user wants a repeatable one-keyword command to generate consistent stock-research reports for any company, saved as a standalone JSON the web app can wire to the graph node.

**How to apply (the steps we used):**
- **Filename = canonical NODE name** from `company_metadata.json` (the name the graph/website uses), NOT the legal name. Save to `reports/<NodeName>.json` (e.g. `reports/Applied Optoelectronics.json`); store the full legal name inside as `"company"`. See [[naming_rules]].
- **Primary sources first:** check `transcripts/` for an existing earnings-call transcript for that company and use it as the anchor source; then WebSearch/WebFetch for the latest earnings, FY results, price/market-cap/shares, analyst targets, competitors, and industry trends. Cite dates on every figure.
- **Cross-check key numbers** for internal consistency before writing (e.g. TTM ≈ FY − oldest quarter + newest quarter; reconcile net loss the same way).
- **Keep the JSON section set consistent:** report_meta (report_date, data_cutoff, no-buy/sell disclaimer, facts-vs-assumptions note, dated sources list), beginner_glossary, company_snapshot, business_model, revenue_streams, industry_trends, competitors, financial_performance (FY + latest quarter + TTM + balance sheet + company forward guidance, clearly labeled), valuation (price/mktcap/shares/multiples/analyst targets + dispersion note), growth_drivers, risks, scenarios (bull/base/bear), final_research_summary (what_is_fact vs what_is_assumption + what_to_watch).
- **Rules:** beginner-friendly (define every jargon term in the glossary); separate FACTS (dated) from ASSUMPTIONS/opinion and from company forward-looking guidance; NO buy/sell/hold recommendation. Report content in **English** (the report renders in the web app → [[feedback_english_ui]]).
- **Validate** the JSON parses (PowerShell `ConvertFrom-Json`). Do **NOT** run `graph_build.py` — reports don't touch the chain graph.
- Finish with a tight chat summary: headline facts + the honest valuation read + a Sources list. Offer optional follow-ups (Korean version, drop a short markdown into `reports.json` map, run another ticker).
