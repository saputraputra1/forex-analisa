import logging
from datetime import datetime

from telegram.ext import Application, CommandHandler, ContextTypes

from config import TELEGRAM_BOT_TOKEN, DEEPSEEK_API_KEY, MIN_CONFIDENCE, MONITOR_INTERVAL_SECONDS
from data_fetcher import get_all_timeframes
from indicators import calculate_all
from ai_analyzer import analyze
from signal_logger import init_db, log_signal, update_outcome, get_winrate, get_recent_signals
from formatter import format_signal, format_indicators, format_winrate, format_start

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

subscribers = set()

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

        result = analyze(ind_m5, ind_m15, price)

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
    if error:
        return
    if result is None:
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

async def signal_command(update, context):
    chat_id = update.effective_chat.id
    await update.message.reply_text("\u23f3 Menganalisa market... (DeepSeek AI processing)")
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
    msg = f"""
\U0001f916 *Status Bot*

\u2022 Status: \u2705 Running
\u2022 Harga XAUUSD: ${price}
\u2022 Subscribers: {len(subscribers)}
\u2022 Monitor interval: setiap {MONITOR_INTERVAL_SECONDS // 60} menit
\u2022 Min confidence: {MIN_CONFIDENCE}%
\u2022 Total sinyal: {wr['total']}
\u2022 Winrate: {wr['winrate']}%
\u2022 Update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    await update.message.reply_text(msg, parse_mode="Markdown")

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

    app.add_handler(CommandHandler("signal", signal_command))
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("subscribe", subscribe_command))
    app.add_handler(CommandHandler("unsubscribe", unsubscribe_command))
    app.add_handler(CommandHandler("winrate", winrate_command))
    app.add_handler(CommandHandler("indicators", indicators_command))
    app.add_handler(CommandHandler("status", status_command))

    job_queue = app.job_queue
    job_queue.run_repeating(monitor_market, interval=MONITOR_INTERVAL_SECONDS, first=10)

    logger.info("Bot started. Press Ctrl+C to stop.")
    app.run_polling()

if __name__ == "__main__":
    main()
