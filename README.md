# XAUUSD Scalping Signal Bot

## Deploy to Railway (24/7 Cloud)

### 1. Push to GitHub

```bash
# Buat repo baru di GitHub, lalu:
cd forexx
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/USERNAME/xauusd-bot.git
git push -u origin main
```

### 2. Deploy to Railway

1. Login ke [railway.app](https://railway.app) (free tier: $5 credit)
2. Click **New Project** → **Deploy from GitHub repo**
3. Select repo `xauusd-bot`
4. Railway auto-detect Python & install dependencies

### 3. Set Environment Variables

Di Railway Dashboard → Project → **Variables**, tambahkan:

| Variable | Value |
|----------|-------|
| `TELEGRAM_BOT_TOKEN` | `8960871477:AAHM-G2UezdbaRt3AruiBeeU5wfqXJyXPR4` |
| `DEEPSEEK_API_KEY` | `sk-a7ba745751994f12bb619f05e8bc0fba` |
| `MIN_CONFIDENCE` | `80` |
| `MONITOR_INTERVAL_SECONDS` | `120` |

> **Jangan upload `.env` file!** Railway pakai env variables dari dashboard. `.env` sudah di `.gitignore`.

### 4. Railway will auto-deploy

- Build: `pip install -r requirements.txt`
- Start: `python main.py`
- Bot akan running **24/7** di cloud
- Auto-restart jika crash

### Keunggulan Railway vs Local

| Aspect | Local | Railway |
|--------|-------|---------|
| Running | Perlu PC menyala 24/7 | Cloud 24/7 |
| Auto-start | Registry startup | Built-in |
| Restart | Via watchdog script | Auto on crash |
| Biaya | Listrik | Free tier cukup |
| Monitoring | Manual | Railway logs |
