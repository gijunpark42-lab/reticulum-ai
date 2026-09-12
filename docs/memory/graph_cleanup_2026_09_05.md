---
name: graph-cleanup-2026-09-05
description: "2026-09-05 structural cleanup: user reversed 'add every DART counterparty as a node'; litmus test re-enforced, 107 nodes removed with deals folded into quarterly_data, 25 wrong-layer moves; revert branch pre-cleanup-2026-09-05"
metadata: 
  node_type: memory
  type: project
  originSessionId: 6cd64f41-58cf-4e4b-8b2b-771fa501e2ac
  modified: 2026-09-06T02:51:53.142Z
---

On 2026-09-05 the user asked (in English) to "verify everything" because the graph held companies
that don't belong (Bank of Korea, display panel makers) or sat in the wrong layer, and to decide
alone but keep a way back. Source of the junk: the 2026-08-29 commit `589b854` that turned all
171 counterparties from the August DART filings into nodes (the owner had said "add all of them"
at the time — this cleanup REVERSES that decision; `dart/AGENT_BRIEF_NODES.md` now carries a
SUPERSEDED note).

**What was done** (script + decision table: `utils/graph_cleanup_2026_09_05.py`, fold log next to it):
- 419 → 312 companies, 949 → 828 player cards, graph 1250 edges. 107 companies removed (banks,
  display fabs, rail/ship/EPC contractors, foreign utilities, transformer-tank steel shops, Samsung DX
  phone suppliers, distributors, related-party machine shops). Kept from the import: US utilities
  (NextEra, AEP, Xcel, Dominion, Southern, Eversource, Puget Sound), NuScale, X-Energy, MHI, Quanta
  Services, Wesco, Intersect Power, QTS, Tesla (Samsung Foundry), listed OSATs (JCET, Huatian, TFME,
  Powertech, SFA Semi, Signetics), LG Innotek, Korea Circuit, Siltronic, SK Siltron, SK gas/chemical
  captives, Wonik QnC, PSK Inc., TUC, MEC, Taiyo Holdings, Doosan Corporation, POSCO, MR, Taihan.
- **Fold rule (keep using it):** a deleted node's edge contracts became `quarterly_data` on the
  counterpart with keys `counterparty` / `counterparty_role` ("Customer X: …" / "Supplier X: …").
  145 folded, 11 re-pointed by renames, 0 data points lost (HEAD-vs-worktree audit).
- Renames to canonical parents: PTI→Powertech Technology, STATS ChipPAC→JCET, Atotech(+Korea)→MKS
  Instruments, Doosan Electronics→Doosan Corporation, Taiyo Ink Products→Taiyo Holdings,
  Siemens Industry Software→Siemens.
- Wrong-layer moves (pre-existing, not DART): SEMCO/Simmtech/AT&S/Unimicron/Ibiden → advanced_packaging;
  NVIDIA/AMD/Cerebras/Google out of `interconnect` into compute_hardware (power_semiconductor,
  neocloud, packaging_substrate); Intel → Server CPU; Marvell/Broadcom/Celestial AI/Ranovus/NVIDIA/
  Lumen re-sectored in optical_networking; Anthropic out of Neocloud; Exelon → Utilities sector.
- company_metadata.json +45 entries (all graph companies now have metadata). Side effect: the
  `enrich dart` universe gained 9 Korean names (Doosan Corp, Korea Circuit, LG Innotek, POSCO,
  PSK Inc., SFA Semi, Signetics, Taihan Cable, Wonik QnC) — POSCO Holdings filings are huge and
  mostly non-AI; user may want to drop its ticker.

**Revert:** branch `pre-cleanup-2026-09-05` = commit `6ae94db` (state before). Uncommitted:
`git checkout -- . && git clean -fd utils/`; after a commit: `git reset --hard pre-cleanup-2026-09-05`.

**Policy going forward:** DART counterparties become nodes ONLY if they pass the litmus test
("does its stock benefit from this product being built/sold?"); otherwise fold the deal into the
filer's own quarterly_data. Do not re-propose "add all counterparties". See [[feedback-integrity]],
[[naming-rules]], [[concurrent-job-race]].
