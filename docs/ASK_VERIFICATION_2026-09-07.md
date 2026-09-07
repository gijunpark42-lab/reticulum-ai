# Ask the Graph — verification run, 2026-09-07

The four questions from the upgrade spec, asked through the real Ask tab (browser → `/api/ask/rewrite` → union retrieval → `/api/ask`) against the real graph on `next dev`.

- **Local engine** (`claude-code-local`: Claude Code CLI, Opus, max effort, no tools) — below.
- **Gemini engine** — NOT yet run with the new prompt: no Gemini key on this PC and production still runs the previous code until the change is deployed. Re-run after deploying with `ask4.js https://gijun42.com gemini` (the script lives in the session tmp folder) or locally with `GEMINI_API_KEY` in `web/.env`, and paste the second column here.

Citation chips render as bare numbers in this text export (e.g. `[10][11][12]` → `101112`).

## local (http://localhost:3000)

### 1. who has the biggest cloud compute capacity

_claude-code-local (your machine) · 46.3 s · 77.6 s · 31 snippets matched · topics: capex, guidance, backlog
intent: rank · searched: hyperscaler capex guidance 2026 · GW data center capacity commitments · data center backlog · intent: rank · searched: hyperscaler capex guidance 2026 · GW data center capacity commitments · data center backlog_

Ranking by disclosed compute/power capacity in gigawatts (the only unit that is comparable across snippets; hyperscalers that disclose only dollars are ranked separately below):

Broadcom (capacity supplied to Anthropic) — 6 GW cumulative: over 1 GW of TPU-based compute in 2026 plus another 5 GW of next-generation TPU-based compute beginning in 2027 (1 + 5 = 6) 15.
SoftBank / SB Energy — about 5 gigawatt of power generation and storage under operation or construction, with 10 gigawatt cited as a start ambition for the US Neo Cloud SPC 13.
NVIDIA — 4.25 GW initial land, power and shell secured at the Portsmouth campus to exclusively host NVIDIA Compute 19; note this sits inside the SoftBank Energy partnership, so it likely overlaps with #2 rather than adding to it.
CoreWeave — year-end active power guided to more than 1.85 gigawatts, raised from more than 1.7 gigawatts 24.
Meta — 1 GW data center in El Paso via the new BlackRock JV 5; on spend rather than GW, Meta is the largest single-company buyer in the graph at $130–145B FY2026 capex 30.
Amazon — a "very large multi-year, multi-gigawatt Trainium training commitment" for Anthropic, magnitude not quantified 22.
IREN — no total GW disclosed; sized instead by $25B–$30B FY2027 capex and three-year contracts pricing in excess of $20 million per megawatt of IT load 257.

Ranking by contracted cloud demand in dollars (backlog/RPO, for the players that do not give GW):

Microsoft — $627B commercial RPO, +99% YoY, with OpenAI Azure commitments a major component 8.
Google — backlog $514 billion, up more than $50B sequentially 14.
Amazon — $364B Q1 backlog plus a newly announced AWS–Anthropic deal of over $100B on top of it (≈ >$464B combined) 22.
Nebius — $27B over 5 years with Meta ($12B dedicated + $15B optional), plus the Microsoft capacity contract 2.
CoreWeave — FY2026 revenue $12.4–13.2 billion and exit annualized run-rate revenue $18.5–19.5 billion 24.
IREN — $4 billion ARR target behind the 2026 deployments, including $700 million of ARR from the NVIDIA cloud contract ramping in 2027 2511.

Evidence:

