# 🗺️ Project Roadmap - Bitcoin & Stock Auto Trading Bot System

## 📌 Vision
To build a high-performance, automated Bitcoin trading bot (Bitkub Exchange) with dynamic risk management, real-time Telegram alerts, and a modern Next.js Web Control Dashboard, with extensible architecture for stock trading.

---

## 🎯 Project Phases

### Phase 1: Core Engine & Bitkub API Integration (Current Phase - Sprint 1)
- [x] Skill Team Setup (`dev`, `qq`, `pm`)
- [x] Trading Strategy Specification: **Trend-Pullback Scalping (EMA 200 + EMA 9/21 + RSI + ATR)**
- [ ] **Python Core Engine**: Bitkub REST API authentication, ticker/candle data engine
- [ ] **Backtest Module**: Automated backtesting & metrics calculator
- [ ] **Order Execution & Risk Module**: Automated Bitkub limit/market orders with ATR Stop Loss / Take Profit

### Phase 2: Alert System & Security Controls (Sprint 2)
- [ ] **Telegram Bot Integration**: Instant signal alerts, order execution notifications, daily PnL summary
- [ ] **Circuit Breaker**: Auto-pause trading on 3 consecutive losses
- [ ] **Emergency Panic Button**: Instantly cancel open orders & exit positions to THB via API

### Phase 3: Web Control Dashboard (Sprint 3)
- [ ] **FastAPI Backend Services**: Expose endpoints for bot status, logs, control triggers
- [ ] **Next.js Web Dashboard**: Modern dark-mode UI, live price charts, trade history, active position viewer, and Panic Button

### Phase 4: Live Paper Trading & Production Deployment (Sprint 4)
- [ ] Paper Trading validation on Bitkub live feed
- [ ] Production deployment & monitoring setup
- [ ] Multi-asset expansion planning (Stocks / SET API interface)
