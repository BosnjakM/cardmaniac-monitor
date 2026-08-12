#!/usr/bin/env python3
"""Monitor Cardmaniac + Brack and email on matching new products."""

from __future__ import annotations

import http.cookiejar
import json
import os
import re
import smtplib
import ssl
import time
import urllib.parse
import urllib.request
from email.message import EmailMessage
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# --- Cardmaniac (notify on ANY new pre-order product) ---
CARDMANIAC_URL = "https://cardmaniac.ch/collections/pre-order/products.json"
CARDMANIAC_PAGE = "https://cardmaniac.ch/collections/pre-order"
CARDMANIAC_SEEN = ROOT / "seen.json"

# --- Brack (notify only on keyword matches) ---
BRACK_PAGE = (
    "https://www.brack.ch/sport-freizeit/spielwaren/puzzles-spiele/spiele/sammelkarten"
    "?filter%5BfacetManufacturerName%5D="
    + urllib.parse.quote("The Pokémon Company")
)
BRACK_SEEN = ROOT / "seen_brack.json"

BRACK_KEYWORDS = [
    "30th celebration",
    "30th",
    "30 jahre",
    "30-jahre",
    "30jährigen",
    "30-jährigen",
    "tech-sticker",
    "tech sticker",
    "sticker-kollektion",
    "sticker kollektion",
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


# ----- Brack -----


def _brack_opener() -> urllib.request.OpenerDirector:
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def _http_get(url: str, headers: dict[str, str], timeout: int = 45) -> str:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def _brack_get(opener: urllib.request.OpenerDirector, url: str, timeout: int = 45) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "de-CH,de;q=0.9,en;q=0.8",
            "Referer": "https://www.brack.ch/",
        },
    )
    with opener.open(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def fetch_brack_via_jina() -> list[dict]:
    """Fallback: fetch rendered HTML through r.jina.ai (works from cloud IPs)."""
    proxy_url = "https://r.jina.ai/" + BRACK_PAGE
    html = _http_get(
        proxy_url,
        headers={
            "User-Agent": UA,
            "Accept": "text/html",
            "X-Return-Format": "html",
        },
        timeout=90,
    )
    products = parse_brack_products(html)
    if not products:
        raise RuntimeError("Jina-Fallback lieferte keine Produkte")
    return products


def fetch_brack_pokemon(retries: int = 1) -> list[dict]:
    last_err: Exception | None = None

    # 1) Direct fetch (works from home networks; often blocked from cloud)
    for attempt in range(1, retries + 1):
        try:
            opener = _brack_opener()
            _brack_get(opener, "https://www.brack.ch/", timeout=20)
            html = _brack_get(opener, BRACK_PAGE, timeout=25)
            products = parse_brack_products(html)
            if products:
                return products
            raise RuntimeError("Seite geladen, aber keine Produkte gefunden")
        except Exception as exc:  # noqa: BLE001 - network/Akamai flakiness
            last_err = exc
            print(f"[Brack] Direktversuch {attempt}/{retries} fehlgeschlagen: {exc}")

    # 2) Cloud-friendly proxy (needed on GitHub Actions)
    try:
        print("[Brack] Nutze Jina-Proxy-Fallback…")
        return fetch_brack_via_jina()
    except Exception as exc:  # noqa: BLE001
        last_err = exc
        print(f"[Brack] Jina-Fallback fehlgeschlagen: {exc}")

    raise RuntimeError(f"Brack konnte nicht geladen werden: {last_err}")


def parse_brack_products(html: str) -> list[dict]:
    """Parse Pokémon products from Brack category HTML (productDataMap)."""
    items: dict[str, dict] = {}

    # Prefer structured productDataMap JSON blob if present
    m = re.search(r'\{"productDataMap":\{', html)
    if m:
        # Brace-match the outer object starting at m.start()
        start = m.start()
        depth = 0
        end = None
        for i, ch in enumerate(html[start:], start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end:
            try:
                blob = json.loads(html[start:end])
                pdata = blob.get("productDataMap") or {}
                for sku, entry in pdata.items():
                    title = (
                        (entry.get("description") or {}).get("nameWithoutManufacturer")
                        or entry.get("name")
                        or "(ohne Titel)"
                    )
                    path = entry.get("url") or f"/product-{sku}"
                    if not path.startswith("http"):
                        path = "https://www.brack.ch" + path
                    items[str(sku)] = {
                        "id": str(sku),
                        "title": title,
                        "url": path,
                        "shop": "Brack",
                    }
            except json.JSONDecodeError:
                items = {}

    # Fallback: url + nearby nameWithoutManufacturer
    if not items:
        for um in re.finditer(r'"url"\s*:\s*"(/the-pokemon-company-[^"]+)"', html):
            path = um.group(1)
            ahead = html[um.end() : um.end() + 2500]
            nm = re.search(
                r'"nameWithoutManufacturer"\s*:\s*"((?:\\.|[^"\\])*)"', ahead
            )
            if not nm:
                continue
            name = nm.group(1)
            sku = path.rsplit("-", 1)[-1]
            items[sku] = {
                "id": sku,
                "title": name,
                "url": "https://www.brack.ch" + path,
                "shop": "Brack",
            }

    return list(items.values())


def check_brack() -> None:
    products = fetch_brack_pokemon()
    print(f"[Brack] Gefunden: {len(products)} Pokémon-Produkte")

    matching = [p for p in products if matches_keywords(p["title"], BRACK_KEYWORDS)]
    print(f"[Brack] Keyword-Treffer jetzt: {len(matching)}")
    for p in matching:
        print(f"  · {p['title']}")

    seen = load_seen(BRACK_SEEN)
    match_ids = {p["id"] for p in matching}

    if not seen and matching:
        # Seed current matches so we don't spam on first deploy
        save_seen(BRACK_SEEN, match_ids)
        print("[Brack] Erster Lauf: seen_brack.json mit aktuellen Treffern initialisiert.")
        return
    if not seen:
        save_seen(BRACK_SEEN, set())
        print("[Brack] Erster Lauf: keine Keyword-Treffer, seen_brack.json leer initialisiert.")
        return

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
            "Neue Treffer bei Brack (Suchbegriffe: 30th Celebration / 30 Jahre / Tech-Sticker):",
            "https://www.brack.ch/pokemon",
            "",
        ]
        for p in new_matches:
            lines.append(f"- {p['title']}")
            lines.append(f"  {p['url']}")
            lines.append("")
        send_email(subject, "\n".join(lines))
    else:
        print("[Brack] Keine neuen Keyword-Treffer.")

    # Remember all matches we've ever notified about (don't drop old ones,
    # otherwise a temporary catalog glitch would re-notify).
    save_seen(BRACK_SEEN, seen | match_ids)


def main() -> None:
    # Cardmaniac is critical; Brack may flake due to bot protection.
    check_cardmaniac()

    try:
        check_brack()
    except Exception as exc:  # noqa: BLE001
        print(f"[Brack] FEHLER (Cardmaniac läuft trotzdem weiter): {exc}")


if __name__ == "__main__":
    main()
