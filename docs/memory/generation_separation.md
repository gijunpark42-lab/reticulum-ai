---
name: generation-separation
description: "Core principle — accelerator chains are split by investment-significant GENERATION, not aggregated; transitions are the alpha"
metadata: 
  node_type: memory
  type: project
  originSessionId: 8057d507-c93b-45cc-8380-a2bea3189aa6
---

**Chains are split by investment-significant accelerator GENERATION.** This is the project's core differentiator for a stock tool: the value is not a static snapshot of "who supplies whom," it is the **generational transition delta** — who gains content, who gets displaced, and on what timeline (e.g., HBM3E→HBM4 memory-content growth, copper→optical scale-up, CPO penetration ramping 2026→2028, attach ratio 1:2→1:4→1:8).

**Why:** User decision (2026-06-08): "세대 분리를 하자 … 정확한 정보가 애매하게 많은거보다 중요함 우리프로젝트가 이래서 다른것과 비교되는거고." Precise per-generation supply chains beat a vague aggregate. The transition IS the investment thesis.

**The pattern already in use:** `nvda_b200` = Blackwell generation, `nvidia_vera_rubin` = Rubin generation. Two NVIDIA generations in two chains → comparing them shows the delta (HBM3E vs HBM4, 800G/1.6T vs 1.6T+CPO). Extend this discipline to every vendor.

**How to apply:**
- One chain = one investment-significant generation/platform (e.g., Blackwell, Rubin, MI450/Helios, Trainium2, Trainium3, TPU v7, TPU v8t/v8i). TPU v8 training (8t) and inference (8i) variants will each be built when their supply-chain content differs.
- **Split criterion:** split when the generation transition materially shifts content or winners (CPO introduction, HBM gen jump, copper→optical, attach-ratio change, new packaging paradigm, different foundry/designer). Do NOT split trivial SKUs (minor refreshes, A100/H100 variants) — those accumulate as `contracts`/`quarterly_data` entries on the same chain.
- Each generation chain must carry the **content/spec deltas** that matter to investors: HBM capacity per unit, optical attach ratio, CPO vs pluggable mix, $ content per unit. The Goldman Sachs optical note (04-17-2026) already provides these per generation (GB300 → Rubin Ultra) and should be attached to the affected optical nodes.
- Accuracy over volume. Better a precise single-generation chain than a fuzzy multi-generation blur.

Related: [[project-state]], naming convention mirrors existing files (`nvda_b200`, `nvidia_vera_rubin`, `google_tpu_v7_ironwood`).
