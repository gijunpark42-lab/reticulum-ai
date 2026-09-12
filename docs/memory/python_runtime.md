---
name: python-runtime
description: How to run Python scripts on this Windows machine
metadata: 
  node_type: memory
  type: reference
  originSessionId: 4df4e4a9-c6f7-4bd9-99ed-01c351552f92
---

`python` and `python3` commands do NOT work in PowerShell on this machine.

Use the full path:
```powershell
& "C:\Users\calif\AppData\Local\Python\bin\python.exe" main.py
```

Always `cd` to the project directory first:
```powershell
cd "C:\Users\calif\Desktop\earnings-ai"; & "C:\Users\calif\AppData\Local\Python\bin\python.exe" main.py
```

**Why:** Python is installed at a non-standard path not on the system PATH.
**How to apply:** Every time a Python script needs to run, use the full path above.
