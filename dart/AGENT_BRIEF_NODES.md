# Brief: turn the counterparties you reported into NODES + EDGES (one company per agent)

Earlier you (or a sibling agent) wrote `dart/patches/<slug>.json` for one Korean company and
listed counterparties that could not get an edge because they were not nodes. The owner has
decided: **add all of them as nodes**, and move the deal detail onto edges. You write ONE node
patch; a script applies it. You never edit `chains/` yourself.

Repo root: `C:\Users\calif\OneDrive\Desktop\earnings-ai`

## 1. Inputs
- `dart/patches/<slug>.json` — your company patch (the signals hold the numbers you need).
- The source txt(s) named in your task — re-open the sections that mention each counterparty
  (customer tables, raw-material tables, section XI contract status, notes) so every contract
  entry carries the filed amount, term and date. Do not guess; if the filing gives no figure,
  write "no specific figure".
- The chain file named in your task (the one that holds your company). Read its layer/sector
  structure: `python - <<EOF` is fine, or grep `"layer"`, `"domain"`, `"sector"`, `"sub_sector"`.

## 2. Which counterparties become nodes
INCLUDE every entity that sells goods/services TO the company or buys goods/services FROM it,
plus licensors and manufacturing/JV partners: customers (named or in the >10% table), raw-material
and equipment suppliers, outsourcing partners, EPC customers, utilities, end customers named in a
contract. Also include companies that ARE nodes elsewhere but not in this chain file (e.g. SK Hynix
for a packaging_substrate supplier) — adding them here makes the edge possible; the merged graph
folds them into the existing hub. Use the exact canonical name already in `chains/` for those.
EXCLUDE: banks, depositaries, guarantors, insurers; pure equity stakes with no trade; the
company's own subsidiaries/SPVs; construction contractors; shareholders; peers in comparison tables.

## 3. Placement — pick an EXISTING layer/domain and sector in that chain file
`layer` = the layer slug (`application, ai_models, software_infra, cloud_infra, system_integration,
compute_hardware, memory, interconnect, advanced_packaging, foundry, equipment, materials, minerals`)
or domain slug (`power, thermal, security, edge_ai`) as written in the file; `sector` = an existing
sector name in that layer (verbatim); `sub_sector` only if that sector is split. Put a customer where
its ROLE in this chain sits (a US utility buying transformers -> `power` / `Grid`; a Chinese OSAT
buying test handlers -> `advanced_packaging` or `foundry` OSAT sector, whichever exists; a wafer
supplier -> `materials`). If no sector fits, choose the closest existing one — never invent a layer.
`product` = the specific thing that flows in THIS chain, in English, e.g.
"300mm silicon wafers (SK Hynix supplier)", "UHV transformers buyer — US utility".

## 4. Edges and contracts
Direction follows the goods: supplier -> buyer. So a raw-material supplier gets an edge
`Supplier -> YourCompany`; a customer gets `YourCompany -> Customer`. Each edge carries `contracts`
entries built from the filing (label = the source label used in your company patch):
`{"source", "signal", "units", "value", "date_signed", "type", "topics"}` — `type` one of
"supply agreement" / "purchase" / "customer share" / "licence" / "EPC contract" / "JV manufacturing".
For a >10%-customer disclosure use type "customer share", `value` = the KRW amount and % of revenue,
`units` = the period ("H1 2026"). Every date with its year. ENGLISH ONLY (no Korean characters).
If the counterparty was in an earlier "skipped edges" list (target existed elsewhere), still add
the node here and the edge.

## 5. Output
Write `dart/node_patches/<slug>.json`:
```json
{
  "chain": "chains/components/power_cooling.json",
  "nodes": [{"company": "NextEra Energy", "layer": "power", "sector": "Grid", "product": "..."}],
  "edges": [{"from": "LS Electric", "to": "NextEra Energy", "relationship": "...", "contracts": [...]}]
}
```
One file, one chain. Validate: parses, no `[가-힣]`, every `layer`/`sector` exists verbatim in the
chain file, every `from`/`to` is either an existing player or in your `nodes` list. Final message:
path, node count, edge count, and anything you deliberately excluded (one line each).
