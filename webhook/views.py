"""
webhook/views.py -- TradingView alert webhook receiver.

Webhook URL: https://easyawas.onrender.com/webhook/trade/

Expected JSON from TradingView alert:
{
  "symbol":   "{{ticker}}",
  "price":    "{{close}}",
  "strategy": "VCP",
  "action":   "BUY",
  "tp_pct":   "20.0",
  "sl_pct":   "5.0"
}
"""

import json, os, logging, requests
from datetime import date
from django.http  import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger(__name__)

WEBHOOK_SECRET   = os.environ.get("WEBHOOK_SECRET", "")
ALPACA_KEY       = os.environ.get("ALPACA_API_KEY", "")
ALPACA_SECRET    = os.environ.get("ALPACA_SECRET_KEY", "")
ALPACA_BASE_URL  = "https://paper-api.alpaca.markets"
TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
POSITION_SIZE    = float(os.environ.get("POSITION_SIZE", "1000"))

LOG_DIR = "/tmp"   # Render ephemeral storage — resets on redeploy


# ── Trade log (daily JSON file) ────────────────────────────────────────────────

def log_trade(record):
    """Append one trade record to today's log file."""
    path = f"{LOG_DIR}/vcp_trades_{date.today()}.json"
    trades = []
    try:
        with open(path) as f:
            trades = json.load(f)
    except Exception:
        pass
    trades.append(record)
    try:
        with open(path, "w") as f:
            json.dump(trades, f, indent=2)
    except Exception as e:
        logger.warning("Could not write trade log: %s", e)


def get_daily_log():
    """Return today's trade list."""
    path = f"{LOG_DIR}/vcp_trades_{date.today()}.json"
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return []


# ── Alpaca helpers ─────────────────────────────────────────────────────────────

def alpaca_headers():
    return {
        "APCA-API-KEY-ID":     ALPACA_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET,
        "Content-Type":        "application/json",
    }


def place_bracket_order(symbol, entry_price, tp_pct, sl_pct):
    """Places a bracket order with fractional qty on Alpaca paper account."""
    tp_price = round(entry_price * (1 + tp_pct / 100), 2)
    sl_price = round(entry_price * (1 - sl_pct / 100), 2)
    qty      = round(POSITION_SIZE / entry_price, 6)   # fractional shares

    payload = {
        "symbol":        symbol,
        "qty":           str(qty),
        "side":          "buy",
        "type":          "market",
        "time_in_force": "day",
        "order_class":   "bracket",
        "take_profit":   {"limit_price": str(tp_price)},
        "stop_loss":     {"stop_price": str(sl_price)},
    }

    resp = requests.post(
        f"{ALPACA_BASE_URL}/v2/orders",
        headers=alpaca_headers(),
        json=payload,
        timeout=10,
    )

    if resp.status_code in (200, 201):
        data = resp.json()
        return {
            "order_id": data.get("id"),
            "symbol":   symbol,
            "qty":      qty,
            "tp_price": tp_price,
            "sl_price": sl_price,
            "status":   data.get("status"),
        }
    else:
        logger.error("Alpaca order failed: %s %s", resp.status_code, resp.text)
        return None


# ── Telegram helper ────────────────────────────────────────────────────────────

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": message},
            timeout=8,
        )
    except Exception as e:
        logger.warning("Telegram failed: %s", e)


# ── Webhook view ───────────────────────────────────────────────────────────────

@method_decorator(csrf_exempt, name="dispatch")
class TradeWebhookView(View):

    def post(self, request):
        # ── Security check ─────────────────────────────────────────────────────
        if WEBHOOK_SECRET:
            token = request.headers.get("X-TV-Secret", "")
            if token != WEBHOOK_SECRET:
                logger.warning("Webhook: bad secret from %s", request.META.get("REMOTE_ADDR"))
                return JsonResponse({"error": "unauthorized"}, status=403)

        # ── Parse body ─────────────────────────────────────────────────────────
        try:
            body = json.loads(request.body.decode("utf-8"))
        except Exception:
            return JsonResponse({"error": "invalid JSON"}, status=400)

        symbol   = body.get("symbol", "").upper().strip()
        strategy = body.get("strategy", "UNKNOWN")
        action   = body.get("action", "BUY").upper()
        tp_pct   = float(body.get("tp_pct", 20.0))
        sl_pct   = float(body.get("sl_pct",  5.0))

        try:
            price = float(body.get("price", 0))
        except (ValueError, TypeError):
            price = 0.0

        if not symbol or price <= 0:
            return JsonResponse({"error": "missing symbol or price"}, status=400)

        if action != "BUY":
            return JsonResponse({"status": "skipped", "reason": "only BUY supported"})

        logger.info("Webhook: %s %s @ $%.2f tp=%.1f%% sl=%.1f%%",
                    strategy, symbol, price, tp_pct, sl_pct)

        # ── Place Alpaca order ─────────────────────────────────────────────────
        order = place_bracket_order(symbol, price, tp_pct, sl_pct)

        record = {
            "date":     str(date.today()),
            "symbol":   symbol,
            "strategy": strategy,
            "price":    price,
            "tp_pct":   tp_pct,
            "sl_pct":   sl_pct,
            "source":   "webhook",
        }

        if order:
            record.update({"order_id": order["order_id"], "qty": order["qty"],
                           "tp_price": order["tp_price"], "sl_price": order["sl_price"],
                           "result": "order_placed"})
            log_trade(record)
            msg = (
                f"VCP Alert Fired\n"
                f"Stock    : {symbol} @ ${price:.2f}\n"
                f"Shares   : {order['qty']:.4f}  (${POSITION_SIZE:.0f} position)\n"
                f"TP       : ${order['tp_price']}  (+{tp_pct}%)\n"
                f"SL       : ${order['sl_price']}  (-{sl_pct}%)\n"
                f"Order ID : {order['order_id']}"
            )
            send_telegram(msg)
            return JsonResponse({"status": "order_placed", "order": order})
        else:
            record["result"] = "order_failed"
            log_trade(record)
            send_telegram(f"VCP ALERT: {symbol} signal received but Alpaca order FAILED @ ${price:.2f}")
            return JsonResponse({"error": "alpaca order failed"}, status=500)

    def get(self, request):
        return JsonResponse({"status": "webhook endpoint live", "method": "POST required"})


# ── Daily summary view ─────────────────────────────────────────────────────────

@method_decorator(csrf_exempt, name="dispatch")
class DailySummaryView(View):
    """GET /webhook/summary/ — sends today's VCP trade log to Telegram."""

    def get(self, request):
        trades = get_daily_log()
        today  = str(date.today())

        if not trades:
            send_telegram(f"VCP Daily Summary — {today}\nNo trades today.")
            return JsonResponse({"status": "sent", "trades": 0})

        placed = [t for t in trades if t.get("result") == "order_placed"]
        lines  = [f"VCP Daily Summary — {today}",
                  f"Total signals: {len(trades)}  Orders placed: {len(placed)}",
                  f"Position size: ${POSITION_SIZE:.0f}/trade", ""]
        for t in placed:
            lines.append(
                f"  {t['symbol']:<8} @ ${t['price']:.2f}  "
                f"TP=${t.get('tp_price','?')}  SL=${t.get('sl_price','?')}  "
                f"({t.get('source','?')})"
            )
        send_telegram("\n".join(lines))
        return JsonResponse({"status": "sent", "trades": len(placed)})
