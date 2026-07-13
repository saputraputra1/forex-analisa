from openai import OpenAI
from config import DEEPSEEK_API_KEY, DEEPSEEK_MODEL, DEEPSEEK_BASE_URL
import json
import time

client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL,
)

def _build_prompt(data_m5, data_m15, price):
    def format_indicator(tf_name, ind):
        if ind is None:
            return f"[{tf_name}] Data tidak mencukupi"
        bb = ind["bb"]
        stoch = ind["stochastic"]
        sr = ind["sr"]
        return f"""[{tf_name}]
Harga Close: {ind['close']}
High/Low: {ind['high']} / {ind['low']}
RSI(7): {ind['rsi']}
MACD: {ind['macd']['macd']} | Signal: {ind['macd']['signal']} | Histogram: {ind['macd']['histogram']}
Bollinger Bands: Upper {bb['upper']} | Middle {bb['middle']} | Lower {bb['lower']}
Stochastic: %K {stoch['k']} | %D {stoch['d']}
EMA 9: {ind['ema_9']} | EMA 21: {ind['ema_21']} | EMA 50: {ind['ema_50']}
SMA 9: {ind['sma_9']} | SMA 21: {ind['sma_21']}
Support terdekat: {sr['nearest_support']}
Resistance terdekat: {sr['nearest_resistance']}
Volume: {ind['volume']}"""

    prompt = f"""[ROLE]
Anda adalah analis trading XAUUSD (Gold vs USD) spesialis SCALPING. Target winrate 85-90%.
Anda hanya memberikan sinyal ketika konfigurasi teknikal sangat kuat dan mendukung.

[INSTRUKSI]
1. Analisa data teknikal M5 dan M15 di bawah
2. Cari konfluensi antara kedua timeframe
3. Tentukan sinyal: BUY jika bullish, SELL jika bearish, HOLD jika tidak jelas
4. Berikan confidence 0-100%
5. HOLD jika confidence < 80%
6. Berikan entry price, stop loss, take profit yang presisi
7. Berikan alasan teknikal singkat (max 2 kalimat)
8. Jawab HOLD jika tidak ada setup bagus — jangan maksa sinyal

[DATA TEKNIKAL SAAT INI]
Harga Spot: ${price}

{format_indicator("M5", data_m5)}

{format_indicator("M15", data_m15)}

[OUTPUT FORMAT]
Harap respon dengan format JSON SAJA, tanpa teks lain:
{{
  "signal": "BUY" | "SELL" | "HOLD",
  "confidence": 85,
  "entry": 2345.67,
  "stop_loss": 2338.00,
  "take_profit": 2353.00,
  "reason": "Alasan teknikal singkat max 2 kalimat",
  "timeframe_confluence": true,
  "dominant_timeframe": "M5"
}}"""
    return prompt

def analyze(data_m5, data_m15, price, max_retries=3):
    prompt = _build_prompt(data_m5, data_m15, price)
    for attempt in range(max_retries):
        try:
            resp = client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=300,
            )
            text = resp.choices[0].message.content.strip()
            text = text.replace("```json", "").replace("```", "").strip()
            result = json.loads(text)
            required = ["signal", "confidence", "entry", "stop_loss", "take_profit", "reason"]
            for field in required:
                if field not in result:
                    result[field] = None
            if result["signal"] not in ("BUY", "SELL", "HOLD"):
                result["signal"] = "HOLD"
            if result["confidence"] is None:
                result["confidence"] = 0
            result["confidence"] = min(100, max(0, int(result["confidence"])))
            return result
        except json.JSONDecodeError:
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            return _fallback_signal(price, data_m5, data_m15)
        except Exception:
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            return _fallback_signal(price, data_m5, data_m15)
    return _fallback_signal(price, data_m5, data_m15)

def _fallback_signal(price, data_m5, data_m15):
    rsi_val = 50
    if data_m5 and "rsi" in data_m5:
        rsi_val = data_m5["rsi"]
    signal = "HOLD"
    if rsi_val < 30:
        signal = "BUY"
    elif rsi_val > 70:
        signal = "SELL"
    return {
        "signal": signal,
        "confidence": 50,
        "entry": price,
        "stop_loss": round(price * 0.995, 2) if signal == "BUY" else round(price * 1.005, 2),
        "take_profit": round(price * 1.005, 2) if signal == "BUY" else round(price * 0.995, 2),
        "reason": "Fallback: analisa berdasarkan RSI saja (DeepSeek error)",
        "timeframe_confluence": False,
        "dominant_timeframe": "M5",
    }
