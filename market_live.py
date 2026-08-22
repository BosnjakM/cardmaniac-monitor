#!/usr/bin/env python3
"""Live sealed comps: TCGPlayer (tcgcsv.com) + PriceCharting. USD → CHF."""

from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CACHE_PATH = ROOT / "price_cache.json"
CACHE_TTL_SEC = 12 * 3600

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 Safari/537.36"
)

TCG_GROUPS_URL = "https://tcgcsv.com/tcgplayer/3/groups"
TCG_PRODUCTS_URL = "https://tcgcsv.com/tcgplayer/3/{gid}/products"
TCG_PRICES_URL = "https://tcgcsv.com/tcgplayer/3/{gid}/prices"
PC_SEARCH = "https://www.pricecharting.com/search-products?q={q}&type=prices"
FX_URL = "https://api.frankfurter.app/latest?from=USD&to=CHF"

KIND_PRODUCT = {
    "booster": (["booster pack"], ["bundle", "box", "code card", "sleeved", "art bundle", "mini"]),
    "display": (["booster box"], ["case"]),
    "etb": (["elite trainer box"], ["pokemon center", "case", "exclusive", "dollar general"]),
    "bundle": (["booster bundle"], ["display", "case", "surprise"]),
    "poster": (["poster collection"], ["case"]),
    "tin": (["tin"], ["case", "collection box"]),
}


def _curl(url: str, timeout: int = 20, follow: bool = True) -> bytes:
    cmd = [
        "curl",
        "-sS",
        "--fail",
        "--http1.1",
        "-4",
        "--max-time",
        str(timeout),
        "-A",
        UA,
        url,
    ]
    if follow:
        cmd.insert(2, "-L")
    result = subprocess.run(cmd, capture_output=True, check=False)
    if result.returncode != 0 or not result.stdout:
        raise RuntimeError(f"curl {result.returncode} for {url}")
    return result.stdout


