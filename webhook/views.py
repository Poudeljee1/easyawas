"""
webhook/views.py -- TradingView alert webhook receiver.

TradingView sends a POST with JSON body when an alert fires.
This view places an Alpaca bracket order and sends a Telegram confirmation.

Expected JSON from TradingView alert message:
{
  "symbol":   "{{ticker}}",
  "price":    "{{close}}",
  "strategy": "TJL_Long",
  "action":   "BUY",
  "tp_pct":   "3.0",
  "sl_pct":   "1.5"
}

Webhook URL to paste in TradingView:
  https://easyawas.onrender.com/webhook/trade/

Security: requests must include header  X-TV-Secret: <WEBHOOK_SECRET>
Set WEBHOOK_SECRET in Render environment variables.
"""

import json, os, logging, requests
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


# ── Alpaca helpers ─────────────────────────────────────────────────────────────

def alpaca_headers():
    return {
        "APCA-API-KEY-ID":     ALPACA_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET,
        "Content-Type":        "application/json",
    }


def place_bracket_order(symbol, entry_price, tp_pct, sl_pct):
    """Places a bracket (entry + TP + SL) order on Alpaca paper account."""
    tp_price = round(entry_price * (1 + tp_pct / 100), 2)
    sl_price = round(entry_price * (1 - sl_pct / 100), 2)
    qty      = max(1, int(POSITION_SIZE / entry_price))

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
            "order_id":  data.get("id"),
            "symbol":    symbol,
            "qty":       qty,
            "tp_price":  tp_price,
            "sl_price":  sl_price,
            "status":    data.get("status"),
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
        tp_pct   = float(body.get("tp_pct",  3.0))
        sl_pct   = float(body.get("sl_pct",  1.5))

        try:
            price = float(body.get("price", 0))
        except (ValueError, TypeError):
            price = 0.0

        if not symbol or price <= 0:
            logger.warning("Webhook: missing symbol or price: %s", body)
            return JsonResponse({"error": "missing symbol or price"}, status=400)

        if action != "BUY":
            return JsonResponse({"status": "skipped", "reason": "only BUY supported"})

        logger.info("Webhook received: %s %s @ $%.2f tp=%.1f%% sl=%.1f%%",
                    strategy, symbol, price, tp_pct, sl_pct)

        # ── Place Alpaca order ─────────────────────────────────────────────────
        order = place_bracket_order(symbol, price, tp_pct, sl_pct)

        if order:
            msg = (
                f"TradingView Alert Fired\n"
                f"Strategy : {strategy}\n"
                f"Stock    : {symbol} @ ${price:.2f}\n"
                f"Action   : BUY {order['qty']} shares\n"
                f"TP       : ${order['tp_price']}  (+{tp_pct}%)\n"
                f"SL       : ${order['sl_price']}  (-{sl_pct}%)\n"
                f"Order ID : {order['order_id']}"
            )
            send_telegram(msg)
            logger.info("Order placed: %s", order)
            return JsonResponse({"status": "order_placed", "order": order})
        else:
            send_telegram(
                f"ALERT: Webhook received {symbol} signal but Alpaca order FAILED.\n"
                f"Strategy: {strategy}  Price: ${price:.2f}"
            )
            return JsonResponse({"error": "alpaca order failed"}, status=500)

    def get(self, request):
        return JsonResponse({"status": "webhook endpoint live", "method": "POST required"})
