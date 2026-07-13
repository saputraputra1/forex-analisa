from datetime import datetime

def format_signal(data):
    signal = data.get("signal", "HOLD")
    confidence = data.get("confidence", 0)
    entry = data.get("entry", "—")
    sl = data.get("stop_loss", "—")
    tp = data.get("take_profit", "—")
    reason = data.get("reason", "—")
    confluence = data.get("timeframe_confluence", False)
    dom_tf = data.get("dominant_timeframe", "M5")

    signal_emoji = {"BUY": "\U0001f7e2", "SELL": "\U0001f534", "HOLD": "\u23f8\ufe0f"}
    direction_emoji = {"BUY": "\U0001f4c8", "SELL": "\U0001f4c9", "HOLD": "\u27a1\ufe0f"}
    emoji = signal_emoji.get(signal, "\u2753")
    dir_emoji = direction_emoji.get(signal, "")

    conf_bar = "\u2588" * (confidence // 10) + "\u2591" * ((10 - confidence // 10))
    conf_color = "\U0001f7e2" if confidence >= 80 else "\U0001f7e0" if confidence >= 60 else "\U0001f534"

    msg = f"""
{emoji} *SINYAL SCALPING XAUUSD* {dir_emoji}
{'\u2500' * 30}

*Sinyal:* {signal}
*Confidence:* {conf_color} {confidence}%
{conf_bar}
*Entry:* ${entry}
*Stop Loss:* ${sl}
*Take Profit:* ${tp}
*Risk/Reward:* 1:{_calc_rr(entry, sl, tp, signal)}

*Alasan Entry:* _{reason}_

*Timeframe:* {dom_tf} | Konfluensi M5 & M15: {'\u2705 Ya' if confluence else '\u26a0\ufe0f Tidak'}
*Waktu:* {datetime.now().strftime('%H:%M:%S')} WIB
"""
    return msg

def _calc_rr(entry, sl, tp, signal):
    try:
        entry, sl, tp = float(entry), float(sl), float(tp)
        if signal == "BUY":
            risk = entry - sl
            reward = tp - entry
        else:
            risk = sl - entry
            reward = entry - tp
        if risk <= 0:
            return "—"
        rr = round(reward / risk, 2)
        return f"1:{rr}"
    except (TypeError, ValueError):
        return "—"

def format_indicators(ind_m5, ind_m15):
    def _fmt(name, ind):
        if ind is None:
            return f"*{name}:* Data tidak tersedia"
        return f"""*{name}:*
RSI(7): {ind['rsi']}
MACD: {ind['macd']['macd']} | Hist: {ind['macd']['histogram']}
BB: Upper {ind['bb']['upper']} | Mid {ind['bb']['middle']} | Lower {ind['bb']['lower']}
Stoch %K: {ind['stochastic']['k']} | %D: {ind['stochastic']['d']}
EMA 9: {ind['ema_9']} | EMA 21: {ind['ema_21']} | EMA 50: {ind['ema_50']}
Support: {ind['sr']['nearest_support']} | Res: {ind['sr']['nearest_resistance']}
"""
    return f"{_fmt('M5', ind_m5)}\n{_fmt('M15', ind_m15)}"

def format_winrate(wr):
    bar_wins = "\u2588" * (wr["wins"] if wr["closed"] > 0 else 0)
    bar_losses = "\u2591" * (wr["losses"] if wr["closed"] > 0 else 0)
    return f"""
\U0001f3c6 *Winrate Signal*
{'\u2500' * 20}
Total: {wr['total']} sinyal
Closed: {wr['closed']}
\u2705 Win: {wr['wins']}
\u274c Loss: {wr['losses']}
\u23f3 Pending: {wr['pending']}
*Winrate: {wr['winrate']}%*
{bar_wins}{bar_losses}
"""

def format_start():
    return f"""
\U0001f916 *XAUUSD Scalping Signal Bot*

Bot ini memberikan sinyal trading XAUUSD (Gold) untuk *scalping* dengan target winrate 85-90% menggunakan AI (DeepSeek).

*Commands:*
/signal \u2014 Sinyal instan (bypass filter)
/start \u2014 Pesan ini
/subscribe \u2014 Aktifkan smart alert (auto-kirim saat confidence \u226580%)
/unsubscribe \u2014 Nonaktifkan smart alert
/winrate \u2014 Statistik winrate
/indicators \u2014 Detail indikator teknikal
/status \u2014 Status bot

*Smart Alert:* Bot monitor market tiap 2 menit & kirim sinyal hanya ketika setup bagus.
"""