Broadcom 1 GW in 2026 + 5 GW next-gen from 2027 to Anthropic (Broadcom Q2 FY2026 (06-03-2026)) 15.
SB Energy ~5 GW under operation/construction and 10 GW neo-cloud ambition (SoftBank Q1 FY2027 (08-06-2026)) 13.
NVIDIA's 4.25 GW initial land-power-shell at Portsmouth via SoftBank Energy (NVIDIA Q2 FY2027 (08-26-2026)) 19; same call notes NVIDIA Compute is "fully utilized across every cloud served," with hyperscaler capex ~$800B in 2026 and $1.3T in 2027 and cloud backlog >$2T 10.
CoreWeave >1.85 GW year-end active power, capex $35–39B (CoreWeave Q2 FY2026 (08-11-2026)) 24.
Meta 1 GW El Paso BlackRock JV and "demand-constrained" posture (Meta Q2 FY2026 (07-29-2026)) 5; FY2026 capex $130–145B 30.
Amazon multi-gigawatt Trainium commitment, >$100B on top of $364B backlog (Amazon Q1 FY2026 (04-29-2026)) 22.
IREN FY2027 capex $25–30B (IREN Q4 FY2026 (08-27-2026)) 25; >$20M per MW contract pricing 7; $700M NVIDIA ARR 11.
Microsoft $627B commercial RPO (Microsoft Q3 FY2026 (04-29-2026)) 8; Google $514B backlog and Cloud revenue $24.8B +82% (Google Q2 FY2026 (07-22-2026)) 14; Nebius $27B Meta agreement (Nebius Q1 FY2026 (05-13-2026)) 2.

Gap: no snippet gives total installed or contracted gigawatts for Microsoft, Google or Amazon, so the GW list and the dollar list cannot be merged into a single ranking.

### 2. Who supplies HBM4 for NVIDIA Vera Rubin?

_claude-code-local (your machine) · 22.0 s · 53.0 s · 47 snippets matched · NVIDIA · chains: nvidia_vera_rubin, hbm_memory · topics: hbm, supply_tightness
intent: lookup · searched: HBM4 supply Vera Rubin · HBM4 allocation NVIDIA · intent: lookup · searched: HBM4 supply Vera Rubin · HBM4 allocation NVIDIA_

All three major HBM makers — Micron, Samsung and SK Hynix — supply HBM4 into NVIDIA's Vera Rubin platform, confirmed jointly at NVIDIA GTC Taipei 2026 (06-01-2026) 101112 and by NVIDIA itself, which cites "longstanding deep relationships with all three major memory suppliers" as it works to add capacity into 2027 (NVIDIA Q2 FY2027 (08-26-2026)) 1718.

By supplier, with the detail the graph carries:

Micron — HBM4 36GB 12-Hi in volume shipment in 2026, specifically designed for Vera Rubin (announced at GTC); 48GB 16-Hi sampled; already >$1 billion in HBM4 revenue with the 12-high ramp tracking 2x faster than HBM3E 1283839.
Samsung — world-first HBM4 mass production from Feb 2026 on 1c nano, ramping under multi-year supply commitments, with production-ready HBM4 capacity sold out and HBM sales guided +>3x YoY in 2026 340; named as HBM4 supplier in the Vera Rubin system 10.
SK Hynix — named as an HBM4 supplier in the Vera Rubin system 12; separately in mass production of 192 GB SOCAMM2 on 1z-nm "optimized for NVIDIA's Vera Rubin platform" (SK Hynix Q1 FY2026 (04-23-2026)) 9 — that is a module product, not HBM4.

Evidence:

Three-way HBM4 supply into Vera Rubin: NVIDIA GTC Taipei 2026 (06-01-2026) names Samsung, Micron and SK Hynix each "used in the Vera Rubin system" 101112.
NVIDIA confirms all three memory suppliers and rising memory pricing into 2027 (NVIDIA Q2 FY2027 (08-26-2026)) 1718.
Micron design-in and volumes: Micron Q2 FY2026 (03-18-2026) 12838; Micron Q3 FY2026 (06-24-2026) for >$1B HBM4 revenue and 2x ramp 39.
Samsung HBM4 first-to-mass-production and sold-out capacity: Samsung Q1 FY2026 (04-30-2026) 340.
SK Hynix Vera Rubin-optimized SOCAMM2: SK Hynix Q1 FY2026 (04-23-2026) 9.
Context on where the stacks are consumed: Vera Rubin entered production shipments in Aug 2026 and is guided to ~20% of Q3 FY2027 data center revenue (NVIDIA Q2 FY2027 (08-26-2026)) 37; packaging is TSMC CoWoS-R/CoWoS-L on 3nm 2736, with FormFactor's SmartMatrix used at "two of the three HBM makers" for final HBM4 stack test (FormFactor Q2 FY2026 (07-29-2026)) 41.

