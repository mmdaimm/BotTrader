# ⚡ 24/7 Bot Reliability & Uptime Guide

This document outlines architectural patterns to ensure 24/7 uninterrupted operation of the Python Trading Bot.

---

## 1. Exception Handling & Self-Healing Loop
- **API Failure Resilience**: Bitkub REST API calls must be wrapped in exponential backoff retry loops (retrying up to 3 times on HTTP 500/502/504 errors).
- **Network Disconnection Recovery**: If connection drops, log the event, sleep for 10 seconds, and attempt reconnect without stopping the main event loop.

---

## 2. Process Management (PM2 / Systemd)
To ensure the bot restarts automatically if the server reboots or crashes:

### Option A: PM2 Process Manager
```bash
pm2 start src/main.py --name "bitkub-trader-bot" --interpreter python
pm2 save
pm2 startup
```

### Option B: Linux Systemd Service (`/etc/systemd/system/traderbot.service`)
```ini
[Unit]
Description=Bitkub Trading Bot Service
After=network.target

[Service]
User=root
WorkingDirectory=/e/Project/WebTraderBot
ExecStart=/usr/bin/python3 src/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```
