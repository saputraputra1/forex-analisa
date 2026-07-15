import os
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
NVIDIA_MODEL = os.getenv("NVIDIA_MODEL", "z-ai/glm-5.2")
NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
MIN_CONFIDENCE = int(os.getenv("MIN_CONFIDENCE", "55"))
MONITOR_INTERVAL_SECONDS = int(os.getenv("MONITOR_INTERVAL_SECONDS", "120"))

JAKARTA_TZ = timezone(timedelta(hours=7))

def now_jakarta():
    return datetime.now(JAKARTA_TZ)

TIMEFRAMES = {
    "M5": {"interval": "5m", "period": "1d", "candles": 50},
    "M15": {"interval": "15m", "period": "2d", "candles": 30},
    "H1": {"interval": "60m", "period": "5d", "candles": 50},
    "D1": {"interval": "1d", "period": "1mo", "candles": 30},
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
