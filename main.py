import logging
from datetime import datetime
from config import now_jakarta

from telegram import Update, BotCommand
from telegram.error import Conflict
from telegram.ext import Application, CommandHandler, ContextTypes

from config import TELEGRAM_BOT_TOKEN, NVIDIA_API_KEY, MIN_CONFIDENCE, MONITOR_INTERVAL_SECONDS
from data_fetcher import get_all_timeframes
from indicators import calculate_all
from snr import analyze_snr
from ict_smc import analyze_ict_smc
from news_calendar import get_upcoming_events, get_imminent_events
from fundamental_analyzer import analyze_fundamental, get_market_session, get_dxy_price
from ai_analyzer import analyze
from signal_logger import init_db, log_signal, get_winrate, get_recent_signals, check_outcomes, auto_close_expired
from formatter import (
    format_signal, format_indicators, format_winrate, format_start,
    format_ict_analysis, format_news, format_news_alert,
    format_tp_alert, format_sl_alert,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

subscribers = set()
news_subscribers = set()
news_warning_cache = {}

async def _run_analysis(force=False):
    try:
        data = get_all_timeframes()
        price = data["price"]
        if price is None:
            return None, "Gagal mengambil harga XAUUSD"

        tf_analysis = {}
        for tf_name in ["M5", "M15", "H1", "H4", "D1"]:
            df = data.get(tf_name)
            if df is not None and not df.empty:
                ind = calculate_all(df)
                snr = analyze_snr(df)
                ict = analyze_ict_smc(df)
                tf_analysis[tf_name] = (df, ind, snr, ict)

        if not tf_analysis:
            return None, "Data candlestick tidak mencukupi untuk analisa"

        signals = analyze(tf_analysis, price)

        if not signals:
            return None, "Gagal mendapat analisa dari AI"

        results = []
        for s in signals:
            if force or s["confidence"] >= MIN_CONFIDENCE:
                sid = log_signal(s)
                s["_id"] = sid
                s["_data_stale"] = data.get("data_stale", False)
                s["_price_source"] = data.get("price_source", "")
                results.append(s)

        if not results:
            return None, None

        return results, None
    except Exception as e:
        logger.exception("Error in _run_analysis")
        return None, f"Error: {str(e)}"

def _pick_best_signal(signals: list) -> dict:
    return max(signals, key=lambda s: s["confidence"])

async def send_signal(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    results, error = await _run_analysis(force=False)
    if error or results is None:
        return
    best = _pick_best_signal(results)
    msg = format_signal(best)
    try:
        await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Failed to send signal: {e}")

async def monitor_market(context: ContextTypes.DEFAULT_TYPE):
    if not subscribers:
        return
    logger.info(f"Monitoring market for {len(subscribers)} subscriber(s)...")
    for chat_id in list(subscribers):
        await send_signal(context, chat_id)

async def monitor_news(context: ContextTypes.DEFAULT_TYPE):
    if not news_subscribers:
        return
    events = get_imminent_events(minutes_ahead=35)
    now_key = datetime.now().strftime("%Y-%m-%d %H:%M")
    for event in events:
        event_key = f"{event['event']}_{event['time']}"
        cache_val = news_warning_cache.get(event_key)
        if cache_val and (datetime.now() - cache_val).total_seconds() < 600:
            continue
        if 10 <= event["minutes_until"] <= 32:
            news_warning_cache[event_key] = datetime.now()
            msg = format_news_alert(event)
            for chat_id in list(news_subscribers):
                try:
                    await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")
                except Exception:
                    continue

async def monitor_outcomes(context: ContextTypes.DEFAULT_TYPE):
    if not subscribers:
        return
    try:
        data = get_all_timeframes()
        price = data["price"]
        if price is None:
            return
        auto_close_expired(hours=24)
        hits = check_outcomes(price)
        if not hits:
            return
        logger.info(f"Outcome alerts: {len(hits)} signal(s) hit TP/SL")
        for h in hits:
            if h["outcome"] == "WIN":
                msg = format_tp_alert(h)
            elif h["outcome"] == "LOSS":
                msg = format_sl_alert(h)
            else:
                continue
            for chat_id in list(subscribers):
                try:
                    await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")
                except Exception:
                    continue
    except Exception as e:
        logger.error(f"Error in monitor_outcomes: {e}")

async def signal_command(update, context):
    chat_id = update.effective_chat.id
    await update.message.reply_text("\u23f3 Menganalisa market... (Multi-TF: D1/H4/H1/M15/M5 + ICT/SMC + SNR)")
    results, error = await _run_analysis(force=True)
    if error:
        await update.message.reply_text(f"\u274c {error}")
        return
    if not results:
        await update.message.reply_text("\u23f8\ufe0f Tidak ada sinyal valid saat ini.")
        return
    best = _pick_best_signal(results)
    msg = format_signal(best)
    if len(results) > 1:
        msg += f"\n\n_({len(results)-1} zona entry lain ditemukan, hanya ditampilkan yang terbaik)_"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def start_command(update, context):
    await update.message.reply_text(format_start(), parse_mode="Markdown")

async def subscribe_command(update, context):
    chat_id = update.effective_chat.id
    if chat_id in subscribers:
        await update.message.reply_text("\u26a0\ufe0f Anda sudah subscribe smart alert.")
        return
    subscribers.add(chat_id)
    await update.message.reply_text(
        "\u2705 *Smart Alert Aktif!*\n\n"
        "Bot akan otomatis mengirim sinyal ketika terdeteksi setup bagus (confidence \u226580%).\n"
        "Gunakan /unsubscribe untuk berhenti.",
        parse_mode="Markdown",
    )
    logger.info(f"Subscriber added: {chat_id}")

async def unsubscribe_command(update, context):
    chat_id = update.effective_chat.id
    if chat_id not in subscribers:
        await update.message.reply_text("\u26a0\ufe0f Anda belum subscribe.")
        return
    subscribers.discard(chat_id)
    await update.message.reply_text("\u2705 Smart Alert dinonaktifkan.")
    logger.info(f"Subscriber removed: {chat_id}")

async def subscribe_news_command(update, context):
    chat_id = update.effective_chat.id
    if chat_id in news_subscribers:
        await update.message.reply_text("\u26a0\ufe0f Anda sudah subscribe news alert.")
        return
    news_subscribers.add(chat_id)
    await update.message.reply_text(
        "\u2705 *News Alert Aktif!*\n\n"
        "Bot akan mengirim notifikasi 30 menit sebelum event HIGH impact USD.\n"
        "Gunakan /unsubscribe\\_news untuk berhenti.",
        parse_mode="Markdown",
    )
    logger.info(f"News subscriber added: {chat_id}")

async def unsubscribe_news_command(update, context):
    chat_id = update.effective_chat.id
    if chat_id not in news_subscribers:
        await update.message.reply_text("\u26a0\ufe0f Anda belum subscribe news alert.")
        return
    news_subscribers.discard(chat_id)
    await update.message.reply_text("\u2705 News alert dinonaktifkan.")
    logger.info(f"News subscriber removed: {chat_id}")

async def news_command(update, context):
    try:
        events = get_upcoming_events(hours_ahead=48, min_impact="HIGH")
        msg = format_news(events)
        await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception as e:
        logger.exception("News command failed")
        await update.message.reply_text(f"\u274c Gagal mengambil jadwal news: {str(e)[:100]}")

async def ict_command(update, context):
    await update.message.reply_text("\u23f3 Menganalisa ICT/SMC + SNR (Multi-TF)...")
    data = get_all_timeframes()
    session = get_market_session()["session"]
    dxy = get_dxy_price()
    tf_ict_data = {}
    for tf_name in ["D1", "H4", "H1", "M15", "M5"]:
        df = data.get(tf_name)
        if df is not None and not df.empty:
            snr = analyze_snr(df)
            ict = analyze_ict_smc(df)
            if snr and ict:
                tf_ict_data[tf_name] = (snr, ict)
    if not tf_ict_data:
        await update.message.reply_text("Data tidak mencukupi untuk analisa ICT/SMC.")
        return
    msg = format_ict_analysis(tf_ict_data, session, dxy)
    await update.message.reply_text(msg, parse_mode="Markdown")

async def winrate_command(update, context):
    wr = get_winrate()
    msg = format_winrate(wr)
    recent = get_recent_signals(10)
    if recent:
        msg += "\n*10 Sinyal Terakhir:*\n"
        for s in recent:
            emoji = {"WIN": "\u2705", "LOSS": "\u274c", "PENDING": "\u23f3", "NONE": "\u23ed\ufe0f"}.get(s["outcome"], "\u2753")
            pips = s.get("pips")
            pips_str = f" | {pips:+.1f} pips" if pips is not None else ""
            tp_sl = ""
            if s.get("take_profit"):
                tp_sl += f" TP${s['take_profit']}"
            if s.get("stop_loss"):
                tp_sl += f" SL${s['stop_loss']}"
            msg += f"{emoji} {s['signal']} ${s['entry']} | {s['confidence']}%{tp_sl}{pips_str}\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def indicators_command(update, context):
    await update.message.reply_text("\u23f3 Mengambil data indikator (Multi-TF)...")
    data = get_all_timeframes()
    tf_inds = {}
    for tf_name in ["D1", "H4", "H1", "M15", "M5"]:
        df = data.get(tf_name)
        if df is not None and not df.empty:
            ind = calculate_all(df)
            if ind:
                tf_inds[tf_name] = ind
    if not tf_inds:
        await update.message.reply_text("Data indikator tidak tersedia.")
        return
    msg = f"\U0001f4ca *Indikator Teknikal XAUUSD (Multi-TF)*\nHarga: ${data['price']}\n{format_indicators(tf_inds)}"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def status_command(update, context):
    wr = get_winrate()
    data = get_all_timeframes()
    price = data["price"] or "—"
    fund = analyze_fundamental()
    news_count = len(get_upcoming_events(hours_ahead=24, min_impact="HIGH"))
    msg = f"""
\U0001f916 *Status Bot*

\u2022 Status: \u2705 Running
\u2022 Harga XAUUSD: ${price} ({data.get('price_source', 'GC=F')})
\u2022 Session: {fund['session']} | DXY: {fund['dxy'] or 'N/A'}
\u2022 Signal subs: {len(subscribers)} | News subs: {len(news_subscribers)}
\u2022 News HIGH hari ini: {news_count}
\u2022 Monitor: tiap {MONITOR_INTERVAL_SECONDS // 60} menit
\u2022 Min confidence: {MIN_CONFIDENCE}%
\u2022 Total sinyal: {wr['total']}
\u2022 Winrate: {wr['winrate']}%
\u2022 Update: {now_jakarta().strftime('%Y-%m-%d %H:%M:%S')} WIB
"""
    await update.message.reply_text(msg, parse_mode="Markdown")

async def error_handler(update, context):
    if isinstance(context.error, Conflict):
        logger.warning("Telegram Conflict: another instance detected, retrying...")
        return
    logger.error(f"Error: {context.error}", exc_info=context.error)

def main():
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
        print("\u274c ERROR: TELEGRAM_BOT_TOKEN belum diisi di file .env")
        return
    if not NVIDIA_API_KEY or NVIDIA_API_KEY == "YOUR_NVIDIA_API_KEY":
        print("\u274c ERROR: NVIDIA_API_KEY belum diisi di file .env")
        return

    init_db()
    logger.info("Database initialized")

    cmds = [
        BotCommand("signal", "Sinyal scalping instan"),
        BotCommand("start", "Info bot & commands"),
        BotCommand("subscribe", "Aktifkan auto-signal"),
        BotCommand("unsubscribe", "Nonaktifkan auto-signal"),
        BotCommand("subscribe_news", "Alert news HIGH impact"),
        BotCommand("unsubscribe_news", "Stop news alert"),
        BotCommand("news", "Jadwal ekonomi hari ini"),
        BotCommand("ict", "Detail ICT/SMC + SNR"),
        BotCommand("indicators", "Indikator teknikal"),
        BotCommand("winrate", "Statistik winrate"),
        BotCommand("status", "Status bot"),
    ]

    async def _post_init(application):
        try:
            await application.bot.set_my_commands(cmds)
            logger.info("Bot commands registered in Telegram menu")
        except Exception as e:
            logger.warning(f"Could not set bot commands: {e}")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).post_init(_post_init).build()

    app.add_handler(CommandHandler("signal", signal_command))
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("subscribe", subscribe_command))
    app.add_handler(CommandHandler("unsubscribe", unsubscribe_command))
    app.add_handler(CommandHandler("subscribe_news", subscribe_news_command))
    app.add_handler(CommandHandler("unsubscribe_news", unsubscribe_news_command))
    app.add_handler(CommandHandler("news", news_command))
    app.add_handler(CommandHandler("ict", ict_command))
    app.add_handler(CommandHandler("winrate", winrate_command))
    app.add_handler(CommandHandler("indicators", indicators_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_error_handler(error_handler)

    job_queue = app.job_queue
    job_queue.run_repeating(monitor_market, interval=MONITOR_INTERVAL_SECONDS, first=10)
    job_queue.run_repeating(monitor_news, interval=60, first=20)
    job_queue.run_repeating(monitor_outcomes, interval=60, first=30)

    logger.info("Bot started. Press Ctrl+C to stop.")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
