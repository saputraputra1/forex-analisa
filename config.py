import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
MIN_CONFIDENCE = int(os.getenv("MIN_CONFIDENCE", "80"))
MONITOR_INTERVAL_SECONDS = int(os.getenv("MONITOR_INTERVAL_SECONDS", "120"))
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

TIMEFRAMES = {
    "M5": {"interval": "5m", "period": "1d", "candles": 50},
    "M15": {"interval": "15m", "period": "2d", "candles": 30},
}

INDICATOR_PARAMS = {
    "rsi_period": 7,
    "macd_fast": 5,
    "macd_slow": 13,
    "macd_signal": 5,
    "bb_period": 20,
    "bb_std": 2.0,
    "stoch_k": 5,
    "stoch_d": 3,
    "ema_periods": [9, 21, 50],
}
