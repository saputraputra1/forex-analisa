import sqlite3
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "signal_log.db")

def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            signal TEXT NOT NULL,
            entry REAL,
            stop_loss REAL,
            take_profit REAL,
            confidence INTEGER,
            reason TEXT,
            outcome TEXT,
            exit_price REAL,
            pips REAL,
            timeframe_confluence INTEGER
        )
    """)
    conn.commit()
    conn.close()

def log_signal(signal_data):
    conn = _get_conn()
    conn.execute("""
        INSERT INTO signals (timestamp, signal, entry, stop_loss, take_profit, confidence, reason, timeframe_confluence)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().isoformat(),
        signal_data.get("signal"),
        signal_data.get("entry"),
        signal_data.get("stop_loss"),
        signal_data.get("take_profit"),
        signal_data.get("confidence"),
        signal_data.get("reason"),
        1 if signal_data.get("timeframe_confluence") else 0,
    ))
    conn.commit()
    signal_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return signal_id

def update_outcome(signal_id, exit_price):
    conn = _get_conn()
    row = conn.execute("SELECT * FROM signals WHERE id = ?", (signal_id,)).fetchone()
    if not row:
        conn.close()
        return
    entry = row["entry"]
    signal_type = row["signal"]
    sl = row["stop_loss"]
    tp = row["take_profit"]
    if signal_type == "BUY":
        if exit_price >= tp:
            outcome = "WIN"
            pips = round((tp - entry) * 10, 1)
        elif exit_price <= sl:
            outcome = "LOSS"
            pips = round((sl - entry) * 10, 1)
        else:
            outcome = "PENDING"
            pips = round((exit_price - entry) * 10, 1)
    elif signal_type == "SELL":
        if exit_price <= tp:
            outcome = "WIN"
            pips = round((entry - tp) * 10, 1)
        elif exit_price >= sl:
            outcome = "LOSS"
            pips = round((entry - sl) * 10, 1)
        else:
            outcome = "PENDING"
            pips = round((entry - exit_price) * 10, 1)
    else:
        outcome = "NONE"
        pips = 0
    conn.execute("""
        UPDATE signals SET outcome = ?, exit_price = ?, pips = ? WHERE id = ?
    """, (outcome, exit_price, pips, signal_id))
    conn.commit()
    conn.close()
    return outcome

def get_winrate():
    conn = _get_conn()
    total = conn.execute("SELECT COUNT(*) FROM signals WHERE outcome IN ('WIN', 'LOSS')").fetchone()[0]
    wins = conn.execute("SELECT COUNT(*) FROM signals WHERE outcome = 'WIN'").fetchone()[0]
    losses = conn.execute("SELECT COUNT(*) FROM signals WHERE outcome = 'LOSS'").fetchone()[0]
    pending = conn.execute("SELECT COUNT(*) FROM signals WHERE outcome IS NULL OR outcome = 'PENDING'").fetchone()[0]
    conn.close()
    winrate = round((wins / total * 100), 1) if total > 0 else 0
    return {
        "total": total + pending,
        "closed": total,
        "wins": wins,
        "losses": losses,
        "pending": pending,
        "winrate": winrate,
    }

def get_recent_signals(limit=10):
    conn = _get_conn()
    rows = conn.execute("""
        SELECT * FROM signals ORDER BY id DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_pending_signals():
    conn = _get_conn()
    rows = conn.execute("""
        SELECT * FROM signals WHERE outcome IS NULL OR outcome = 'PENDING' ORDER BY id DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def check_outcomes(current_price, min_age_minutes=30):
    pending = get_pending_signals()
    results = []
    now = datetime.now()
    for s in pending:
        signal_type = s["signal"]
        tp = s["take_profit"]
        sl = s["stop_loss"]
        entry = s["entry"]
        if not tp or not sl or not entry:
            continue

        # skip sinyal yg masih terlalu muda — kasih waktu buat harga bergerak
        ts = s.get("timestamp")
        if ts:
            try:
                age = now - datetime.fromisoformat(ts)
                if age.total_seconds() < min_age_minutes * 60:
                    continue
            except Exception:
                pass

        outcome = None
        if signal_type == "BUY":
            if current_price >= tp:
                outcome = "WIN"
                pips = round((tp - entry) * 10, 1)
            elif current_price <= sl:
                outcome = "LOSS"
                pips = round((sl - entry) * 10, 1)
        elif signal_type == "SELL":
            if current_price <= tp:
                outcome = "WIN"
                pips = round((entry - tp) * 10, 1)
            elif current_price >= sl:
                outcome = "LOSS"
                pips = round((entry - sl) * 10, 1)
        if outcome:
            conn = _get_conn()
            conn.execute(
                "UPDATE signals SET outcome = ?, exit_price = ?, pips = ? WHERE id = ?",
                (outcome, current_price, pips, s["id"]),
            )
            conn.commit()
            conn.close()
            results.append({
                "signal_id": s["id"],
                "signal": signal_type,
                "entry": entry,
                "stop_loss": sl,
                "take_profit": tp,
                "outcome": outcome,
                "exit_price": current_price,
                "pips": pips,
                "timestamp": s["timestamp"],
            })
    return results

def auto_close_expired(hours=24):
    conn = _get_conn()
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
    rows = conn.execute(
        "SELECT id FROM signals WHERE (outcome IS NULL OR outcome = 'PENDING') AND timestamp < ?",
        (cutoff,),
    ).fetchall()
    for r in rows:
        conn.execute(
            "UPDATE signals SET outcome = 'NONE', pips = 0 WHERE id = ?",
            (r["id"],),
        )
    conn.commit()
    conn.close()
    return len(rows)
