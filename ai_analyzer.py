from openai import OpenAI
from config import DEEPSEEK_API_KEY, DEEPSEEK_MODEL, DEEPSEEK_BASE_URL
from snr import analyze_snr
from ict_smc import analyze_ict_smc
from fundamental_analyzer import get_market_session, get_dxy_price
import json
import time

client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL,
)

def _build_prompt(data_m5, data_m15, price, ind_m5, ind_m15):
    def fmt_ind(tf_name, ind, snr_data, ict_data):
        if ind is None:
            return f"[{tf_name}] Data tidak mencukupi"
        bb = ind["bb"]
        stoch = ind["stochastic"]
        fvg = ict_data["fvg"]
        ob = ict_data["order_blocks"]
        liq = ict_data["liquidity"]
        bulls = [f"{o['zone_bottom']}-{o['zone_top']}" for o in ob["bullish_obs"]]
        bears = [f"{o['zone_bottom']}-{o['zone_top']}" for o in ob["bearish_obs"]]
        bfvg = [f"{g['gap_bottom']}-{g['gap_top']}" for g in fvg["bullish_fvg"]]
        bfvg_s = [f"{g['gap_bottom']}-{g['gap_top']}" for g in fvg["bearish_fvg"]]
        killzone = ict_data["killzone"]
        return f"""[{tf_name} - TEKNIKAL]
Close: {ind['close']} | High: {ind['high']} | Low: {ind['low']}
RSI(7): {ind['rsi']}
MACD: {ind['macd']['macd']} / Signal {ind['macd']['signal']} / Hist {ind['macd']['histogram']}
BB: Upper {bb['upper']} Mid {bb['middle']} Lower {bb['lower']}
Stoch: %K {stoch['k']} %D {stoch['d']}
EMA: 9={ind['ema_9']} 21={ind['ema_21']} 50={ind['ema_50']}
ATR(14): {ind['atr']}

[{tf_name} - SNR]
Trend: {snr_data['trend']}
BOS: {snr_data['bos']} | CHoCH: {snr_data['choch'] or 'none'}
Support: {snr_data['nearest_support']} Resistance: {snr_data['nearest_resistance']}
Pivot: {snr_data['pivot']} R1: {snr_data['pivot_r1']} S1: {snr_data['pivot_s1']}
Round Numbers: {', '.join(map(str, snr_data['round_numbers']))}

[{tf_name} - ICT/SMC]
Structure: {snr_data['trend']}
Killzone: {killzone}
Bullish OB: {', '.join(bulls) if bulls else 'none'}
Bearish OB: {', '.join(bears) if bears else 'none'}
Bullish FVG: {', '.join(bfvg) if bfvg else 'none'}
Bearish FVG: {', '.join(bfvg_s) if bfvg_s else 'none'}
Liquidity Sweep: {'yes - ' + str(liq['sweep_level']) if liq['liquidity_sweep_detected'] else 'no'}
Buy-side Liq: {', '.join(map(str, liq['buy_side_liquidity'])) if liq['buy_side_liquidity'] else 'none'}
Sell-side Liq: {', '.join(map(str, liq['sell_side_liquidity'])) if liq['sell_side_liquidity'] else 'none'}"""

    session = get_market_session()
    dxy = get_dxy_price()

    prompt = f"""[ROLE]
Anda adalah analis trading XAUUSD (Gold vs USD) spesialis SCALPING dengan konsep ICT/SMC (Inner Circle Trader / Smart Money Concepts). Target winrate 85-90%. Anda hanya memberikan sinyal ketika konfigurasi teknikal + ICT sangat kuat dan mendukung.

[INSTRUKSI]
1. Analisa data TEKNIKAL + SNR + ICT/SMC M5 dan M15 di bawah
2. Cari konfluensi antara M5 dan M15
3. Gunakan konsep ICT/SMC: Order Block, FVG, Liquidity Sweep, Killzone, Market Structure
4. Tentukan sinyal: BUY jika bullish, SELL jika bearish, HOLD jika tidak jelas
5. Berikan confidence 0-100%, HOLD jika <80%
6. Entry price presisi (idealnya di OB/FVG zone)
7. Stop loss di bawah/atas OB terdekat atau swing high/low
8. Take profit di liquidity atau swing terdekat
9. Alasan harus mencakup: konfluensi teknikal, SNR level, ICT setup, dan killzone

[DATA SAAT INI]
Harga Spot: ${price}
Market Session: {session['session']} (volatility: {session['volatility']})
DXY (Dollar Index): {dxy or 'N/A'}

{fmt_ind("M5", ind_m5, analyze_snr(data_m5), analyze_ict_smc(data_m5)) if ind_m5 is not None else "[M5] Data tidak mencukupi"}

{fmt_ind("M15", ind_m15, analyze_snr(data_m15), analyze_ict_smc(data_m15)) if ind_m15 is not None else "[M15] Data tidak mencukupi"}

[OUTPUT FORMAT JSON SAJA]:
{{
  "signal": "BUY" | "SELL" | "HOLD",
  "confidence": 85,
  "entry": 2345.67,
  "stop_loss": 2338.00,
  "take_profit": 2353.00,
  "reason": "Alasan teknikal + ICT/SMC + SNR (max 3 kalimat)",
  "timeframe_confluence": true,
  "dominant_timeframe": "M5",
  "ict_setup": "OB + FVG + Liquidity Sweep" | "none" | "..."
}}"""
    return prompt

def analyze(data_m5, data_m15, price, ind_m5=None, ind_m15=None, max_retries=3):
    prompt = _build_prompt(data_m5, data_m15, price, ind_m5, ind_m15)
    for attempt in range(max_retries):
        try:
            resp = client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=400,
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
            if "ict_setup" not in result:
                result["ict_setup"] = "none"
            return result
        except json.JSONDecodeError:
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            return _fallback_signal(price, ind_m5)
        except Exception:
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            return _fallback_signal(price, ind_m5)
    return _fallback_signal(price, ind_m5)

def _fallback_signal(price, ind_m5):
    rsi_val = 50
    if ind_m5 and "rsi" in ind_m5:
        rsi_val = ind_m5["rsi"]
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
        "ict_setup": "none",
    }
