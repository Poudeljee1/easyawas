#!/bin/bash
# premarket_gappers_scan.sh — Premarket gappers scanner
# Data: Yahoo Finance day-gainers API -> Benzinga news catalysts -> JSON output

set -euo pipefail

python3 - << 'PYEOF'
import html as html_mod
import io, json, re, sys, time, urllib.request, urllib.error
from datetime import datetime, timezone

# Force UTF-8 stdout so Windows cp1252 doesn't blow up on Unicode chars
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

def fetch_json(url, timeout=25, retries=3):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={**HEADERS, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries - 1:
                wait = 6 * (attempt + 1)
                print(f"    Rate-limited, waiting {wait}s...")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("Max retries exceeded")

def fetch_html(url, timeout=22, retries=3):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={**HEADERS, "Accept": "text/html,*/*"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries - 1:
                wait = 12 * (attempt + 1)
                print(f"    Rate-limited, waiting {wait}s...")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("Max retries exceeded")

def safe_float(val, default=0.0):
    if val is None:
        return default
    try:
        return float(str(val).replace('%','').replace(',','').replace('+','').strip())
    except (ValueError, AttributeError):
        return default

# ── 1. Fetch Yahoo Finance day-gainers screener API ──────────────────────────
print("[1/3] Fetching Yahoo Finance gainers...")
SCREENER = (
    "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved"
    "?scrIds=day_gainers&count=50&formatted=false"
)
try:
    data = fetch_json(SCREENER)
    quotes = data["finance"]["result"][0].get("quotes", [])
    print(f"    API returned {len(quotes)} quotes")
except Exception as e:
    sys.exit(f"ERROR fetching Yahoo Finance screener: {e}")

# ── 2. Filter gainers ────────────────────────────────────────────────────────
# Field names: ticker, intradayprice, percentchange, dayvolume
gappers = []
for row in quotes:
    if not isinstance(row, dict):
        continue
    symbol = (row.get("ticker") or row.get("symbol") or "").strip().upper()
    if not symbol or not re.match(r'^[A-Z]{1,5}$', symbol):
        continue

    price   = safe_float(row.get("intradayprice") or row.get("regularMarketPrice"))
    gap_pct = safe_float(row.get("percentchange")  or row.get("regularMarketChangePercent"))
    # percentchange comes back as actual percent (e.g. 52.97), not decimal; regularMarketChangePercent is decimal
    if abs(gap_pct) < 2 and abs(gap_pct) > 0:
        gap_pct *= 100
    volume  = int(safe_float(row.get("dayvolume") or row.get("regularMarketVolume") or 0))

    if gap_pct <= 5 or price <= 3.0 or volume < 50_000:
        continue
    gappers.append({"symbol": symbol, "price": round(price, 2),
                    "gap_pct": round(gap_pct, 2), "premarket_volume": volume})

gappers.sort(key=lambda x: x["gap_pct"], reverse=True)
gappers = gappers[:10]
print(f"    After filters: {len(gappers)} gappers qualify")
for g in gappers:
    print(f"      {g['symbol']:6s}  {g['gap_pct']:+.1f}%  ${g['price']:.2f}  vol={g['premarket_volume']:,}")

if not gappers:
    print("WARNING: No gappers passed filters (market may be closed or pre-session).")
    out = {"scanned_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "gappers": []}
    fname = f"premarket_gappers_{datetime.now().strftime('%Y-%m-%d')}.json"
    with open(fname, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"Saved empty results -> {fname}")
    sys.exit(0)

# ── 3. Benzinga catalyst lookup ──────────────────────────────────────────────
print("[2/3] Fetching Benzinga catalysts...")

def _unescape_next_f(chunk):
    """Unescape a self.__next_f.push([1,"..."]) inner string."""
    # Unescape only \uXXXX sequences (safe for multi-byte UTF-8)
    text = re.sub(r'\\u([0-9a-fA-F]{4})',
                  lambda m: chr(int(m.group(1), 16)), chunk)
    text = (text.replace('\\"', '"')
                .replace('\\n', ' ')
                .replace('\\t', ' ')
                .replace('\\/', '/'))
    return html_mod.unescape(text)

def fetch_catalyst(ticker):
    url = f"https://www.benzinga.com/quote/{ticker}"
    try:
        html = fetch_html(url, timeout=20)
    except Exception as e:
        print(f"    {ticker}: fetch error - {e}")
        return None, []

    titles   = []
    teasers  = []
    catalyst = None

    # Strategy 1: React Server Components chunks (self.__next_f.push([1,"..."]))
    # These contain the actual news data, double-escaped inside a JSON string
    chunks = re.findall(r'self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)', html, re.S)
    for chunk in chunks:
        inner = _unescape_next_f(chunk)
        # Extract "title":"..." entries (news headlines)
        for t in re.findall(r'"title"\s*:\s*"([^"]{25,200})"', inner):
            if t not in titles and len(t) > 25:
                titles.append(t)
        # Extract "teaserText":"..." entries (one-line summaries)
        for t in re.findall(r'"teaserText"\s*:\s*"([^"]{20,400})"', inner):
            if t not in teasers and len(t) > 20:
                teasers.append(t)
        # "whyMoving" summary (Benzinga's own catalyst blurb)
        wm = re.search(r'"whyMoving"\s*:\s*"([^"]{20,500})"', inner)
        if wm and not catalyst:
            catalyst = wm.group(1).strip()

    # Strategy 2: <h3> headline tags in rendered HTML
    if len(titles) < 2:
        for m in re.findall(r'<h3[^>]*>(.*?)</h3>', html, re.S):
            clean = re.sub(r'<[^>]+>', '', m).strip()
            clean = re.sub(r'\s+', ' ', clean)
            if 30 < len(clean) < 200 and clean not in titles:
                titles.append(clean)

    # Strategy 3: article links
    if len(titles) < 2:
        for m in re.findall(r'<a[^>]+href="/(?:news|story)/[^"]*"[^>]*>(.*?)</a>', html, re.S | re.I):
            clean = re.sub(r'<[^>]+>', '', m).strip()
            if 30 < len(clean) < 180 and clean not in titles:
                titles.append(clean)

    # Boilerplate strings to reject
    JUNK = {
        "stock price", "quote", "get started", "{{", "earnings overview",
        "analyst rating", "history | benzinga", "sign up", "log in",
        "streetTracks gold shares", "unusual options activity", "streettracks",
        "activity calendar", "gld)", "gld )", "options activity",
        "profit calculator", "cash-secured put", "options calculator",
        "100x options", "put calculator", "covered call calculator",
        "editor's note", "editor’s note", "benchmark tracking etf",
    }

    def is_junk(s):
        sl = s.lower()
        return any(j.lower() in sl for j in JUNK)

    def clean_text(s):
        """Remove leftover escape artefacts and collapse whitespace."""
        s = re.sub(r'(?:\\{1,2}\s*){2,}', ' ', s)   # \\ \\ \\ noise
        s = re.sub(r'\s{2,}', ' ', s).strip()
        return s

    # Apply junk filter and cleanup
    clean_titles = [clean_text(html_mod.unescape(t)) for t in titles
                    if not is_junk(t) and len(t) > 25]
    # Prefer headlines that name the ticker, then any non-junk headline
    headlines = sorted(clean_titles, key=lambda t: ticker.upper() in t.upper(), reverse=True)[:2]

    # Build catalyst: prefer teasers that mention the ticker; fall back to any non-junk teaser
    if not catalyst:
        for t in teasers:
            cand = clean_text(html_mod.unescape(t))
            if is_junk(cand) or len(cand) < 20:
                continue
            if ticker.upper() in cand.upper():
                catalyst = re.split(r'(?<=[.!?])\s+', cand)[0]
                break
    if not catalyst:
        for t in teasers:
            cand = clean_text(html_mod.unescape(t))
            if is_junk(cand) or "stock price, charts" in cand.lower() or len(cand) < 20:
                continue
            catalyst = re.split(r'(?<=[.!?])\s+', cand)[0]
            break

    # Clean and validate final catalyst
    if catalyst:
        catalyst = clean_text(html_mod.unescape(catalyst))
        if is_junk(catalyst) or len(catalyst) < 12:
            catalyst = None

    if catalyst:
        catalyst = html_mod.unescape(catalyst)
        print(f"    {ticker}: {catalyst[:80]}...")
    else:
        print(f"    {ticker}: no catalyst found")

    return catalyst, headlines

results = []
for i, g in enumerate(gappers):
    catalyst, headlines = fetch_catalyst(g["symbol"])
    results.append({
        "rank":             i + 1,
        "symbol":           g["symbol"],
        "price":            g["price"],
        "gap_pct":          g["gap_pct"],
        "premarket_volume": g["premarket_volume"],
        "catalyst":         catalyst,
        "headlines":        headlines,
    })
    if i < len(gappers) - 1:
        time.sleep(3.0)

# ── 4. Save JSON ─────────────────────────────────────────────────────────────
print("[3/3] Saving results...")
out = {
    "scanned_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "gappers":    results,
}
fname = f"premarket_gappers_{datetime.now().strftime('%Y-%m-%d')}.json"
with open(fname, "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2, ensure_ascii=False)

# ── 5. One-line summary ──────────────────────────────────────────────────────
top3     = results[:3]
top3_str = ", ".join(
    "{} ({:.1f}%) -- {}".format(
        r["symbol"], r["gap_pct"],
        (r["catalyst"] or "no catalyst")[:60],
    )
    for r in top3
)
print(f"\nPremarket Gappers: {len(results)} names. Top: {top3_str}")
print(f"Saved -> {fname}")

PYEOF
