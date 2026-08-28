# Enrichment patch inbox

Enrichment jobs write their ADD-only results here as `<company>_<quarter>.json` instead of
editing `chains/` directly. `python graph_build.py` (or `python apply_patches.py`) merges every
pending patch into the chains and moves it to `applied/` as a receipt.

See the docstring in `apply_patches.py` for the file shape, and CLAUDE.md Workflow 2.
