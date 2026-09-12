---
name: project-stock-shorts
description: "Sibling project Desktop/stock-shorts — automated TikTok/Reels factory using earnings-ai data; v2 motion renderer working, SK hynix video shipped"
metadata: 
  node_type: memory
  type: project
  originSessionId: fc55431c-0d9a-48a4-b3fa-864f65a36aec
---

`C:\Users\calif\OneDrive\Desktop\stock-shorts\` (sibling of earnings-ai, READ-ONLY on it).
Workflow: user says "make a short for X" → Claude writes `scripts/<slug>.json` from
earnings-ai data (+ yfinance valuation via market.py, WebSearch context OK) → `python -X utf8
make_short.py scripts/<slug>.json` → `output/<slug>.mp4` + caption txt. User only posts.

**v2 spec (2026-06-11, user-locked):** English, en-US-AndrewMultilingualNeural at rate +20%;
TikTok-style pop-in motion (motion.py streams frames via imageio-ffmpeg, anims pop/slam/fade,
Ken Burns base zoom); info-DENSE dark cards; 9-10 scenes ~55-65s; **NO "not financial advice"
anywhere** (user removed it explicitly); no BGM (user adds in-app). Card types: title/chain/
facts/quote/roadmap/signal/evidence/chart/outro. The differentiator cards: roadmap (generation
transitions), evidence (cross-company shortage signals from the merged graph), quote (mgmt
supply statements). First video shipped: sk_hynix.mp4 63.6s.

**APPROVED + DAILY CADENCE (2026-06-11): user said "좋다" to the v2 sk_hynix video and will
produce ONE COMPANY PER DAY going forward.** The full step-by-step recipe is written in
stock-shorts/CLAUDE.md → "DAILY PRODUCTION PLAYBOOK" — follow it verbatim when the user names
a company: data pull (neighbors/latest_signals/metrics/timelines-cross-rows/market.stats) →
angle = what generic finance TikTok can't say (transition timing, capacity dates, mgmt supply
quotes, cross-company squeeze evidence) → 10-scene arc, ~150-160 words total → render → frame
QA (₩ glyphs, emoji overlap, logos) → deliver mp4 + caption. Outro CTA teases the NEXT
company — check the previous script's outro before picking content.

Gotchas: ₩ needs Malgun fallback (`_value_font` in cards.py); Kwak Noh-jung has no Wikipedia
photo → monogram fallback (drop a real photo at assets/person_kwak_noh_jung.png to override);
clearbit logos sometimes 403 → favicon 48px fallback (small but fine in pills); OneDrive can
lock the _work_ dir (rmtree ignore_errors); console prints with ₩/→ need `python -X utf8`.
Narration pacing: Andrew at +20% ≈ 2.45 words/sec — ~150 words ≈ 60s with 10×0.4s pads.
Related: [[project-state]], [[user-profile]]
