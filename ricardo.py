#!/usr/bin/env python3
"""Ricardo Pokémon auctions ending soon vs live TCGPlayer/PriceCharting comps."""

from __future__ import annotations

import json
import re
import subprocess
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from market_live import quote_item

ROOT = Path(__file__).resolve().parent
RICARDO_SEEN = ROOT / "seen_ricardo.json"
RICARDO_MARKET = ROOT / "ricardo_market.json"

SEARCH_URLS = [
    "https://www.ricardo.ch/de/s/pokemon/?sort=end_date&offer_type=auction",
    "https://www.ricardo.ch/de/s/pokemon/?sort=end_date&offer_type=auction&page=2",
]

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 Safari/537.36"
)

WINDOW_MAX_MIN = 30
MIN_PROFIT_CHF = 25
MIN_RATIO = 2.0  # 100% upside → market at least 2x cost
BIG_PROFIT_CHF = 50

KIND_WORDS = {
    "display": ("display", "booster box", "boosterbox", "booster-box", "36er"),
    "etb": (
        "elite trainer",
        "top trainer",
        "top-trainer",
        "trainer box",
        "trainer-box",
        " etb",
        "ttb",
    ),
    "tin": (" tin", "dose"),
    "bundle": ("bundle", "6-pack", "6 pack", "6er pack"),
    "poster": ("poster", "poster-kollektion", "poster collection"),
    "booster": (
        "sleeved booster",
        "booster pack",
        "boosterpacks",
        "booster packs",
        " booster",
    ),
}

RESEAL_WORDS = (
    "reseal",
    "re-seal",
    "repack",
    "geöffnet",
    "geoeffnet",
    "opened",
    "nicht original",
    "tamper",
)


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.casefold()


def _curl_get(url: str, timeout: int = 25) -> bytes:
    cmd = [
        "curl",
        "-sL",
        "--fail",
        "--http1.1",
        "-4",
        "--retry",
        "1",
        "--max-time",
        str(timeout),
        "-A",
        UA,
        "-H",
        "Accept-Language: de-CH,de;q=0.9",
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, check=False)
    if result.returncode != 0 or not result.stdout:
        raise RuntimeError(f"curl {result.returncode} for {url}")
    if b"Ricardo Captcha" in result.stdout[:800] or b"Just a moment" in result.stdout[:800]:
        raise RuntimeError("Cloudflare/Captcha")
    return result.stdout


def _parse_articles(html: str) -> list[dict]:
    parts = re.findall(r"self\.__next_f\.push\((.*?)\)<\/script>", html, re.S)
    articles: dict[str, dict] = {}
    for raw in parts:
        try:
            pushed = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(pushed, list) or len(pushed) < 2:
            continue
        payload = pushed[1]
        if not isinstance(payload, str) or "bidPrice" not in payload:
            continue
        try:
            data = json.loads(payload.split(":", 1)[1])
        except (json.JSONDecodeError, IndexError):
            continue

        def walk(obj) -> None:
            if isinstance(obj, dict):
                arts = obj.get("articles")
                if (
                    isinstance(arts, list)
                    and arts
                    and isinstance(arts[0], dict)
                    and "id" in arts[0]
                    and "title" in arts[0]
                ):
                    for art in arts:
                        articles[str(art["id"])] = art
                    return
                for val in obj.values():
                    walk(val)
            elif isinstance(obj, list):
                for val in obj:
                    walk(val)

        walk(data)
    return list(articles.values())


def fetch_ending_auctions() -> list[dict]:
    by_id: dict[str, dict] = {}
    for url in SEARCH_URLS:
        html = _curl_get(url).decode("utf-8", errors="ignore")
        for art in _parse_articles(html):
            by_id[str(art.get("id"))] = art
    return list(by_id.values())


def _qty(title_l: str, kind: str | None = None) -> int:
    m = re.search(r"\b(\d+)\s*[x×*]", title_l)
    if m:
        n = int(m.group(1))
        if 2 <= n <= 48:
            return n
    if kind in {"bundle", "etb", "tin", "poster", "display"}:
        return 1
    patterns = [
        r"\b(\d+)\s*(?:stk|stueck|stück|packs?|booster)\b",
        r"\b(\d+)\s*er\b",
    ]
    for pat in patterns:
        m = re.search(pat, title_l)
        if m:
            n = int(m.group(1))
            if 2 <= n <= 48:
                return n
    return 1


