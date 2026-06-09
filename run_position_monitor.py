"""
run_position_monitor.py — 5-Minute Paper Position Monitor
  • Loads all open paper positions from paper_trading_state.json
  • Fetches live price for each via yfinance (America/New_York time gate)
  • Closes positions that hit TP (+3%) or SL (-1.5%) — NO time-based exit
  • Positions that are still open at 3:30 PM are saved as-is and resume
    next trading day; hold time accumulates across all calendar days
  • Appends every closed trade to paper_trades_15day.xlsx

Called by Task Scheduler every 5 minutes, 10:00 AM – 3:30 PM ET, weekdays.
"""

import io
import sys
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, r"C:\Users\USER\hello")
from paper_trade_engine import (
    now_et,
    load_state, save_state,
    check_and_close_positions,
)

# ── Time gate — America/New_York, market hours only ───────────────────────────
# The gate only controls whether this *check cycle* runs.
# Positions that are open when the gate closes simply stay open in state.json
# and are picked up again at 10:00 AM the next trading day.
WINDOW_START_H, WINDOW_START_M = 10,  0
WINDOW_END_H,   WINDOW_END_M   = 15, 30   # stop new checks at/after market close

def within_window():
    net  = now_et()   # America/New_York, always
    if net.weekday() >= 5:   # 5=Saturday, 6=Sunday
        return False, f"weekend ({net.strftime('%A')})"
    hhmm = net.hour * 60 + net.minute
    ws   = WINDOW_START_H * 60 + WINDOW_START_M
    we   = WINDOW_END_H   * 60 + WINDOW_END_M
    if not (ws <= hhmm <= we):
        return False, f"outside market hours ({net.strftime('%H:%M')} ET)"
    return True, "ok"

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    net = now_et()
    print(f"\n[MONITOR] {net.strftime('%Y-%m-%d %H:%M ET')}")

    ok, reason = within_window()
    if not ok:
        # Positions are NOT closed — they carry over to the next session.
        print(f"[GATE] Monitor idle: {reason}  (open positions preserved in state.json)")
        return

    state    = load_state()
    open_pos = state.get("open_positions", {})

    if not open_pos:
        print("  No open positions.")
        return

    # Show entry context for each open position
    for sym, pos in open_pos.items():
        held_mins = round((net.timestamp() - pos["entry_unix"]) / 60, 1)
        print(f"  {sym:6s}  entry=${pos['entry_price']:.4f}  "
              f"TP=${pos['tp_price']:.4f}  SL=${pos['sl_price']:.4f}  "
              f"held={held_mins:.0f}m")

    closed = check_and_close_positions(state)
    save_state(state)

    still_open = list(state["open_positions"].keys())
    print(f"  Closed this cycle: {len(closed)} | "
          f"Still open: {still_open if still_open else 'none'}")

    if closed:
        pnl_total = sum(t["pnl"] for t in closed)
        print(f"  Cycle P&L: ${pnl_total:+.2f}")


if __name__ == "__main__":
    main()
