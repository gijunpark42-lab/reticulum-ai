@echo off
rem Opens a Cloudflare "quick tunnel" to the local Ask runner (port 8787).
rem No account needed. The window prints a https://....trycloudflare.com address:
rem copy it into LOCAL_ASK_URL on Vercel (the address changes every time this restarts).
"%ProgramFiles(x86)%\cloudflared\cloudflared.exe" tunnel --url http://127.0.0.1:8787
pause
