# Cardmaniac + Brack Monitor

Läuft alle **~10 Minuten** auf **GitHub Actions** (Cloud) und mailt an **mab151204@gmail.com**.

## Was wird überwacht?

| Shop | Quelle | Wann Mail? |
|------|--------|------------|
| **Cardmaniac** | Pre-Order Collection | **Jedes** neue Produkt (+ Priorität im Betreff bei Tech-Sticker/30th) |
| **Brack** | Pokémon-Sammelkarten (Hersteller „The Pokémon Company“) | Nur wenn Titel **30th / Celebration / 30 Jahre / Tech-Sticker** enthält |

## Wie funktioniert Brack?

Brack blockiert die normale Suche für Bots. Deshalb lädt der Monitor die Kategorie-Seite mit Pokémon-Filter, liest die Produktliste aus dem HTML und prüft die Titel auf deine Suchbegriffe. Bei einem neuen Treffer kommt eine Mail **mit Direktlink**.

## Secrets (bereits gesetzt)

- `SMTP_USER` = `mab151204@gmail.com`
- `SMTP_PASS` = Gmail App-Passwort

## Manuell testen

Im Repo: **Actions → Cardmaniac + Brack Monitor → Run workflow**
