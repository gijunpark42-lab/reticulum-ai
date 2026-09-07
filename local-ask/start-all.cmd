@echo off
rem Double-click to start BOTH pieces, each in its own window:
rem   1. the local Ask runner  (node server.mjs)
rem   2. the Cloudflare quick tunnel that gives it a public https address
rem Close either window to stop that piece; the website falls back to Gemini.
cd /d "%~dp0"
if not exist ".env" (
  echo Missing local-ask\.env  -  copy .env.example to .env and set ASK_SHARED_SECRET first.
  pause
  exit /b 1
)
start "local-ask runner" "%~dp0start-local-ask.cmd"
start "cloudflared tunnel" "%~dp0start-tunnel.cmd"
echo Two windows opened.
echo Copy the https://....trycloudflare.com address from the tunnel window into LOCAL_ASK_URL on Vercel.
pause
