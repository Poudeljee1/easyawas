"""
run_scanner_b.py — Hourly TJL Scanner B
  • Reads today's premarket_gappers_YYYY-MM-DD.json for the universe
  • Runs TJL conditions on every ticker (all time logic in America/New_York)
  • Saves tjl_watchlist_YYYY-MM-DD_HHMMet.json
  • For every new PASS signal → places a simulated paper trade (once per ticker/day)
  • Positions are monitored by run_position_monitor.py and carry overnight

Called by Task Scheduler every hour, 10:00 AM – 3:30 PM ET, weekdays.
"""

import io
import json
import os
import sys
from datetime import datetime, timezone

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ── Local engine ──────────────────────────────────────────────────────────────
sys.path.insert(0, r"C:\Users\USER\hello")
from paper_trade_engine import (
    WORK_DIR,
    now_et, today_str,
    load_state, save_state,
    already_traded_today,
    evaluate_tjl,
    place_paper_trade,
)

# ── Time gate: 10:00 AM – 3:30 PM ET weekdays ────────────────────────────────
WINDOW_START_H, WINDOW_START_M = 10,  0
WINDOW_END_H,   WINDOW_END_M   = 15, 30

def within_window():
    net = now_et()
    if net.weekday() >= 5:            # Saturday=5, Sunday=6
        return False, f"weekend ({net.strftime('%A')})"
    hhmm = net.hour * 60 + net.minute
    ws   = WINDOW_START_H * 60 + WINDOW_START_M
    we   = WINDOW_END_H   * 60 + WINDOW_END_M
    if hhmm < ws:
        return False, f"before window ({net.strftime('%H:%M')} ET < 10:00)"
    if hhmm > we:
        return False, f"after window ({net.strftime('%H:%M')} ET > 15:30)"
    return True, "ok"

# ── Gappers universe ──────────────────────────────────────────────────────────

def load_gappers_universe():
    fn = os.path.join(WORK_DIR, f"premarket_gappers_{today_str()}.json")
    if not os.path.exists(fn):
        print(f"[WARN] Gappers file not found: {fn}")
        return []
    with open(fn, encoding="utf-8") as f:
        data = json.load(f)
    symbols = [g["symbol"] for g in data.get("gappers", [])]
    print(f"[INFO] Gappers universe ({len(symbols)}): {', '.join(symbols)}")
    return symbols

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    net = now_et()
    print(f"\n{'='*60}")
    print(f"  Scanner B — TJL  |  {net.strftime('%Y-%m-%d %H:%M ET')}")
    print(f"{'='*60}")

    # Time gate
    ok, reason = within_window()
    if not ok:
        print(f"[GATE] Scan skipped: {reason}")
        return

    # Universe
    symbols = load_gappers_universe()
    if not symbols:
        print("[WARN] Empty universe — nothing to scan.")
        return

    # Load persistent state
    state = load_state()

    # ── Run TJL on every ticker ───────────────────────────────────────────────
    all_results = []
    hits        = []

    for sym in symbols:
        print(f"\n  Scanning {sym} …")
        res = evaluate_tjl(sym)
        all_results.append(res)

        marker = "PASS ✓" if res["result"] == "pass" else res["result"].upper()
        print(f"    → {marker}  |  {res['reason']}")

        # ── Paper trade on PASS ───────────────────────────────────────────────
        if res["result"] == "pass":
            hits.append(res)
            if already_traded_today(sym, state):
                print(f"    [SKIP] Already traded {sym} today")
            else:
                entry_px = res["curr_px"]
                place_paper_trade(sym, entry_px, state)
                save_state(state)

    # ── Save watchlist JSON ───────────────────────────────────────────────────
    timestamp_et = net.strftime("%H%MET")
    out_file = os.path.join(WORK_DIR, f"tjl_watchlist_{today_str()}_{timestamp_et}.json")
    out_data = {
        "scanned_at":        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "scan_time_et":      net.strftime("%H:%M ET"),
        "window":            "10:00-15:30 ET",
        "extended_hours":    True,
        "candidates_checked": len(symbols),
        "hits":              [r["symbol"] for r in hits],
        "all_results":       all_results,
    }
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(out_data, f, indent=2)
    print(f"\n[SAVED] {out_file}")

    # ── Summary ───────────────────────────────────────────────────────────────
    pass_syms = [r["symbol"] for r in hits]
    print(f"\n[SUMMARY] {len(symbols)} scanned | "
          f"{len(hits)} PASS: {pass_syms or 'none'}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
