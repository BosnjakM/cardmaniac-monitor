# Cardmaniac + Brack Monitor

Läuft alle **~10 Minuten** auf **GitHub Actions** und mailt an **mab151204@gmail.com**.

## Was wird überwacht?

| Shop | Quelle | Wann Mail? |
|------|--------|------------|
| **Cardmaniac** | Pre-Order API | **Jedes** neue Produkt |
| **Brack** | Öffentliche Produkt-Sitemaps | Pokémon-URL enthält **30th / 30-jahre / Tech-Sticker** |

## Wie funktioniert Brack?

Die normale Brack-Website blockiert Cloud-Server (Bot-Schutz). Deshalb nutzt der Monitor die **öffentlichen Google-Sitemaps** von Brack, sucht Pokémon-Produkt-Links mit deinen Keywords und schickt bei Neuem eine Mail **mit Direktlink**.

Hinweis: Die Sitemap kann gegenüber dem Shop etwas verzögert sein (oft Stunden, selten länger).

## Secrets

- `SMTP_USER` / `SMTP_PASS` (Gmail App-Passwort) — bereits gesetzt
