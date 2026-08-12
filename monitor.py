#!/usr/bin/env python3
"""Monitor Cardmaniac, CardCollectors, Manor, and Brack."""

from __future__ import annotations

import hashlib
import html as html_lib
import json
import os
import re
import smtplib
import ssl
import subprocess
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from email.message import EmailMessage
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# --- Cardmaniac (notify on ANY new pre-order product) ---
CARDMANIAC_URL = "https://cardmaniac.ch/collections/pre-order/products.json"
CARDMANIAC_PAGE = "https://cardmaniac.ch/collections/pre-order"
CARDMANIAC_SEEN = ROOT / "seen.json"

# --- CardCollectors (notify when watched products become in stock) ---
CARDCOLLECTORS_WATCHLIST = ROOT / "watchlist_cardcollectors.json"
CARDCOLLECTORS_STOCK = ROOT / "stock_cardcollectors.json"
CARDCOLLECTORS_API = "https://cardcollectors.ch/wp-json/wc/store/v1/products"

# --- Manor (Pokemon search → notify on 30th / 30 Jahre titles) ---
MANOR_SEEN = ROOT / "seen_manor.json"
MANOR_SEARCH = "https://www.manor.ch/de/search"
MANOR_KEYWORDS = [
    "30th",
    "30 jahre",
    "30-jahre",
    "30jährigen",
    "30-jährigen",
    "30 jaehrige",
]

# --- Ryu.land (30th Celebration collection + new related collections/products) ---
RYU_SEEN = ROOT / "seen_ryu.json"
RYU_COLLECTION = "30th-30th-celebration"
RYU_COLLECTION_URL = (
    f"https://ryu.land/collections/{RYU_COLLECTION}/products.json"
)
RYU_COLLECTIONS_JSON = "https://ryu.land/collections.json"

# --- Brack (notify only on keyword matches via public sitemaps) ---
BRACK_SEEN = ROOT / "seen_brack.json"
BRACK_STATE = ROOT / "brack_sitemap_state.json"
BRACK_SITEMAP_INDEX = (
    "https://www.brack.ch/exports/google/brack.ch/de/sitemap-index.xml"
)

# Match against URL slug (lowercase). Keep specific to avoid false positives.
BRACK_URL_KEYWORDS = [
    "30th",
    "30-jahre",
    "30jahre",
    "30-jaehrige",
    "30-jahrige",
]

# Highlight these on Cardmaniac (still notifies on all new products there)
CARDMANIAC_PRIORITY_KEYWORDS = [
    "30th celebration",
    "tech-sticker",
    "tech sticker",
    "sticker-kollektion",
    "sticker kollektion",
]

MAIL_TO = os.environ.get("MAIL_TO") or "mab151204@gmail.com"
SMTP_HOST = os.environ.get("SMTP_HOST") or "smtp.gmail.com"
SMTP_PORT = int(os.environ.get("SMTP_PORT") or "587")
SMTP_USER = os.environ.get("SMTP_USER") or ""
SMTP_PASS = os.environ.get("SMTP_PASS") or ""
FORCE_BRACK_SCAN = (os.environ.get("FORCE_BRACK_SCAN") or "").strip() in {
    "1",
    "true",
    "yes",
}

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 Safari/537.36"
)


def matches_keywords(title: str, keywords: list[str]) -> bool:
    lower = title.casefold()
    return any(k in lower for k in keywords)


def load_seen(path: Path) -> set[str]:
    if not path.exists():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    return {str(x) for x in data.get("product_ids", [])}


