from openai import OpenAI
from config import NVIDIA_API_KEY, NVIDIA_MODEL, NVIDIA_BASE_URL
from snr import analyze_snr
from ict_smc import analyze_ict_smc
from fundamental_analyzer import get_market_session, get_dxy_price
import json
import time

client = OpenAI(
    api_key=NVIDIA_API_KEY,
    base_url=NVIDIA_BASE_URL,
)

TF_ROLES = {
    "D1": "Overall bias (bullish/bearish/neutral) dan key support/resistance major",
    "H4": "Market structure, Order Block besar, dan level kunci",
    "H1": "Entry confirmation, OB/FVG zones, dan trend menengah",
    "M15": "Timing entry, konfluensi dengan HTF",
    "M5": "Precision entry, scalping trigger, dan momentum",
}

def _fmt_ind(tf_name, ind, snr_data, ict_data):
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
    role = TF_ROLES.get(tf_name, "")
    return f"""[{tf_name} - Role: {role}]
[{tf_name} - TEKNIKAL]
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


def _build_prompt(tf_analysis, price):
    session = get_market_session()
    dxy = get_dxy_price()

    tf_blocks = []
    for tf_name in ["D1", "H4", "H1", "M15", "M5"]:
        if tf_name in tf_analysis:
            df, ind, snr, ict = tf_analysis[tf_name]
            tf_blocks.append(_fmt_ind(tf_name, ind, snr, ict))
        else:
            tf_blocks.append(f"[{tf_name}] Data tidak tersedia")
    tf_text = "\n\n".join(tf_blocks)

    prompt = f"""[ROLE]
Anda adalah analis trading XAUUSD (Gold vs USD) spesialis SCALPING dengan konsep ICT/SMC. Target winrate 85-90%. Tugas Anda adalah MENEMUKAN setup trading berdasarkan multi-timeframe analysis.

[TIMEFRAME ROLES]
- D1 (Daily): Overall bias — bullish/bearish/neutral, key S/R major
- H4 (4-Hour): Market structure, Order Block besar, level kunci
- H1 (1-Hour): Entry confirmation, OB/FVG zones, trend menengah
- M15 (15-Min): Timing entry, konfluensi dengan HTF
- M5 (5-Min): Precision entry, scalping trigger, momentum

[INSTRUKSI MULTI-TIMEFRAME]
1. Analisa D1 dulu untuk tentukan BIAS (bullish/bearish/neutral)
2. H4 cari structure break (BOS/CHoCH) dan Order Block besar
3. H1 cari konfirmasi entry di OB/FVG zone yang SEARAH dengan bias D1/H4
4. M15 cek timing dan konfluensi
5. M5 cari precision entry (trigger point)
6. Jika D1 bullish + H4 ada bullish OB + H1 ada FVG di atas OB = BUY valid
7. Jika D1 bearish + H4 ada bearish OB + H1 ada FVG di bawah OB = SELL valid
8. Confidence berdasarkan jumlah konfluensi lintas timeframe:
   - 3+ TF searah = 80-95%
   - 2 TF searah = 65-80%
   - Hanya 1 TF = 55-65%
9. Entry presisi di OB/FVG zone dari H1/M15
10. SL di bawah/atas OB dari H4 (lebih aman)
11. TP di liquidity zone dari H4/D1
12. Hasilkan ARRAY 2-5 sinyal berbeda

[TIPS AGAR TIDAK HOLD]
- Jika D1 trend jelas (strong bullish/bearish), WAJIB cari entry
- Jika H4 ada OB yang belum di-test, itu entry zone
- Jika H1 ada BOS + FVG searah dengan D1, itu sinyal kuat
- RSI oversold/overbought di HTF = momentum kuat
- EMA crossover di H1/H4 = trend shift

[DATA SAAT INI]
Harga Spot: ${price}
Market Session: {session['session']} (volatility: {session['volatility']})
DXY (Dollar Index): {dxy or 'N/A'}

{tf_text}

[OUTPUT FORMAT - JSON ARRAY, minimal 2 sinyal]:
[
  {{
    "signal": "BUY" | "SELL",
    "confidence": 82,
    "entry": 2345.67,
    "stop_loss": 2338.00,
    "take_profit": 2353.00,
    "reason": "D1 bullish bias, H4 bullish OB di 2340-2345, H1 FVG di 2343, M15 BOS bullish (max 3 kalimat)",
    "timeframe_confluence": true,
    "dominant_timeframe": "H1",
    "ict_setup": "OB + FVG + BOS",
    "htf_bias": "bullish"
  }}
]"""
    return prompt


def _validate_signal(result, price):
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
    if "htf_bias" not in result:
        result["htf_bias"] = "neutral"
    if result["entry"] is None:
        result["entry"] = price
    return result


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
        "reason": "Fallback: analisa berdasarkan RSI saja (AI error)",
        "timeframe_confluence": False,
        "dominant_timeframe": "M5",
        "ict_setup": "none",
        "htf_bias": "neutral",
    }


def analyze(tf_analysis, price, max_retries=3):
    prompt = _build_prompt(tf_analysis, price)
    fallback_ind = None
    if "M5" in tf_analysis:
        fallback_ind = tf_analysis["M5"][1]
    elif "M15" in tf_analysis:
        fallback_ind = tf_analysis["M15"][1]
    for attempt in range(max_retries):
        try:
            resp = client.chat.completions.create(
                model=NVIDIA_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=1,
                top_p=1,
                max_tokens=2000,
                seed=42,
            )
            text = resp.choices[0].message.content.strip()
            text = text.replace("```json", "").replace("```", "").strip()
            result = json.loads(text)
            if isinstance(result, list):
                signals = [_validate_signal(r, price) for r in result]
                signals = [s for s in signals if s["signal"] in ("BUY", "SELL")]
                if not signals:
                    signals = [_validate_signal(result[0], price)]
                return signals[:5]
            else:
                return [_validate_signal(result, price)]
        except json.JSONDecodeError:
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            return [_fallback_signal(price, fallback_ind)]
        except Exception:
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            return [_fallback_signal(price, fallback_ind)]
    return [_fallback_signal(price, fallback_ind)]
