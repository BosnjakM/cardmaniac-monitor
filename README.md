# Cardmaniac + Brack Monitor

Läuft auf **GitHub Actions**, Mail an **mab151204@gmail.com**.

## Status

| Shop | Status | Wann Mail? |
|------|--------|------------|
| **Cardmaniac** | aktiv (alle ~10 Min) | jedes neue Pre-Order-Produkt |
| **Brack** | Code ist da, aber GitHub-Server werden von Brack oft blockiert | nur **30th / 30 Jahre** |

## Brack – so würde es funktionieren

1. Produktlinks prüfen  
2. Filter: Pokémon + `30th` / `30 Jahre`  
3. Bei Neuem → Mail mit Direktlink  

Lokal auf deinem Mac funktioniert der Brack-Scan. Von der GitHub-Cloud aus antwortet Brack oft nicht (Bot-Schutz).

### Empfohlen für Brack: Google Alert (zuverlässig, ohne 24/7-PC)

1. Öffne: https://www.google.com/alerts  
2. Suchbegriff:  
   `site:brack.ch Pokémon (30th OR "30 Jahre")`  
3. „Wie oft“ → **Sofort**  
4. Quelle → **Automatisch**, an `mab151204@gmail.com`

Dann mailt Google, sobald neue Brack-Seiten indexiert werden.

### Alternative

Self-hosted GitHub Runner auf deinem Mac (nur wenn der Mac online ist) — dann greift unser Brack-Scan direkt.

## Secrets

`SMTP_USER` / `SMTP_PASS` sind gesetzt (Cardmaniac-Mails).