def _looks_single_card(title_l: str) -> bool:
    if re.search(r"\b\d{1,3}\s*/\s*\d{2,3}\b", title_l) and "booster" not in title_l:
        return True
    if "karte" in title_l and not any(
        w in title_l for w in ("booster", "display", "trainer", "tin", "bundle", "poster")
    ):
        return True
    return False


def _kind(title_l: str) -> str | None:
    for kind, words in KIND_WORDS.items():
        if any(w in title_l for w in words):
            return kind
    return None


def load_market() -> list[dict]:
    raw = json.loads(RICARDO_MARKET.read_text(encoding="utf-8"))
    items = []
    for item in raw.get("items", []):
        aliases = sorted(
            {_fold(a) for a in item.get("aliases") or [] if a},
            key=len,
            reverse=True,
        )
        items.append({**item, "aliases": aliases})
    return items


def match_market(title: str, market_items: list[dict]) -> tuple[dict, int, bool] | None:
    title_l = _fold(title)
    if _looks_single_card(title_l):
        return None
    kind = _kind(title_l)
    if not kind:
        return None

    best = None
    best_len = 0
    generic = None
    generic_len = 0
    for item in market_items:
        if item.get("kind") != kind:
            continue
        is_generic = str(item.get("id") or "").startswith("generic-")
        for alias in item["aliases"]:
            if not alias or alias not in title_l:
                continue
            if is_generic:
                if len(alias) > generic_len:
                    generic = item
                    generic_len = len(alias)
            elif len(alias) > best_len:
                best = item
                best_len = len(alias)
    if not best:
        best = generic
    if not best:
        return None

    qty = _qty(title_l, kind)
    reseal = any(w in title_l for w in RESEAL_WORDS)
    return best, qty, reseal


def _shipping(art: dict) -> float:
    costs = []
    for row in art.get("shipping") or []:
        try:
            costs.append(float(row.get("cost")))
        except (TypeError, ValueError):
            continue
    return min(costs) if costs else 0.0


def _minutes_left(end_date: str | None) -> float | None:
    if not end_date:
        return None
    try:
        end = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (end - datetime.now(timezone.utc)).total_seconds() / 60.0


def _listing_url(art: dict) -> str:
    title = art.get("title") or "pokemon"
    slug = re.sub(r"[^a-z0-9]+", "-", _fold(title)).strip("-")[:80]
    aid = art.get("id")
    if slug:
        return f"https://www.ricardo.ch/de/a/{slug}-{aid}/"
    return f"https://www.ricardo.ch/de/a/{aid}"


def _load_seen() -> set[str]:
    if not RICARDO_SEEN.exists():
        return set()
    data = json.loads(RICARDO_SEEN.read_text(encoding="utf-8"))
    return {str(x) for x in data.get("alerted_ids", [])}