def _load_cache() -> dict:
    if not CACHE_PATH.exists():
        return {}
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _save_cache(cache: dict) -> None:
    CACHE_PATH.write_text(
        json.dumps(cache, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _fresh(entry: dict | None) -> bool:
    if not entry:
        return False
    try:
        return time.time() - float(entry.get("ts", 0)) < CACHE_TTL_SEC
    except (TypeError, ValueError):
        return False


def usd_to_chf() -> float:
    cache = _load_cache()
    fx = cache.get("usd_chf")
    if _fresh(fx) and fx.get("rate"):
        return float(fx["rate"])
    try:
        data = json.loads(_curl(FX_URL, timeout=12))
        rate = float(data["rates"]["CHF"])
    except Exception:  # noqa: BLE001
        rate = 0.80
    cache = _load_cache()
    cache["usd_chf"] = {"ts": time.time(), "rate": rate}
    _save_cache(cache)
    return rate


def listing_lang(title_l: str) -> str:
    if any(
        w in title_l
        for w in (
            "englisch",
            "english",
            "eng edition",
            "en edition",
            "language en",
            "sprache en",
            "us version",
            "usa",
        )
    ):
        return "en"
    if any(w in title_l for w in ("japan", "japanese", "jp edition", "japanisch")):
        return "jp"
    if any(w in title_l for w in ("französ", "francais", "french", "fr edition")):
        return "fr"
    if any(w in title_l for w in ("italien", "italiano", "italian", "it edition")):
        return "it"
    if any(w in title_l for w in ("deutsch", "german", "de edition", "deutsche")):
        return "de"
    # Ricardo.ch default: German sealed, not US EN comps
    return "de"


def lang_factor(item: dict, lang: str) -> float:
    """US/EN comps overstate DE/EU sealed — especially vintage."""
    if lang in {"en", "jp"}:
        return 1.0
    custom = item.get("de_vs_en")
    if custom is not None:
        return float(custom)
    unit = float(item.get("unit_chf") or 0)
    # Vintage-ish catalog prices → steep DE haircut vs PriceCharting EN
    if unit >= 25:
        return 0.35
    return 0.80


def _pc_query(item: dict, matched_alias: str) -> str | None:
    by_alias = item.get("pc_by_alias") or {}
    folded_alias = (matched_alias or "").casefold()
    if folded_alias in by_alias:
        return by_alias[folded_alias]
    q = item.get("pc_query")
    if q:
        return q
    return None


def pricecharting_usd(query: str) -> dict | None:
    cache = _load_cache()
    key = f"pc:{query.casefold()}"
    hit = (cache.get("quotes") or {}).get(key)
    if _fresh(hit) and hit.get("usd"):
        return hit

    q = re.sub(r"\s+", "+", query.strip())
    url = PC_SEARCH.format(q=q)
    try:
        html = _curl(url, timeout=20).decode("utf-8", errors="ignore")
    except Exception:  # noqa: BLE001
        return None
    if "used_price" not in html:
        return None
    block = re.search(
        r'id="used_price"[\s\S]{0,400}?class="price js-price">\s*\$([0-9,.]+)',
        html,
    )
    if not block:
        return None
    usd = float(block.group(1).replace(",", ""))
    if usd <= 0:
        return None
    canonical = None
    m = re.search(
        r'rel="canonical" href="(https://www\.pricecharting\.com/game/[^"]+)"',
        html,
    )
    if m:
        canonical = m.group(1)
    entry = {"ts": time.time(), "usd": usd, "url": canonical or url, "query": query}
    cache = _load_cache()
    cache.setdefault("quotes", {})[key] = entry
    _save_cache(cache)
    return entry


def _tcg_groups() -> list[dict]:
    cache = _load_cache()
    g = cache.get("tcg_groups")
    if _fresh(g) and g.get("results"):
        return g["results"]
    try:
        data = json.loads(_curl(TCG_GROUPS_URL, timeout=20))
        results = data.get("results") or []
    except Exception:  # noqa: BLE001
        return (g or {}).get("results") or []
    cache = _load_cache()
    cache["tcg_groups"] = {"ts": time.time(), "results": results}
    _save_cache(cache)
    return results


def _tcg_group_catalog(gid: int) -> tuple[list[dict], dict[int, list[dict]]]:
    cache = _load_cache()
    key = f"tcg_group_{gid}"
    hit = cache.get(key)
    if _fresh(hit) and hit.get("products") is not None:
        prices_by = {int(k): v for k, v in (hit.get("prices") or {}).items()}
        return hit["products"], prices_by
    try:
        products = json.loads(_curl(TCG_PRODUCTS_URL.format(gid=gid), timeout=20))
        prices = json.loads(_curl(TCG_PRICES_URL.format(gid=gid), timeout=20))
    except Exception:  # noqa: BLE001
        return [], {}
    prod_rows = products.get("results") or []
    prices_by: dict[int, list[dict]] = {}
    for row in prices.get("results") or []:
        try:
            pid = int(row["productId"])
        except (KeyError, TypeError, ValueError):
            continue
        prices_by.setdefault(pid, []).append(row)
    cache = _load_cache()
    cache[key] = {
        "ts": time.time(),
        "products": prod_rows,
        "prices": {str(k): v for k, v in prices_by.items()},
    }
    _save_cache(cache)
    return prod_rows, prices_by


def _pick_group(item: dict, groups: list[dict]) -> dict | None:
    gid = item.get("tcg_group_id")
    if gid:
        for g in groups:
            if g.get("groupId") == gid:
                return g
    needles = []
    if item.get("tcg_group"):
        needles.append(str(item["tcg_group"]).casefold())
    q = (item.get("pc_query") or "").casefold()
    q = re.sub(r"^pokemon\s+", "", q)
    q = re.sub(
        r"\s+(booster pack|booster box|elite trainer box|booster bundle|poster collection|tin)\s*$",
        "",
        q,
    )
    if q:
        needles.append(q)
    if not needles:
        return None
    best = None
    best_len = 10**9
    for g in groups:
        gn = (g.get("name") or "").casefold()
        simple = re.sub(r"^[a-z0-9]+:\s*", "", gn)
        for n in needles:
            if n and (n == simple or n == gn or n in simple or simple in n):
                if len(simple) < best_len:
                    best = g
                    best_len = len(simple)
    return best


def _pick_product(kind: str, products: list[dict]) -> dict | None:
    need, ban = KIND_PRODUCT.get(kind, ([], []))
    hits = []
    for p in products:
        name = (p.get("name") or "").casefold()
        if "code card" in name:
            continue
        if not any(n in name for n in need):
            continue
        if any(b in name for b in ban):
            continue
        hits.append(p)
    if not hits:
        return None
    hits.sort(key=lambda p: len(p.get("name") or ""))
    return hits[0]


def tcgplayer_usd(item: dict) -> dict | None:
    if str(item.get("id") or "").startswith("generic-"):
        return None
    groups = _tcg_groups()
    group = _pick_group(item, groups)
    if not group:
        return None
    products, prices_by = _tcg_group_catalog(int(group["groupId"]))
    prod = _pick_product(item.get("kind") or "", products)
    if not prod:
        return None
    rows = prices_by.get(int(prod["productId"])) or []
    usd = None
    for row in rows:
        mp = row.get("marketPrice")
        if mp:
            usd = float(mp)
            break
    if not usd or usd <= 0:
        return None
    return {
        "usd": usd,
        "url": prod.get("url") or "",
        "name": prod.get("name"),
        "group": group.get("name"),
    }


def quote_item(item: dict, title: str, qty: int) -> dict | None:
    """CHF market for qty units. Prefer TCGPlayer dump, else PriceCharting."""
    if qty < 1:
        return None
    title_l = title.casefold()
    lang = listing_lang(title_l)
    factor = lang_factor(item, lang)
    rate = usd_to_chf()

    tcg = tcgplayer_usd(item)
    if tcg:
        unit = tcg["usd"] * rate * factor
        market = round(unit * qty, 2)
        note = (
            f"TCGPlayer {tcg['name']} ${tcg['usd']:.2f} → {unit:.0f} CHF/Stk"
            + (f" (×{factor:.2f} {lang.upper()} vs EN)" if factor < 1 else "")
        )
        return {
            "market": market,
            "unit": round(unit, 2),
            "source": "TCGPlayer",
            "note": note,
            "url": tcg.get("url") or "",
            "lang": lang,
            "usd": tcg["usd"],
        }

    query = _pc_query(item, "")
    if not query:
        return None
    pc = pricecharting_usd(query)
    if not pc:
        return None
    unit = pc["usd"] * rate * factor
    market = round(unit * qty, 2)
    note = (
        f"PriceCharting ungraded ${pc['usd']:.2f} → {unit:.0f} CHF/Stk"
        + (f" (×{factor:.2f} {lang.upper()} vs EN)" if factor < 1 else "")
    )
    return {
        "market": market,
        "unit": round(unit, 2),
        "source": "PriceCharting",
        "note": note,
        "url": pc.get("url") or "",
        "lang": lang,
        "usd": pc["usd"],
    }

