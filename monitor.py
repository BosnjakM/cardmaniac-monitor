#!/usr/bin/env python3
"""Monitor Cardmaniac Pre-Order collection and email on new products."""

from __future__ import annotations

import json
import os
import smtplib
import ssl
import urllib.request
from email.message import EmailMessage
from pathlib import Path

COLLECTION_URL = "https://cardmaniac.ch/collections/pre-order/products.json"
COLLECTION_PAGE = "https://cardmaniac.ch/collections/pre-order"
SEEN_PATH = Path(__file__).with_name("seen.json")

# Highlight these matches in the email subject (still notifies on ALL new products)
PRIORITY_KEYWORDS = [
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


def fetch_products() -> list[dict]:
    req = urllib.request.Request(
        COLLECTION_URL,
        headers={"User-Agent": "cardmaniac-monitor/1.0"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)

    products = []
    for p in data.get("products", []):
        handle = p.get("handle", "")
        products.append(
            {
                "id": p["id"],
                "title": p.get("title", "(ohne Titel)"),
                "handle": handle,
                "url": f"https://cardmaniac.ch/products/{handle}" if handle else COLLECTION_PAGE,
                "vendor": p.get("vendor", ""),
                "product_type": p.get("product_type", ""),
            }
        )
    return products


def load_seen() -> dict:
    if not SEEN_PATH.exists():
        return {"product_ids": []}
    return json.loads(SEEN_PATH.read_text(encoding="utf-8"))


def save_seen(product_ids: list[int]) -> None:
    payload = {"product_ids": sorted(product_ids)}
    SEEN_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def is_priority(title: str) -> bool:
    lower = title.casefold()
    return any(k in lower for k in PRIORITY_KEYWORDS)


def send_email(new_products: list[dict]) -> None:
    if not SMTP_USER or not SMTP_PASS:
        raise SystemExit(
            "SMTP_USER / SMTP_PASS fehlen. Bitte GitHub Secrets setzen (siehe README)."
        )

    priority = [p for p in new_products if is_priority(p["title"])]
    if priority:
        subject = f"🎯 PRIORITÄT: {priority[0]['title']}"
        if len(new_products) > 1:
            subject += f" (+{len(new_products) - 1} weitere)"
    elif len(new_products) == 1:
        subject = f"🆕 Neues Pre-Order: {new_products[0]['title']}"
    else:
        subject = f"🆕 {len(new_products)} neue Pre-Order Produkte bei Cardmaniac"

    lines = [
        "Neue Produkte in der Pre-Order Collection:",
        COLLECTION_PAGE,
        "",
    ]
    for p in new_products:
        mark = " [PRIORITÄT / Suchtreffer]" if is_priority(p["title"]) else ""
        lines.append(f"- {p['title']}{mark}")
        lines.append(f"  {p['url']}")
        if p.get("vendor") or p.get("product_type"):
            lines.append(f"  {p.get('vendor', '')} · {p.get('product_type', '')}".strip(" ·"))
        lines.append("")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = MAIL_TO
    msg.set_content("\n".join(lines))

    context = ssl.create_default_context()
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
        server.starttls(context=context)
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)

    print(f"Email gesendet an {MAIL_TO}: {subject}")


def main() -> None:
    products = fetch_products()
    print(f"Gefunden: {len(products)} Produkte")

    seen = load_seen()
    seen_ids = set(seen.get("product_ids", []))
    current_ids = {p["id"] for p in products}

    # First run / empty state: seed without notifying
    if not seen_ids:
        save_seen(list(current_ids))
        print("Erster Lauf: seen.json initialisiert, keine Mail.")
        return

    new_products = [p for p in products if p["id"] not in seen_ids]
    if new_products:
        print("Neu:")
        for p in new_products:
            print(f"  - {p['title']}")
        send_email(new_products)
    else:
        print("Keine neuen Produkte.")

    # Keep only currently listed IDs so removals don't bloat forever;
    # re-added products will notify again (desired for pre-orders).
    save_seen(list(current_ids))


if __name__ == "__main__":
    main()