def _save_seen(ids: set[str]) -> None:
    # Keep the file from growing forever — last 400 alerts is enough.
    keep = sorted(ids)[-400:]
    RICARDO_SEEN.write_text(
        json.dumps({"alerted_ids": keep}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def evaluate_auctions(articles: list[dict], market_items: list[dict]) -> list[dict]:
    deals = []
    for art in articles:
        if not art.get("hasAuction"):
            continue
        mins = _minutes_left(art.get("endDate"))
        if mins is None or mins <= 0 or mins > WINDOW_MAX_MIN:
            continue
        matched = match_market(art.get("title") or "", market_items)
        if not matched:
            continue
        item, qty, reseal = matched
        title = art.get("title") or ""
        catalog_market = float(item.get("unit_chf") or 0) * qty
        source = "Katalog"
        source_note = f"Katalog {item.get('id')} {qty}× {item.get('unit_chf')} CHF"
        source_url = ""
        try:
            live = quote_item(item, title, qty)
        except Exception as exc:  # noqa: BLE001
            print(f"[Ricardo] Live-Preis Fehler: {exc}")
            live = None
        if live:
            market = live["market"]
            source = live["source"]
            source_note = live["note"]
            source_url = live.get("url") or ""
        else:
            market = catalog_market
        if reseal:
            market *= 0.55
            source_note += " · Reseal 55%"
        market = round(market, 2)
        bid = art.get("bidPrice")
        try:
            bid_f = float(bid) if bid is not None else 1.0
        except (TypeError, ValueError):
            bid_f = 1.0
        if bid_f <= 0:
            bid_f = 1.0
        ship = _shipping(art)
        cost = bid_f + ship
        profit = market - cost
        ratio = market / cost if cost else 0
        if profit < MIN_PROFIT_CHF:
            continue
        if ratio < MIN_RATIO and profit < BIG_PROFIT_CHF:
            continue
        deals.append(
            {
                "id": str(art.get("id")),
                "title": title,
                "url": _listing_url(art),
                "bid": bid_f,
                "shipping": ship,
                "cost": round(cost, 2),
                "market": market,
                "profit": round(profit, 2),
                "ratio": round(ratio, 2),
                "minutes": round(mins, 1),
                "qty": qty,
                "catalog": item.get("id"),
                "catalog_market": round(catalog_market, 2),
                "source": source,
                "source_note": source_note,
                "source_url": source_url,
                "bids": art.get("bidsCount") or 0,
            }
        )
    deals.sort(key=lambda d: d["profit"], reverse=True)
    return deals


def check_ricardo(send_email) -> None:
    market_items = load_market()
    try:
        articles = fetch_ending_auctions()
    except Exception as exc:  # noqa: BLE001
        print(f"[Ricardo] FEHLER: {exc}")
        return

    print(f"[Ricardo] {len(articles)} Auktionen geladen")
    deals = evaluate_auctions(articles, market_items)
    print(f"[Ricardo] Deals im 30-Min-Fenster: {len(deals)}")

    seen = _load_seen()
    if not RICARDO_SEEN.exists():
        _save_seen(seen)
    fresh = [d for d in deals if d["id"] not in seen]
    for d in deals:
        print(
            f"  · {d['minutes']:.0f}min  bid {d['bid']:.0f}  markt {d['market']:.0f}  "
            f"+{d['profit']:.0f} ({d['ratio']:.1f}x {d.get('source','')})  {d['title'][:60]}"
        )

    if fresh:
        if len(fresh) == 1:
            d = fresh[0]
            subject = f"💰 Ricardo Deal: {d['title'][:70]}"
        else:
            subject = f"💰 Ricardo: {len(fresh)} Deals laufen in ≤30 Min aus"
        lines = [
            "Pokémon-Auktionen auf Ricardo, die bald enden und unter Schätzwert liegen:",
            "https://www.ricardo.ch/de/s/pokemon/?sort=end_date&offer_type=auction",
            "",
            "Regel: mind. 25 CHF Gewinn und (2x Marktwert oder ≥50 CHF Differenz).",
            "Markt: TCGPlayer (tcgcsv) oder PriceCharting, sonst Katalog. DE/FR/IT vs US-EN abgewertet.",
            "Reseal/geöffnet im Titel → 55%. Cardmarket/CollectHolo brauchen API-Keys.",
            "",
        ]
        for d in fresh:
            lines.append(f"- {d['title']}")
            lines.append(f"  {d['url']}")
            lines.append(
                f"  Gebot {d['bid']:.0f} CHF + Versand {d['shipping']:.0f} = {d['cost']:.0f} CHF"
            )
            lines.append(
                f"  Markt ~{d['market']:.0f} CHF → +{d['profit']:.0f} CHF / {d['ratio']:.1f}x "
                f"| noch {d['minutes']:.0f} min | {d['bids']} Gebote"
            )
            lines.append(f"  {d.get('source_note') or d['source']}")
            if d.get("source_url"):
                lines.append(f"  {d['source_url']}")
            lines.append("")
        send_email(subject, "\n".join(lines))
        print("[Ricardo] Mail gesendet.")
        _save_seen(seen | {d["id"] for d in fresh})
    else:
        print("[Ricardo] Keine neuen Deal-Mails.")
        if deals:
            _save_seen(seen | {d["id"] for d in deals})
