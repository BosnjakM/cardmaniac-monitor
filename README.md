# Cardmaniac + Brack Monitor

Läuft auf **GitHub Actions** und mailt an **mab151204@gmail.com**.

## Was wird überwacht?

| Shop | Frequenz | Wann Mail? |
|------|----------|------------|
| **Cardmaniac** | alle ~10 Min | **Jedes** neue Pre-Order-Produkt |
| **Brack** | wenn sich die Produkt-Sitemap ändert (meist ~täglich) + bei manuellem Run | Pokémon-URL enthält **30th / 30-jahre / Tech-Sticker** |

## Wie funktioniert Brack?

Brack blockiert die normale Shop-Seite für Cloud-Server. Deshalb nutzt der Monitor die **öffentlichen Google-Sitemaps**:

1. Kleiner Sitemap-Index wird geprüft  
2. Nur wenn sich der Katalog-Export geändert hat → Full-Scan  
3. Bei neuem Keyword-Treffer → Mail **mit Link**

Manueller Test: **Actions → Run workflow** (erzwingt Brack-Scan).

## Secrets

- `SMTP_USER` / `SMTP_PASS` — bereits gesetzt