def save_seen(path: Path, product_ids: set[str] | list) -> None:
    ids = sorted(str(x) for x in product_ids)
    path.write_text(
        json.dumps({"product_ids": ids}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def send_email(subject: str, body: str) -> None:
    if not SMTP_USER or not SMTP_PASS:
        raise SystemExit(
            "SMTP_USER / SMTP_PASS fehlen. Bitte GitHub Secrets setzen (siehe README)."
        )

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = MAIL_TO
    msg.set_content(body)

    context = ssl.create_default_context()
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
        server.starttls(context=context)
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)

    print(f"Email gesendet an {MAIL_TO}: {subject}")


# ----- Cardmaniac -----


def fetch_cardmaniac() -> list[dict]:
    req = urllib.request.Request(
        CARDMANIAC_URL,
        headers={"User-Agent": "cardmaniac-monitor/1.1"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)

    products = []
    for p in data.get("products", []):
        handle = p.get("handle", "")
        products.append(
            {
                "id": str(p["id"]),
                "title": p.get("title", "(ohne Titel)"),
                "url": (
                    f"https://cardmaniac.ch/products/{handle}"
                    if handle
                    else CARDMANIAC_PAGE
                ),
                "shop": "Cardmaniac",
            }
        )
    return products


def check_cardmaniac() -> None:
    products = fetch_cardmaniac()
    print(f"[Cardmaniac] Gefunden: {len(products)} Produkte")

    seen = load_seen(CARDMANIAC_SEEN)
    current_ids = {p["id"] for p in products}

    if not seen:
        save_seen(CARDMANIAC_SEEN, current_ids)
        print("[Cardmaniac] Erster Lauf: seen.json initialisiert, keine Mail.")
        return

    new_products = [p for p in products if p["id"] not in seen]
    if new_products:
        print("[Cardmaniac] Neu:")
        for p in new_products:
            print(f"  - {p['title']}")

        priority = [
            p
            for p in new_products
            if matches_keywords(p["title"], CARDMANIAC_PRIORITY_KEYWORDS)
        ]
        if priority:
            subject = f"🎯 Cardmaniac PRIORITÄT: {priority[0]['title']}"
            if len(new_products) > 1:
                subject += f" (+{len(new_products) - 1} weitere)"
        elif len(new_products) == 1:
            subject = f"🆕 Cardmaniac: {new_products[0]['title']}"
        else:
            subject = f"🆕 Cardmaniac: {len(new_products)} neue Pre-Order Produkte"

        lines = [
            "Neue Produkte bei Cardmaniac Pre-Order:",
            CARDMANIAC_PAGE,
            "",
        ]
        for p in new_products:
            mark = (
                " [PRIORITÄT]"
                if matches_keywords(p["title"], CARDMANIAC_PRIORITY_KEYWORDS)
                else ""
            )
            lines.append(f"- {p['title']}{mark}")
            lines.append(f"  {p['url']}")
            lines.append("")
        send_email(subject, "\n".join(lines))
    else:
        print("[Cardmaniac] Keine neuen Produkte.")

    save_seen(CARDMANIAC_SEEN, current_ids)


# ----- CardCollectors (stock watch) -----


def _slug_from_url(url: str) -> str:
    return urllib.parse.urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]


def fetch_cardcollectors_product(slug: str) -> dict | None:
    api = f"{CARDCOLLECTORS_API}?slug={urllib.parse.quote(slug)}"
    req = urllib.request.Request(api, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    if not data:
        return None
    p = data[0]
    return {
        "id": str(p["id"]),
        "slug": slug,
        "title": html_lib.unescape(p.get("name") or slug),
        "url": p.get("permalink") or f"https://cardcollectors.ch/produkt/{slug}/",
        "in_stock": bool(p.get("is_in_stock")),
    }


def check_cardcollectors() -> None:
    if not CARDCOLLECTORS_WATCHLIST.exists():
        print("[CardCollectors] Keine watchlist_cardcollectors.json — übersprungen.")
        return

    urls = json.loads(CARDCOLLECTORS_WATCHLIST.read_text(encoding="utf-8"))
    prev = {}
    if CARDCOLLECTORS_STOCK.exists():
        prev = json.loads(CARDCOLLECTORS_STOCK.read_text(encoding="utf-8")).get(
            "stock", {}
        )

    print(f"[CardCollectors] Prüfe {len(urls)} Produkte…")
    now: dict[str, bool] = {}
    became_available: list[dict] = []

    for url in urls:
        slug = _slug_from_url(url)
        try:
            product = fetch_cardcollectors_product(slug)
        except Exception as exc:  # noqa: BLE001
            print(f"[CardCollectors] Fehler bei {slug}: {exc}")
            if slug in prev:
                now[slug] = bool(prev[slug])
            continue

        if not product:
            print(f"[CardCollectors] Nicht gefunden: {slug}")
            continue

        in_stock = product["in_stock"]
        now[slug] = in_stock
        status = "In den Warenkorb" if in_stock else "Nicht vorrätig"
        print(f"  · {status}: {product['title']}")

        was = prev.get(slug)
        # First time we see this slug: seed only, no mail
        if was is None:
            continue
        if in_stock and not was:
            became_available.append(product)

    if became_available:
        if len(became_available) == 1:
            subject = f"🛒 CardCollectors VERFÜGBAR: {became_available[0]['title']}"
        else:
            subject = (
                f"🛒 CardCollectors: {len(became_available)} Produkte jetzt verfügbar"
            )
        lines = [
            "Diese Produkte sind jetzt verfügbar (In den Warenkorb):",
            "",
        ]
        for p in became_available:
            lines.append(f"- {p['title']}")
            lines.append(f"  {p['url']}")
            lines.append("")
        send_email(subject, "\n".join(lines))
    else:
        print("[CardCollectors] Keine neuen Verfügbarkeiten.")

    CARDCOLLECTORS_STOCK.write_text(
        json.dumps({"stock": now}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


# ----- Manor -----


def _manor_fetch_page(page: int) -> tuple[int, list[dict]]:
    params = {"query": "Pokemon", "brand": "pokemon", "page": str(page)}
    url = MANOR_SEARCH + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept-Language": "de-CH,de;q=0.9",
            "Accept": "text/html",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode("utf-8", errors="ignore")

    m = re.search(
        r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, flags=re.S
    )
    if not m:
        raise RuntimeError(f"Manor __NEXT_DATA__ fehlt (page={page})")

    data = json.loads(m.group(1))
    page_props = data["props"]["pageProps"]
    total = int(page_props.get("plpProductNumber") or 0)
    state = page_props["initialApolloState"]

    items: list[dict] = []
    for key, val in state.items():
        if not str(key).startswith("IndexedProduct:") or not isinstance(val, dict):
            continue
        title = val.get("name") or ""
        items.append(
            {
                "id": str(val.get("code") or str(key).split("/")[-1]),
                "title": title,
                "url": val.get("link")
                or f"https://www.manor.ch/p/{str(key).split('/')[-1]}",
                "brand": val.get("brandName") or val.get("brandId") or "",
                "stock": (val.get("stock") or {}).get("status"),
            }
        )
    return total, items


def fetch_manor_keyword_products() -> list[dict]:
    total, first = _manor_fetch_page(0)
    page_size = max(len(first), 1)
    pages = max(1, (total + page_size - 1) // page_size)
    print(f"[Manor] Pokémon-Suche: {total} Produkte, {pages} Seiten")

    by_id: dict[str, dict] = {p["id"]: p for p in first}

    def load(page: int) -> list[dict]:
        _, items = _manor_fetch_page(page)
        return items

    if pages > 1:
        with ThreadPoolExecutor(max_workers=6) as pool:
            futs = {pool.submit(load, p): p for p in range(1, pages)}
            for fut in as_completed(futs):
                page = futs[fut]
                try:
                    for item in fut.result():
                        by_id[item["id"]] = item
                except Exception as exc:  # noqa: BLE001
                    print(f"[Manor] Seite {page} fehlgeschlagen: {exc}")

    matching = [
        p
        for p in by_id.values()
        if matches_keywords(p["title"], MANOR_KEYWORDS)
    ]
    return matching


def check_manor() -> None:
    matching = fetch_manor_keyword_products()
    print(f"[Manor] Keyword-Treffer (30th / 30 Jahre): {len(matching)}")
    for p in matching:
        print(f"  · {p['title']} [{p.get('stock')}]")

    raw: dict = {"product_ids": [], "initialized": False}
    if MANOR_SEEN.exists():
        raw = json.loads(MANOR_SEEN.read_text(encoding="utf-8"))

    seen = {str(x) for x in raw.get("product_ids", [])}
    initialized = bool(raw.get("initialized"))
    match_ids = {p["id"] for p in matching}

    if not initialized:
        MANOR_SEEN.write_text(
            json.dumps(
                {"product_ids": sorted(match_ids), "initialized": True},
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        print("[Manor] Erster Lauf: State gespeichert, keine Mail.")
        return

    new_matches = [p for p in matching if p["id"] not in seen]
    if new_matches:
        print("[Manor] NEUE Treffer:")
        for p in new_matches:
            print(f"  - {p['title']}")

        if len(new_matches) == 1:
            subject = f"🏬 Manor: {new_matches[0]['title']}"
        else:
            subject = f"🏬 Manor: {len(new_matches)} neue 30th/30-Jahre Treffer"

        lines = [
            "Neue Pokémon-Treffer bei Manor (Suche: Pokemon, Filter: 30th / 30 Jahre):",
            "https://www.manor.ch/de/search?query=Pokemon",
            "",
        ]
        for p in new_matches:
            lines.append(f"- {p['title']}")
            lines.append(f"  {p['url']}")
            if p.get("stock"):
                lines.append(f"  Status: {p['stock']}")
            lines.append("")
        send_email(subject, "\n".join(lines))
    else:
        print("[Manor] Keine neuen Keyword-Treffer.")

    MANOR_SEEN.write_text(
        json.dumps(
            {
                "product_ids": sorted(seen | match_ids),
                "initialized": True,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


# ----- Ryu.land -----


def _ryu_get_json(url: str) -> dict | list:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def _ryu_fetch_all_collections() -> list[dict]:
    cols: list[dict] = []
    page = 1
    while page <= 20:
        data = _ryu_get_json(
            f"{RYU_COLLECTIONS_JSON}?limit=250&page={page}"
        )
        chunk = data.get("collections", []) if isinstance(data, dict) else []
        if not chunk:
            break
        cols.extend(chunk)
        if len(chunk) < 250:
            break
        page += 1
    return cols


def _ryu_is_interesting_collection(handle: str, title: str) -> bool:
    blob = f"{handle} {title}".casefold()
    if "30th" in blob and ("celebrat" in blob or "annivers" in blob):
        return True
    if "pokemon" in blob and ("pre-order" in blob or "preorder" in blob):
        return True
    if "pkm" in blob and ("pre-order" in blob or "preorder" in blob):
        return True
    return False


def _ryu_collection_products(handle: str) -> list[dict]:
    data = _ryu_get_json(
        f"https://ryu.land/collections/{handle}/products.json?limit=250"
    )
    products = []
    for p in data.get("products", []):
        variants = []
        for v in p.get("variants", []):
            variants.append(
                {
                    "id": str(v.get("id")),
                    "title": v.get("title") or "",
                    "available": bool(v.get("available")),
                    "price": v.get("price"),
                }
            )
        products.append(
            {
                "id": str(p.get("id")),
                "title": p.get("title") or "",
                "handle": p.get("handle") or "",
                "url": f"https://ryu.land/products/{p.get('handle')}",
                "tags": p.get("tags") or [],
                "variants": variants,
            }
        )
    return products


def _ryu_search_30th_products() -> list[dict]:
    """Catch 30th products even if not yet filed under the main collection."""
    q = urllib.parse.urlencode(
        {
            "q": "30th",
            "resources[type]": "product",
            "resources[limit]": "10",
            "resources[options][unavailable_products]": "last",
        }
    )
    data = _ryu_get_json(f"https://ryu.land/search/suggest.json?{q}")
    results = (
        ((data.get("resources") or {}).get("results") or {}).get("products") or []
    )
    out = []
    for p in results:
        title = p.get("title") or ""
        tags = [str(t).casefold() for t in (p.get("tags") or [])]
        blob = f"{title} {' '.join(tags)}".casefold()
        if "30th" not in blob:
            continue
        if not any(k in blob for k in ("pokemon", "pokémon", "pkm")):
            continue
        handle = p.get("handle") or ""
        out.append(
            {
                "id": str(p.get("id")),
                "title": title,
                "handle": handle,
                "url": f"https://ryu.land/products/{handle}",
                "tags": p.get("tags") or [],
                "available": bool(p.get("available")),
            }
        )
    return out


def check_ryu() -> None:
    raw: dict = {
        "product_ids": [],
        "collection_handles": [],
        "variant_availability": {},
        "initialized": False,
    }
    if RYU_SEEN.exists():
        raw = json.loads(RYU_SEEN.read_text(encoding="utf-8"))

    seen_products = {str(x) for x in raw.get("product_ids", [])}
    seen_collections = {str(x) for x in raw.get("collection_handles", [])}
    prev_variants: dict = raw.get("variant_availability") or {}
    initialized = bool(raw.get("initialized"))

    # 1) Known 30th collection products
    collection_products = _ryu_collection_products(RYU_COLLECTION)
    print(
        f"[Ryu] Collection {RYU_COLLECTION}: {len(collection_products)} Produkte"
    )

    # 2) Search fallback for other 30th Pokémon products
    search_products = _ryu_search_30th_products()
    print(f"[Ryu] Search 30th Pokémon: {len(search_products)} Treffer")

    by_id: dict[str, dict] = {}
    for p in collection_products + search_products:
        by_id[p["id"]] = p

    # 3) Watch for new related collections (pokemon pre-order / 30th)
    all_cols = _ryu_fetch_all_collections()
    interesting_cols = [
        c
        for c in all_cols
        if _ryu_is_interesting_collection(c.get("handle", ""), c.get("title", ""))
    ]
    print(f"[Ryu] Interessante Collections: {len(interesting_cols)}")
    for c in interesting_cols:
        print(f"  · {c.get('handle')} ({c.get('products_count')})")

    current_col_handles = {c.get("handle") for c in interesting_cols if c.get("handle")}
    current_product_ids = set(by_id)
    current_variants: dict[str, bool] = {}
    for p in collection_products:
        for v in p.get("variants", []):
            current_variants[v["id"]] = bool(v["available"])

    if not initialized:
        RYU_SEEN.write_text(
            json.dumps(
                {
                    "product_ids": sorted(current_product_ids),
                    "collection_handles": sorted(current_col_handles),
                    "variant_availability": current_variants,
                    "initialized": True,
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        print("[Ryu] Erster Lauf: State gespeichert, keine Mail.")
        return

    new_products = [by_id[i] for i in current_product_ids if i not in seen_products]
    new_collections = [
        c
        for c in interesting_cols
        if c.get("handle") and c.get("handle") not in seen_collections
    ]
    newly_available_variants: list[tuple[dict, dict]] = []
    for p in collection_products:
        for v in p.get("variants", []):
            vid = v["id"]
            was = prev_variants.get(vid)
            if was is False and v["available"] is True:
                newly_available_variants.append((p, v))

    alerts: list[str] = []
    if new_collections:
        alerts.append("Neue Collection(s):")
        for c in new_collections:
            handle = c.get("handle")
            alerts.append(f"- {c.get('title')} ({c.get('products_count')} Produkte)")
            alerts.append(f"  https://ryu.land/collections/{handle}")
            alerts.append("")

    if new_products:
        alerts.append("Neue 30th-Produkte:")
        for p in new_products:
            alerts.append(f"- {p['title']}")
            alerts.append(f"  {p['url']}")
            alerts.append("")

    if newly_available_variants:
        alerts.append("Variante jetzt vorbestellbar/verfügbar:")
        for p, v in newly_available_variants:
            alerts.append(f"- {p['title']} — {v['title']}")
            alerts.append(f"  {p['url']}")
            alerts.append("")

    if alerts:
        subject_bits = []
        if new_collections:
            subject_bits.append(f"{len(new_collections)} Collection")
        if new_products:
            subject_bits.append(f"{len(new_products)} Produkt")
        if newly_available_variants:
            subject_bits.append(f"{len(newly_available_variants)} Variante")
        subject = "🐉 Ryu.land: " + ", ".join(subject_bits) + " neu"
        if new_products:
            subject = f"🐉 Ryu.land: {new_products[0]['title']}"
            if len(new_products) + len(new_collections) + len(
                newly_available_variants
            ) > 1:
                subject += " (+weitere)"
        elif newly_available_variants:
            p, v = newly_available_variants[0]
            subject = f"🐉 Ryu.land verfügbar: {p['title']} ({v['title']})"

        body = "\n".join(
            [
                "Update bei ryu.land (30th / Pre-Order Monitoring):",
                f"https://ryu.land/collections/{RYU_COLLECTION}",
                "",
                *alerts,
            ]
        )
        send_email(subject, body)
        print("[Ryu] Mail gesendet.")
    else:
        print("[Ryu] Keine neuen Pre-Order/30th-Änderungen.")

    RYU_SEEN.write_text(
        json.dumps(
            {
                "product_ids": sorted(seen_products | current_product_ids),
                "collection_handles": sorted(seen_collections | current_col_handles),
                "variant_availability": {
                    **prev_variants,
                    **current_variants,
                },
                "initialized": True,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


# ----- Brack -----


def _curl_get(url: str, timeout: int = 45) -> bytes:
    cmd = [
        "curl",
        "-sL",
        "--fail",
        "--http1.1",
        "-4",
        "--retry",
        "2",
        "--retry-delay",
        "1",
        "--max-time",
        str(timeout),
        "-A",
        UA,
        "-H",
        "Accept: application/xml,text/xml,*/*",
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, check=False)
    if result.returncode != 0 or not result.stdout:
        raise RuntimeError(f"curl {result.returncode} for {url}")
    return result.stdout


def _slug_title(url: str) -> str:
    path = urllib.parse.urlparse(url).path.strip("/")
    parts = path.split("-")
    if parts and parts[-1].isdigit():
        parts = parts[:-1]
    if parts[:3] == ["the", "pokemon", "company"]:
        parts = parts[3:]
    title = " ".join(parts).strip()
    return title[:1].upper() + title[1:] if title else path


def _index_fingerprint(index_xml: str) -> str:
    """Hash of product-sitemap loc+lastmod pairs — changes when catalog export updates."""
    blocks = re.findall(
        r"<sitemap>\s*<loc>([^<]*google-product-sitemap-[^<]*)</loc>\s*"
        r"(?:<lastmod>([^<]*)</lastmod>)?",
        index_xml,
        flags=re.I | re.S,
    )
    if not blocks:
        # Fallback: hash whole index
        return hashlib.sha256(index_xml.encode("utf-8")).hexdigest()
    material = "\n".join(f"{loc}|{lastmod}" for loc, lastmod in sorted(blocks))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _load_brack_state() -> dict:
    if not BRACK_STATE.exists():
        return {}
    return json.loads(BRACK_STATE.read_text(encoding="utf-8"))


def _save_brack_state(state: dict) -> None:
    BRACK_STATE.write_text(
        json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def scan_brack_sitemaps(sitemap_urls: list[str]) -> list[dict]:
    pattern = re.compile(
        r"https://www\.brack\.ch/[^<\s\"]*(?:the-pokemon-company|pokemon)[^<\s\"]*",
        re.I,
    )
    kw_re = re.compile("|".join(re.escape(k) for k in BRACK_URL_KEYWORDS), re.I)

    products: dict[str, dict] = {}
    ok = 0
    for sm_url in sitemap_urls:
        try:
            raw = _curl_get(sm_url, timeout=45)
        except Exception as exc:  # noqa: BLE001
            print(f"[Brack] Skip {sm_url.split('/')[-1]}: {exc}")
            continue
        ok += 1
        text = raw.decode("utf-8", errors="ignore")
        for url in pattern.findall(text):
            if not kw_re.search(url):
                continue
            sku = url.rstrip("/").rsplit("-", 1)[-1]
            pid = sku if sku.isdigit() else url
            products[pid] = {
                "id": pid,
                "title": _slug_title(url),
                "url": url,
                "shop": "Brack",
            }

    if ok == 0:
        raise RuntimeError("Keine Product-Sitemap konnte geladen werden")
    print(f"[Brack] {ok}/{len(sitemap_urls)} Sitemaps gescannt, Treffer: {len(products)}")
    return list(products.values())


def check_brack() -> None:
    # 1) Tiny index fetch — decide whether a full scan is needed
    index_xml = _curl_get(BRACK_SITEMAP_INDEX, timeout=30).decode("utf-8", errors="ignore")
    fingerprint = _index_fingerprint(index_xml)
    sitemap_urls = [
        u
        for u in re.findall(r"<loc>([^<]+)</loc>", index_xml)
        if "google-product-sitemap-" in u
    ]
    if not sitemap_urls:
        sitemap_urls = [
            f"https://www.brack.ch/exports/google/brack.ch/de/google-product-sitemap-{i}.xml"
            for i in range(1, 32)
        ]

    state = _load_brack_state()
    prev = state.get("fingerprint")
    if prev == fingerprint and not FORCE_BRACK_SCAN:
        print("[Brack] Sitemap unverändert — kein Full-Scan nötig.")
        return

    reason = "erzwungen" if FORCE_BRACK_SCAN else "Sitemap-Index geändert"
    print(f"[Brack] Full-Scan ({reason})…")
    matching = scan_brack_sitemaps(sitemap_urls)
    print(f"[Brack] Keyword-Treffer: {len(matching)}")
    for p in matching:
        print(f"  · {p['title']}")

    seen = load_seen(BRACK_SEEN)
    match_ids = {p["id"] for p in matching}
    new_matches = [p for p in matching if p["id"] not in seen]

    if new_matches:
        print("[Brack] NEUE Keyword-Treffer:")
        for p in new_matches:
            print(f"  - {p['title']}")

        if len(new_matches) == 1:
            subject = f"🛒 Brack: {new_matches[0]['title']}"
        else:
            subject = f"🛒 Brack: {len(new_matches)} neue 30th/Celebration-Treffer"

        lines = [
            "Neue Treffer bei Brack (30th / 30 Jahre):",
            "https://www.brack.ch/",
            "",
        ]
        for p in new_matches:
            lines.append(f"- {p['title']}")
            lines.append(f"  {p['url']}")
            lines.append("")
        send_email(subject, "\n".join(lines))
    else:
        print("[Brack] Keine neuen Keyword-Treffer.")

    save_seen(BRACK_SEEN, seen | match_ids)
    _save_brack_state({"fingerprint": fingerprint})


def main() -> None:
    check_cardmaniac()

    try:
        check_cardcollectors()
    except Exception as exc:  # noqa: BLE001
        print(f"[CardCollectors] FEHLER: {exc}")

    try:
        check_manor()
    except Exception as exc:  # noqa: BLE001
        print(f"[Manor] FEHLER: {exc}")

    try:
        check_ryu()
    except Exception as exc:  # noqa: BLE001
        print(f"[Ryu] FEHLER: {exc}")

    # Brack is often blocked from GitHub cloud — only run when forced.
    if FORCE_BRACK_SCAN:
        try:
            check_brack()
        except Exception as exc:  # noqa: BLE001
            print(f"[Brack] FEHLER: {exc}")
    else:
        print("[Brack] Übersprungen (nur bei FORCE_BRACK_SCAN=1).")


if __name__ == "__main__":
    main()
