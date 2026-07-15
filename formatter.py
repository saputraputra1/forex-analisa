from datetime import datetime, timezone, timedelta
from config import now_jakarta

def format_signal(data):
    signal = data.get("signal", "HOLD")
    confidence = data.get("confidence", 0)
    entry = data.get("entry", "—")
    sl = data.get("stop_loss", "—")
    tp = data.get("take_profit", "—")
    reason = data.get("reason", "—")
    confluence = data.get("timeframe_confluence", False)
    dom_tf = data.get("dominant_timeframe", "M5")
    ict = data.get("ict_setup", "none")
    htf_bias = data.get("htf_bias", "neutral")

    signal_emoji = {"BUY": "\U0001f7e2", "SELL": "\U0001f534", "HOLD": "\u23f8\ufe0f"}
    direction_emoji = {"BUY": "\U0001f4c8", "SELL": "\U0001f4c9", "HOLD": "\u27a1\ufe0f"}
    emoji = signal_emoji.get(signal, "\u2753")
    dir_emoji = direction_emoji.get(signal, "")

    conf_bar = "\u2588" * (confidence // 10) + "\u2591" * ((10 - confidence // 10))
    conf_color = "\U0001f7e2" if confidence >= 80 else "\U0001f7e0" if confidence >= 60 else "\U0001f534"

    def _fmt(v):
        return f"${v}" if v and float(v) != 0 else "—"

    ict_line = f"\n\u200b*ICT Setup:* {ict}" if ict and ict != "none" else ""
    bias_emoji = {"bullish": "\U0001f7e2", "bearish": "\U0001f534", "neutral": "\u26aa"}.get(htf_bias, "\u26aa")
    stale_warn = "\n\u26a0\ufe0f *Data mungkin stale (market tutup)*\n" if data.get("_data_stale") else ""

    msg = f"""
{emoji} *SINYAL SCALPING XAUUSD* {dir_emoji}
{'\u2500' * 30}{stale_warn}

*Sinyal:* {signal}
*Confidence:* {conf_color} {confidence}%
{conf_bar}
*Entry:* {_fmt(entry)}
*Stop Loss:* {_fmt(sl)}
*Take Profit:* {_fmt(tp)}
*Risk/Reward:* 1:{_calc_rr(entry, sl, tp, signal)}{ict_line}

*HTF Bias:* {bias_emoji} {htf_bias.upper()}
*Dominant TF:* {dom_tf} | Multi-TF Konfluensi: {'\u2705 Ya' if confluence else '\u26a0\ufe0f Tidak'}

*Alasan Entry:* _{reason}_

*Waktu:* {now_jakarta().strftime('%H:%M:%S')} WIB
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

def format_indicators(tf_inds):
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
ATR: {ind.get('atr', '—')}
"""
    parts = []
    for tf_name in ["D1", "H4", "H1", "M15", "M5"]:
        if tf_name in tf_inds:
            parts.append(_fmt(tf_name, tf_inds[tf_name]))
    return "\n".join(parts) if parts else "Data indikator tidak tersedia."

def format_ict_analysis(tf_ict_data, session, dxy):
    def _fmt_snr_ict(tf, snr, ict):
        ob = ict["order_blocks"]
        fvg = ict["fvg"]
        liq = ict["liquidity"]
        return f"""*{tf}:*
Structure: {snr['trend']} | BOS: {'yes' if snr['bos'] else 'no'} | CHoCH: {snr['choch'] or 'none'}
Pivot: {snr['pivot']} | R1: {snr['pivot_r1']} | S1: {snr['pivot_s1']}
S/R: {snr['nearest_support']} / {snr['nearest_resistance']}
Round: {', '.join(map(str, snr['round_numbers'][:3]))}
OB: {ict['order_blocks']['total_detected']} detected | FVG: {len(fvg['bullish_fvg'] + fvg['bearish_fvg'])} gap(s)
Liq Sweep: {'yes' if liq['liquidity_sweep_detected'] else 'no'}
Buy Liq: {liq['buy_side_liquidity'][:2]} | Sell Liq: {liq['sell_side_liquidity'][:2]}
Killzone: {ict['killzone'][:30]}
"""
    parts = []
    for tf_name in ["D1", "H4", "H1", "M15", "M5"]:
        if tf_name in tf_ict_data:
            snr, ict = tf_ict_data[tf_name]
            parts.append(_fmt_snr_ict(tf_name, snr, ict))
    msg = f"""\U0001f9e0 *ICT / SMC + SNR Analysis*
{'\u2500' * 30}
Session: {session} | DXY: {dxy}
"""
    msg += "\n".join(parts)
    return msg

def format_news(events):
    if not events:
        return "\u274c Tidak ada event HIGH impact USD hari ini."
    msg = "\U0001f4c5 *ECONOMIC CALENDAR (HIGH Impact)*\n" + "\u2500" * 30
    for e in events[:8]:
        min_str = f"({e['minutes_until']}m lagi)" if e['minutes_until'] > 0 else "(NOW\U0001f525)"
        msg += f"""
\U0001f1fa\U0001f1f8 *{e['event']}*
\u23f1 {e['time']} WIB {min_str}
Forecast: {e['forecast']} | Prev: {e['previous']}
"""
    return msg

def format_news_alert(event):
    return f"""
\U0001f514 *NEWS ALERT - HIGH IMPACT*
{'\u2500' * 30}
\U0001f1fa\U0001f1f8 {event['event']}
\u23f1 {event['time']} WIB ({event['minutes_until']} menit lagi)
Forecast: {event['forecast']} | Previous: {event['previous']}

\u26a0\ufe0f Volatility diprediksi TINGGI
Hindari entry scalping 5 menit sebelum & sesudah rilis.
"""

def _calc_duration(timestamp_str):
    try:
        t = datetime.fromisoformat(timestamp_str)
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        delta = now_jakarta() - t
        mins = int(delta.total_seconds() / 60)
        if mins < 60:
            return f"{mins}m"
        hours = mins // 60
        rem = mins % 60
        if rem == 0:
            return f"{hours}j"
        return f"{hours}j {rem}m"
    except Exception:
        return "-"

def format_tp_alert(data):
    pips = data.get("pips", 0)
    pips_str = f"+{pips}" if pips >= 0 else str(pips)
    dur = _calc_duration(data.get("timestamp", ""))
    return f"""
\U0001f3af *TP KENA\\!*
{'\u2500' * 30}
Sinyal: *{data['signal']}* @ ${data['entry']}
TP: ${data['take_profit']}
Profit: *{pips_str} pips*
Harga Exit: ${data.get('exit_price', '-')}
Durasi: {dur}
Waktu: {now_jakarta().strftime('%H:%M')} WIB
"""

def format_sl_alert(data):
    pips = data.get("pips", 0)
    pips_str = str(pips)
    dur = _calc_duration(data.get("timestamp", ""))
    return f"""
\U0001f4a5 *SL KENA\\!*
{'\u2500' * 30}
Sinyal: *{data['signal']}* @ ${data['entry']}
SL: ${data['stop_loss']}
Loss: *{pips_str} pips*
Harga Exit: ${data.get('exit_price', '-')}
Durasi: {dur}
Waktu: {now_jakarta().strftime('%H:%M')} WIB
"""

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
\U0001f916 *XAUUSD Scalping Signal Bot v3.0*
{'\u2500' * 25}
\u2728 *Multi-Timeframe:* D1 + H4 + H1 + M15 + M5
\u2728 *Features:* ICT/SMC + SNR + Fundamental + HTF Bias

*Commands:*
/signal \u2014 Sinyal instan (bypass filter)
/start \u2014 Pesan ini
/subscribe \u2014 Aktifkan smart alert
/unsubscribe \u2014 Nonaktifkan smart alert
/subscribe\\_news \u2014 Alert news HIGH impact
/unsubscribe\\_news \u2014 Stop news alert
/news \u2014 Jadwal ekonomi hari ini
/ict \u2014 Detail ICT/SMC + SNR (Multi-TF)
/indicators \u2014 Indikator teknikal (Multi-TF)
/winrate \u2014 Statistik winrate
/status \u2014 Status bot

*Timeframe Roles:*
D1 \u2192 Bias | H4 \u2192 Structure | H1 \u2192 Confirmation
M15 \u2192 Timing | M5 \u2192 Precision Entry

*Smart Alert:* Monitor market tiap 2 menit + kirim sinyal setup bagus.
*News Alert:* Notifikasi 30 menit sebelum event HIGH impact USD.
"""
