---
name: feedback_no_auto_commit
description: "Never commit or push unless the user explicitly says \"커밋해\" / \"푸시해\" (commit / push) — suggesting a commit command is fine, running it is not"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: d23fb5ad-dd34-4fd2-997f-630d12f3013f
  modified: 2026-08-27T19:45:36.935Z
---

Do NOT run `git commit` or `git push` on your own. Only when the user explicitly says
"커밋해", "푸시해", "commit", "push" (or equivalent) in that turn.

**Why:** the user said so directly (2026-08-27): "커밋 및 푸시는 내가 커밋해 푸시 해 이러기
전까지는 안했음좋겠엉". Many parallel jobs share this working tree, so an auto-commit from one
job sweeps in other jobs' half-finished work; the user wants to control when that snapshot is taken.

**How to apply:**
- Finish the work, run `graph_build.py --sync`, leave everything uncommitted.
- It is fine (and helpful) to END a report with the ready-to-paste `git add ... && git commit -m ...`
  command and to say why committing soon is a good idea (git is the only durable safety net for
  uncommitted parallel work — see [[concurrent_job_race]]). Never execute it.
- Approval to commit in one turn does not carry over to later turns.
