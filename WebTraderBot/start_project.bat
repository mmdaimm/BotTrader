@echo off
echo ==========================================================
echo 🚀 Starting WebTraderBot Full-Stack Platform...
echo ==========================================================
echo.

echo 1. Starting FastAPI Backend Engine (Port 8000)...
start "WebTraderBot FastAPI Backend" cmd /k "cd /d %~dp0 && python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload"

echo 2. Starting Next.js Frontend Dashboard (Port 3000)...
start "WebTraderBot Next.js Dashboard" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo ==========================================================
echo ✅ All Servers Launching!
echo 💻 Open Web Dashboard at: http://localhost:3000
echo ⚙️ Backend API Server at:  http://localhost:8000
echo ==========================================================
pause
