# Stock & Pre-Order Monitor

Alerts gehen an die Adresse in GitHub Secret `MAIL_TO` (nicht öffentlich).

Überall: **neu** + **wieder verfügbar** (soweit die Shop-Daten das hergeben).  
History wird nicht mehr geleert, wenn eine Liste kurz leer ist.

| Shop | Was | Status |
|------|-----|--------|
| **Cardmaniac** | Pre-Order neu + Restock (30th/Delta = Priorität) | aktiv |
| **CardCollectors** | Watchlist Restock + Delta-Suche neu/Restock | aktiv |
| **Manor** | 30th / Delta neu + Restock (`IN_STOCK`) | aktiv |
| **Ryu.land** | 30th / Delta / Pre-Order neu + Varianten-Restock | aktiv |
| **Pokecard** | Vorbestellungen neu + Restock | aktiv |
| **ManaShop** | Vorverkauf neu + Restock | aktiv |
| **SparkLeaf** | Pre-Order/Deals 30th+Delta neu + Restock | aktiv |
| **Brack** | Sitemap 30th/Delta neu + wieder in Sitemap (oft blockiert) | teils |

## Wichtig: zuverlässiger Timer

GitHub-Cron allein verzögert oft stark (bis 1h+).  
Für echte ~5-Minuten-Checks folge **`CRON_SETUP.md`** (cron-job.org).
