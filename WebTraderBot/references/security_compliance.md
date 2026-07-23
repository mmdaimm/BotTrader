# 🛡️ Security & API Key Protection Guide

This guide defines the security standards for handling Bitkub Exchange API keys and credentials in the WebTraderBot application.

---

## 1. Environment Variable Management
- **Rule**: NEVER hardcode API keys or secret keys in source code files.
- All secrets must be stored in `.env` (for local development) or `.env.local` / Environment Secret Managers.
- Add `.env`, `.env.local`, `*.pem`, and `config.json` containing credentials to `.gitignore` immediately.

```env
# Bitkub API Credentials
BITKUB_API_KEY=your_bitkub_api_key_here
BITKUB_API_SECRET=your_bitkub_api_secret_here

# Telegram Bot Credentials
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
TELEGRAM_CHAT_ID=your_telegram_chat_id_here
```

---

## 2. Bitkub API Key Security Best Practices
- **Restrict Permissions**: Enable ONLY `Read Wallet` and `Place Order` permissions on Bitkub. **DO NOT** enable `Withdrawal` permissions.
- **IP Whitelisting**: Bind API Keys to your server's static IP address on Bitkub Security Settings.
- **Secret Signature Generation**: All signed API requests must use HMAC SHA256 with timestamp verification to prevent replay attacks.
