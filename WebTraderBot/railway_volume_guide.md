# 🏛️ Railway Persistent Disk Volume Setup Guide (0% Data Loss Guarantee)

To ensure that the SQLite Database (`trading_records.db`) persists **100% permanently** across all container rebuilds, git pushes, and cloud restarts on Railway.app, follow these simple setup steps on the Railway Dashboard:

---

## 📌 Step-by-Step Instructions

1. **Open Railway Project Dashboard**:
   - Go to [Railway Dashboard](https://railway.app) and select your `BotTrader` project.

2. **Add a New Persistent Disk Volume**:
   - Click the **+ New** button (top right).
   - Select **Volume** from the menu.

3. **Configure Volume Mount Path**:
   - Click on the newly created Volume.
   - Set **Mount Path** to: `/app/data`
   - Attach the Volume to your **WebTraderBot / FastAPI Service**.

4. **Redeploy Service**:
   - Click **Deploy / Redeploy** on your Bot Service.

---

## 🟢 How It Works Under the Hood

- The Python backend resolves the SQLite database path at `os.path.join("/app/data", "trading_records.db")`.
- When a Railway Volume is mounted at `/app/data`, Docker attaches external persistent disk storage to that folder.
- Every trade record (`Order_trade_crypto`), execution log (`Order_successed_crypto`), and bot configuration (`bot_state_config`) written by SQLite is stored directly on the persistent volume.
- Even if Railway rebuilds the app container 1,000 times, `/app/data` remains untouched, guaranteeing **0% Data Loss** and **0% Hardcode Requirement**!
