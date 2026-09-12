---
name: feedback-english-ui
description: All user-facing website (Streamlit app) text must be in English
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 2f51cdb3-8ac3-496e-8363-4cab61e2c127
---

All user-facing text in the web app (app.py — button labels, captions, placeholders, tab names, empty-states) must be written in **English**, not Korean. Set as a standing convention on 2026-06-14 when the "주식리포트" button was renamed to "📊 Stock Report" (commit a8f3363).

**Why:** The product is presented in English; mixed Korean UI looks unfinished.
**How to apply:** When adding/changing any visible string in the app, write it in English. Code comments and our chat stay as-is (conversation continues in Korean — see [[user-profile]]); this rule is only about what renders on the website. See [[project-state]] for the app structure.