Gap: the graph does not split HBM4 allocation or share of Vera Rubin content among the three suppliers, and SK Hynix's own HBM4 volume/qualification detail for Vera Rubin is only asserted via the GTC signal.

### 3. How much capex are the hyperscalers guiding for this year?

_claude-code-local (your machine) · 21.8 s · 52.8 s · 26 snippets matched · topics: capex, guidance
intent: compare · searched: capex guidance 2026 · capital expenditure plan hyperscaler · intent: compare · searched: capex guidance 2026 · capital expenditure plan hyperscaler_

Ranked by 2026 (calendar/fiscal-year) capex guidance as stated in the graph:

Top-five hyperscalers, combined — nearly $800B in 2026 (and $1.3T in 2027), per NVIDIA's framing of the cohort 10131418
Meta — FY2026 capex guidance narrowed to $130–145B, from the prior $125–145B (bottom end raised) 6
CoreWeave — FY2026 capex raised to $35–39B 3
IREN — $25–30B for the fiscal year to June 2027 (i.e. the year now in progress, not calendar 2026) 1
Core Scientific — ~$2B capex in 2026, pre-seeding ~1 GW of new billable capacity for delivery from early 2027 12

Implied residual: $800B less Meta's midpoint ($130B + $145B) / 2 = $137.5B leaves ~$662.5B across the other four top-five hyperscalers, or ~$166B each on average — derived arithmetic, not stated in any snippet.

Evidence:

~$800B 2026 / $1.3T 2027 top-five hyperscaler capex and >$2T cloud backlog come from a single source, NVIDIA Q2 FY2027 (08-26-2026), repeated on the Microsoft, Google and Meta nodes 10131418; this is also the newest source in the set (08-26-2026).
Meta's own guidance is company-sourced: Meta Q2 FY2026 (07-29-2026), Q2 capex $31.08B including finance leases (~2x YoY), FY2026 $130–145B 6.
CoreWeave Q2 FY2026 (08-11-2026): FY2026 capex $35–39B alongside revenue $12.4–13.2B and exit ARR $18.5–19.5B 3; Q2 capex alone was $9.4B with construction in progress at $11.9B 2.
IREN Q4 FY2026 (08-27-2026): FY2027 capex ~$25B–$30B, with data center and GPU capex requirements up ~15–20% 1.
Core Scientific Q1 FY2026 (05-06-2026): ~$2B capex in 2026 12.

Gap: the graph carries no company-specific 2026 capex guidance for Microsoft, Amazon, Google or Oracle — only the aggregate top-five figure sourced from NVIDIA, so items 2–5 are the only self-reported numbers.

### 4. Which companies report supply as sold out or on allocation?

_claude-code-local (your machine) · 43.4 s · 74.3 s · 28 snippets matched · topics: supply_tightness
intent: lookup · searched: supply sold out · on allocation capacity constrained · intent: lookup · searched: supply sold out · on allocation capacity constrained_

Companies that describe their own or their inputs' supply as sold out / on allocation

