---
name: common-fixes
description: "Recurring mistakes Opus makes when building chain skeletons, and how to fix them"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 4df4e4a9-c6f7-4bd9-99ed-01c351552f92
---

After every `build_chain_skeleton()` Opus run, always review the output for these patterns before saving or running graph_build.py.

**Why:** Opus consistently makes these mistakes despite prompt instructions. Catching them immediately is cheaper than fixing a corrupted graph later.
**How to apply:** Read the new chain JSON, grep for each pattern, fix with replace_all.

## Checklist after every skeleton build

1. **Fake sub-brand company names** — Opus creates "Samsung Memory SSD", "SK Hynix SSD", "Micron SSD", "Intel Assembly/Test (ATM)", "AWS Annapurna" etc. These are divisions, not companies. Collapse to parent.

2. **Wrong hyperscaler names** — Always check for: `"AWS"` / `"Amazon Web Services"` → `"Amazon"` (renamed repo-wide 2026-08-27), `"Microsoft Azure"` → `"Microsoft"`, `"Google Cloud"` → `"Google"`. See [[naming-rules]].

3. **"Meta AI" in ai_lab** — Opus puts "Meta AI" as a separate ai_lab player. It's a product of Meta, not a company. Rename to "Meta" and remove the self-referential edge from Meta (hyperscaler) → Meta AI.

4. **Missing `quarterly_data: []`** — Sometimes Opus omits the field entirely on some players. Check ai_lab players especially.

5. **"Arista Networks"** → `"Arista"`.

6. **"Dell Technologies"** → `"Dell"`.

7. **"Samsung Electronics"** → `"Samsung"`.

8. **Compound names** — e.g., "Sumitomo Bakelite / Ajinomoto" → should be "Ajinomoto Fine-Techno" (the ABF film maker).

## Edit tool "string not found" error

When using Edit tool on main.py's `__main__` block, always Read the file first to see the current `old_string`. The block changes each session so the old string from memory may not match.

## Enrichment-script gotcha: one company, several nodes in ONE chain

When scripting `quarterly_data` adds, a helper that appends to EVERY player matching the company name
silently writes the same signal to every node that company occupies in that chain — e.g. NVIDIA is both
`compute_hardware/Training GPU` AND `interconnect/Scale-up` in `foundry.json`, and both
`software_infra/Inference Optimization Stack` AND `system_integration/Server / Rack OEM` in `nand_flash.json`.
graph_build merges those into one node, so the merged NVIDIA carries the identical signal twice.

**Fix:** pass an explicit layer/sector for multi-node companies, or run a duplicate scan
(key = company + label + signal-prefix, counted per chain) after every enrichment and strip the
copy on the less apt node. Caught on NVIDIA Q2 FY2027 (2026-08-27) — 5 duplicate entries removed.

## Label prefix MUST equal the node name (silent duplicate-enrichment cause)

`latest_label_in_graph(name)` in `av.py` / `investing.py` matches the label's company prefix
against the node name. If they differ, the company looks NEVER-ENRICHED and gets re-pulled and
re-enriched every sync. Found 2026-08-31 by scanning every earnings label prefix against the set
of node names — 4 offenders, 51 entries:

| label prefix was | node name (canonical) | entries |
|---|---|---|
| `Arm` | `Arm Holdings` | 42 |
| `Nanya` | `Nanya Technology` | 6 |
| `Constellation` | `Constellation Energy` | 2 |
| `Resonac` | `Resonac (Showa Denko)` | 1 |

**Fix:** rename the label prefix to the node name. Safe — the label→transcript join in
`agent/corpus.py` is token-based, so `Arm Holdings Q1 FY2027` still resolves to `arm_q1_2027.txt`.
**Re-run the scan after any enrichment session** (compare every `Q[1-4] FY20xx` label prefix to the
node-name set); it is cheap and catches this before it causes a duplicate pull.

## Transcript FILENAMES must use the company slug, not the ticker

`verify_graph` reports `source_not_found` when the file is named by ticker. Fixed 2026-08-31:
`glw_q1_2026`→`corning_q1_2026`, `jci_q2_2026`→`johnsoncontrols_q2_2026`,
`klic_q2_2026`→`kulickesoffa_q2_2026`, `mmm_q2_2026_press_release`→`3m_q2_2026_press_release`.
Recovered 30 entries from fail to pass.

## Annual results need the canonical Q4 form

A label like `IQE FY2025 (05-28-2026)` has no quarter, so the canonical-label regex cannot parse it
and the entry can never be verified. Project rule: an annual report is labelled **Q4 of the year it
covers**. Fixed `IQE FY2025`→`IQE Q4 FY2025` and `Murata FY2025`→`Murata Q4 FY2025` (20 entries),
with the files renamed `*_fy2025.txt`→`*_q4_2025.txt` to match.

## Verify does not run on chains/ written directly

`graph_build.py` passes only the labels of the patches it just applied to `verify_graph.py`. A
Workflow-1 style direct write to `chains/` is therefore never audited. After any direct write, run
`python -X utf8 verify_graph.py --label "<label>"` by hand. Caught on Fabrinet Q4 FY2026, which had
4 derived dollar figures (`~$736M implied on $4.6B`) that verify correctly flagged as
`number_not_in_source` — the percentages were in the transcript, the dollar conversions were mine.
Keep figures transcript-grounded; do not write arithmetic into `figure`/`value`.

## av.py shadows PyAV (2026-09-01)
Running anything that imports faster-whisper/PyAV from the repo root fails with
`module 'av' has no attribute ...` because our `av.py` (Alpha Vantage) shadows the `av`
package. tw.py guards this (strips repo root from sys.path before importing whisper);
any new script that touches PyAV needs the same guard, or run it from another cwd.

## Claude bg tasks get killed under memory pressure (2026-09-01)
This 16GB machine runs several Claude sessions; harness background tasks (whisper, big
downloads) get killed with "system is running low on memory". Fix: launch heavy jobs as
DETACHED OS processes (PowerShell Start-Process ... -RedirectStandardOutput log) and watch
the log with a Monitor. Also: never run a multi-GB download and whisper in parallel, and
keep call audio in C:/Users/calif/tw_audio (outside OneDrive — sync churn was part of it).
