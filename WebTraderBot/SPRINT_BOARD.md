# 📋 Sprint Board - Sprint 4 (OKX Perpetual Futures & Dual-Direction LONG/SHORT Engine)

**Sprint Goal**: Migrate WebTraderBot to OKX Futures for Dual-Direction Trading (LONG & SHORT), 3x Isolated Leverage, lower fees, and global liquidity.

---

## 🏃 Active Board

### 📝 To Do
- [ ] Add OKX Live Real Trade API Keys in `.env` for Live Execution (`dev`)

### 🔄 In Progress
- [ ] Collecting Paper Trading Performance Data across LONG & SHORT positions (`qq`)

### 🔍 Review / Testing
- [x] Tested Simulated SHORT Position on `ETH-USDT-SWAP` at $1,881.52 with 3x Isolated Margin (`dev`)

### ✅ Done
- [x] Created OKX API v5 Client module (`src/core/okx_client.py`) with Base64 HMAC-SHA256 Signatures and Fail-safe Feed Fallback (`dev`)
- [x] Upgraded TraderBot to Dual-Direction Signal Evaluation (LONG & SHORT) (`src/core/trader_bot.py`) (`dev`)
- [x] Upgraded Risk Engine for 3x Isolated Futures Margin & SHORT SL/TP calculation (`src/core/risk_engine.py`) (`dev`)
- [x] Upgraded Paper Trading Engine to support LONG and SHORT positions with JSON disk persistence (`src/core/paper_trading.py`) (`dev`)
- [x] Upgraded Next.js Web Dashboard for OKX Perpetual Swaps & Dual **+ LONG** / **- SHORT** simulation buttons (`frontend/app/page.tsx`) (`dev`)
