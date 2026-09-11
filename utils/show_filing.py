"""Read a saved SEC filing (transcripts/edgar/*.txt) safely, page by page.

Why this exists: 8-K exhibits are saved as ONE very long line (tens of thousands of characters). Editor-style
readers (and the Read tool) cut long lines, so part of the filing would silently go unread. This prints the file
wrapped to 160 columns and in pages of 25,000 characters, and tells you how many pages there are.

    python -X utf8 utils/show_filing.py transcripts/edgar/CRDO_10-K_2026-06-15_supplychain.txt      # page 1
    python -X utf8 utils/show_filing.py transcripts/edgar/CRDO_10-K_2026-06-15_supplychain.txt 2    # page 2

Rule (enrich edgar): read every page until "=== END OF FILE ===".
"""
import sys
import textwrap

path = sys.argv[1]
page = int(sys.argv[2]) if len(sys.argv) > 2 else 1
PAGE_CHARS = 25000

text = open(path, encoding="utf-8").read()

# 1) wrap long lines so nothing is cut
lines = []
for raw in text.splitlines():
    if len(raw) <= 160:
        lines.append(raw)
    else:
        lines.extend(textwrap.wrap(raw, 160, break_long_words=False, break_on_hyphens=False) or [""])

# 2) group the lines into pages of about 25,000 characters
pages, current, size = [], [], 0
for line in lines:
    if size + len(line) + 1 > PAGE_CHARS and current:
        pages.append(current)
        current, size = [], 0
    current.append(line)
    size += len(line) + 1
pages.append(current)

print(f"=== {path} | page {page} of {len(pages)} | {len(text):,} chars total ===")
print("\n".join(pages[page - 1]))
if page < len(pages):
    print(f"=== MORE: run again with page {page + 1} ===")
else:
    print("=== END OF FILE ===")
