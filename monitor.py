#!/usr/bin/env python3
"""Monitor Cardmaniac + Brack and email on matching new products."""

from __future__ import annotations

import json
import os
import re
import smtplib
import ssl
import urllib.parse
import urllib.request
from email.message import EmailMessage
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# --- Cardmaniac (notify on ANY new pre-order product) ---
CARDMANIAC_URL = "https://cardmaniac.ch/collections/pre-order/products.json"
CARDMANIAC_PAGE = "https://cardmaniac.ch/collections/pre-order"
CARDMANIAC_SEEN = ROOT / "seen.json"

# --- Brack (notify only on keyword matches via public sitemaps) ---
BRACK_SEEN = ROOT / "seen_brack.json"

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


# ----- Brack (via public Google product sitemaps — works on GitHub Actions) -----

BRACK_SITEMAP_INDEX = (
    "https://www.brack.ch/exports/google/brack.ch/de/sitemap-index.xml"
)

# Match against URL slug (lowercase). Keep specific to avoid false positives.
BRACK_URL_KEYWORDS = [
    "30th",
    "30-jahre",
    "30jahre",
    "30-jaehrige",
    "tech-sticker",
    "techsticker",
    "sticker-kollektion",
    "stickerkollektion",
]


def _http_get(url: str, headers: dict[str, str], timeout: int = 45) -> str:
    """Fetch URL; prefer curl (more reliable from GitHub Actions vs some CDNs)."""
    import subprocess

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
        headers.get("User-Agent", UA),
    ]
    for key, value in headers.items():
        if key.lower() == "user-agent":
            continue
        cmd.extend(["-H", f"{key}: {value}"])
    cmd.append(url)
    result = subprocess.run(cmd, capture_output=True, check=False)
    if result.returncode == 0 and result.stdout:
        return result.stdout.decode("utf-8", errors="ignore")

    err = result.stderr.decode("utf-8", errors="ignore")[:160]
    raise RuntimeError(
        f"curl failed code={result.returncode} bytes={len(result.stdout)} err={err!r} url={url}"
    )


def _slug_title(url: str) -> str:
    path = urllib.parse.urlparse(url).path.strip("/")
    # e.g. the-pokemon-company-pokemon-lumiose-city-mini-tin-en-2111867
    parts = path.split("-")
    if parts and parts[-1].isdigit():
        parts = parts[:-1]
    if parts[:3] == ["the", "pokemon", "company"]:
        parts = parts[3:]
    title = " ".join(parts).strip()
    return title[:1].upper() + title[1:] if title else path


def fetch_brack_keyword_products() -> list[dict]:
    """Scan Brack product sitemaps for Pokémon URLs matching keywords."""
    import subprocess

    headers_accept = "application/xml,text/xml,*/*"
    sitemap_urls = [
        f"https://www.brack.ch/exports/google/brack.ch/de/google-product-sitemap-{i}.xml"
        for i in range(1, 32)
    ]

    # Try to refine list from index (optional).
    try:
        idx = _http_get(
            BRACK_SITEMAP_INDEX,
            headers={"User-Agent": UA, "Accept": headers_accept},
            timeout=30,
        )
        found = [
            u
            for u in re.findall(r"<loc>([^<]+)</loc>", idx)
            if "google-product-sitemap-" in u
        ]
        if found:
            sitemap_urls = found
    except Exception as exc:  # noqa: BLE001
        print(f"[Brack] Index optional fehlgeschlagen ({exc}), nutze 1–31")

    print(f"[Brack] Scanne {len(sitemap_urls)} Product-Sitemaps…")
    pattern = re.compile(
        r"https://www\.brack\.ch/[^<\s\"]*(?:the-pokemon-company|pokemon)[^<\s\"]*",
        re.I,
    )
    kw_re = re.compile("|".join(re.escape(k) for k in BRACK_URL_KEYWORDS), re.I)

    products: dict[str, dict] = {}
    ok = 0
    for sm_url in sitemap_urls:
        cmd = [
            "curl",
            "-sL",
            "--fail",
            "--http1.1",
            "-4",
            "--max-time",
            "60",
            "-A",
            UA,
            "-H",
            f"Accept: {headers_accept}",
            sm_url,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, check=False)
            if result.returncode != 0 or not result.stdout:
                print(f"[Brack] Skip {sm_url.split('/')[-1]} (curl {result.returncode})")
                continue
            text = result.stdout.decode("utf-8", errors="ignore")
            ok += 1
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
        except Exception as exc:  # noqa: BLE001
            print(f"[Brack] Skip {sm_url}: {exc}")

    if ok == 0:
        raise RuntimeError("Keine Product-Sitemap konnte geladen werden")
    print(f"[Brack] {ok}/{len(sitemap_urls)} Sitemaps OK, Treffer: {len(products)}")
    return list(products.values())


def check_brack() -> None:
    matching = fetch_brack_keyword_products()
    print(f"[Brack] Keyword-Treffer in Sitemap: {len(matching)}")
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
            "Neue Treffer bei Brack (30th / 30 Jahre / Tech-Sticker):",
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


def main() -> None:
    # Cardmaniac is critical; Brack may flake due to bot protection.
    check_cardmaniac()

    try:
        check_brack()
    except Exception as exc:  # noqa: BLE001
        print(f"[Brack] FEHLER (Cardmaniac läuft trotzdem weiter): {exc}")


if __name__ == "__main__":
    main()