Lumentum — pump lasers "remain effectively sold out for the foreseeable future," ~70-80% share, and EML supply-demand imbalance greater than 30% 24
Samsung — HBM4 capacity sold out, world-first HBM4 mass production from Feb 2026 under multi-year commitments 1
Memory/DRAM makers, reported by ASML — memory customers "say they are SOLD OUT for the remainder of the year" with limits persisting beyond 2026; memory was 51% of net system sales in Q1 6
Unimicron, Kinsus, Nan Ya PCB — ABF substrate capacity sold out, quotes +5-10% QoQ from Q2 2026, spot +30%+ 312
Amazon — Trainium2 "largely SOLD OUT," ~30% better price-performance than comparable GPUs 7
CoreWeave — "largely sold out" of near-term capacity and of prior-generation NVIDIA GPUs; signed an A100 contract extending into 2029 10149
Sandisk — bits "REMAIN ON ALLOCATION BEYOND CALENDAR 2027" as demand grows faster than supply 20
Infineon — "AI POWER ON ALLOCATION — demand strongly exceeds supply"; dedicated AI power revenue EUR 1.5B FY2026 → EUR 2.5B FY2027 24
Ibiden — "no room to allocate more capacity"; new business capped at ~20% of overall in FY2027 27
Jabil — supplier engagement is "about access, about allocation, long-term commitments"; hyperscalers "secure more than their fair share of constrained components" 2223
AT&S — T-glass shortage managed by expanding allocation from existing suppliers and qualifying new ones 8

Constrained but not stated as sold out: Coherent, where indium phosphide is "the PRIMARY CONSTRAINT on the whole business" 26; Dell, where "just about every product going through a leading node is constrained" plus ABF, T-glass and optical shortages 21; Marvell, paying ~$1B of supplier prepayments in FY2027 to buy allocation priority 11. Explicit counterexamples: Bloom Energy is "not order constrained and not capacity constrained" at 5 GW/yr 25, and Meta calls itself "DEMAND-CONSTRAINED" on compute 28.

Evidence

Lumentum pump lasers sold out, +80% YoY shipments, 3-year take-or-pay LTAs (Lumentum Q4 FY2026 (08-11-2026)) 2; EML imbalance >30%, components effectively sold out (Lumentum Q3 FY2026 (05-05-2026)) 4.
Samsung HBM4 sold out under multi-year supply commitments (Samsung Q1 FY2026 (04-30-2026)) 1.
Memory customers sold out for the remainder of the year (ASML Q1 FY2026 (04-15-2026)) 6.
ABF sold out at all three Taiwanese substrate makers; Nan Ya PCB March revenue NT$4.29B, +39% YoY (DigiTimes ABF substrate note (04-20-2026)) 312.
Trainium2 largely sold out (Amazon Q1 FY2026 (04-29-2026)) 7.
CoreWeave sold out of near-term capacity with A100/H100/H200/L40s pricing up QoQ (CoreWeave Q1 FY2026 (05-08-2026)) 10; still sold out of prior generations, A100 contract into 2029 (CoreWeave Q2 FY2026 (08-11-2026)) 149.
NAND on allocation past CY2027; TAM >$300B CY2026 to ~$500B CY2027 (Sandisk Q4 FY2026 (08-05-2026)) 20.
AI power on allocation, capacity converted from HV automotive at Dresden (Infineon Q2 FY2026 (05-06-2026)) 24.
New business capped ~20% on capacity limits (Ibiden Q1 FY2027 (08-05-2026)) 27.
HBM lead times extending, DDR4 shortages; shortages built into the FY2027 outlook (Jabil Q3 FY2026 (06-17-2026)) 2223.
T-glass allocation expansion, ABF price increases passed through (AT&S Q4 FY2026 (05-21-2026)) 8.
InP the binding constraint, output 2x YoY a quarter early (Coherent Q4 FY2026 (08-12-2026)) 26; chain-wide constraint list (Dell Q2 FY2027 (09-01-2026)) 21; ~$1B prepayments for allocation priority (Marvell Q1 FY2027 (05-27-2026)) 11.
5 GW/yr, neither order- nor capacity-constrained (Bloom Energy Q1 FY2026 (04-28-2026)) 25; demand-constrained including core business (Meta Q2 FY2026 (07-29-2026)) 28.

Gaps: the graph carries no direct "sold out" language from the DRAM makers themselves (SK Hynix, Micron) or from NVIDIA/TSMC — the memory claim comes second-hand through ASML.


Console errors: []
