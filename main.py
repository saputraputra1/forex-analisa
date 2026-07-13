import logging
from datetime import datetime

from telegram import Update, BotCommand
from telegram.error import Conflict
from telegram.ext import Application, CommandHandler, ContextTypes

from config import TELEGRAM_BOT_TOKEN, DEEPSEEK_API_KEY, MIN_CONFIDENCE, MONITOR_INTERVAL_SECONDS
from data_fetcher import get_all_timeframes
from indicators import calculate_all
from snr import analyze_snr
from ict_smc import analyze_ict_smc
from news_calendar import get_upcoming_events, get_imminent_events
from fundamental_analyzer import analyze_fundamental, get_market_session, get_dxy_price
from ai_analyzer import analyze
from signal_logger import init_db, log_signal, get_winrate, get_recent_signals
from formatter import (
    format_signal, format_indicators, format_winrate, format_start,
    format_ict_analysis, format_news, format_news_alert,
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
            return None, "Gagal mendapatkan harga XAUUSD"

        ind_m5 = calculate_all(data["M5"]) if not data["M5"].empty else None
        ind_m15 = calculate_all(data["M15"]) if not data["M15"].empty else None

        if ind_m5 is None and ind_m15 is None:
            return None, "Data candlestick tidak mencukupi untuk analisa"

        result = analyze(
            data["M5"] if not data["M5"].empty else None,
            data["M15"] if not data["M15"].empty else None,
            price, ind_m5, ind_m15,
        )

        if result is None:
            return None, "Gagal mendapat analisa dari AI"

        if not force and result["confidence"] < MIN_CONFIDENCE:
            return None, None

        sid = log_signal(result)
        result["_id"] = sid
        return result, None
    except Exception as e:
        logger.exception("Error in _run_analysis")
        return None, f"Error: {str(e)}"

async def send_signal(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    result, error = await _run_analysis(force=False)
    if error or result is None:
        return
    msg = format_signal(result)
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

async def signal_command(update, context):
    chat_id = update.effective_chat.id
    await update.message.reply_text("\u23f3 Menganalisa market... (DeepSeek AI + ICT/SMC + SNR processing)")
    result, error = await _run_analysis(force=True)
    if error:
        await update.message.reply_text(f"\u274c {error}")
        return
    if result is None:
        await update.message.reply_text("\u23f8\ufe0f Tidak ada sinyal valid saat ini.")
        return
    msg = format_signal(result)
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
        "Gunakan /unsubscribe_news untuk berhenti.",
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
    events = get_upcoming_events(hours_ahead=48, min_impact="HIGH")
    msg = format_news(events)
    await update.message.reply_text(msg, parse_mode="Markdown")

async def ict_command(update, context):
    await update.message.reply_text("\u23f3 Menganalisa ICT/SMC + SNR...")
    data = get_all_timeframes()
    session = get_market_session()["session"]
    dxy = get_dxy_price()
    snr_m5 = analyze_snr(data["M5"]) if not data["M5"].empty else None
    ict_m5 = analyze_ict_smc(data["M5"]) if not data["M5"].empty else None
    snr_m15 = analyze_snr(data["M15"]) if not data["M15"].empty else None
    ict_m15 = analyze_ict_smc(data["M15"]) if not data["M15"].empty else None
    if not snr_m5 or not snr_m15:
        await update.message.reply_text("Data tidak mencukupi untuk analisa ICT/SMC.")
        return
    msg = format_ict_analysis(snr_m5, ict_m5, snr_m15, ict_m15, session, dxy)
    await update.message.reply_text(msg, parse_mode="Markdown")

async def winrate_command(update, context):
    wr = get_winrate()
    msg = format_winrate(wr)
    recent = get_recent_signals(5)
    if recent:
        msg += "\n*5 Sinyal Terakhir:*\n"
        for s in recent:
            emoji = {"WIN": "\u2705", "LOSS": "\u274c", "PENDING": "\u23f3"}.get(s["outcome"], "\u2753")
            msg += f"{emoji} {s['signal']} | Entry ${s['entry']} | Conf {s['confidence']}% | {s['outcome'] or 'PENDING'}\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def indicators_command(update, context):
    await update.message.reply_text("\u23f3 Mengambil data indikator...")
    data = get_all_timeframes()
    ind_m5 = calculate_all(data["M5"]) if not data["M5"].empty else None
    ind_m15 = calculate_all(data["M15"]) if not data["M15"].empty else None
    if ind_m5 is None and ind_m15 is None:
        await update.message.reply_text("Data indikator tidak tersedia.")
        return
    msg = f"\U0001f4ca *Indikator Teknikal XAUUSD*\nHarga: ${data['price']}\n{format_indicators(ind_m5, ind_m15)}"
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
\u2022 Harga XAUUSD: ${price}
\u2022 Session: {fund['session']} | DXY: {fund['dxy'] or 'N/A'}
\u2022 Signal subs: {len(subscribers)} | News subs: {len(news_subscribers)}
\u2022 News HIGH hari ini: {news_count}
\u2022 Monitor: tiap {MONITOR_INTERVAL_SECONDS // 60} menit
\u2022 Min confidence: {MIN_CONFIDENCE}%
\u2022 Total sinyal: {wr['total']}
\u2022 Winrate: {wr['winrate']}%
\u2022 Update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
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
    if not DEEPSEEK_API_KEY or DEEPSEEK_API_KEY == "YOUR_DEEPSEEK_API_KEY":
        print("\u274c ERROR: DEEPSEEK_API_KEY belum diisi di file .env")
        return

    init_db()
    logger.info("Database initialized")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

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
    async def _post_init(app):
        await app.bot.set_my_commands(cmds)
    app.post_init = _post_init

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

    logger.info("Bot started. Press Ctrl+C to stop.")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
