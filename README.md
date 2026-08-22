# Stock & Pre-Order Monitor

Alerts gehen an die Adresse in GitHub Secret `MAIL_TO` (nicht öffentlich).

| Shop | Was | Status |
|------|-----|--------|
| **Cardmaniac** | jedes neue Pre-Order-Produkt (Delta = Priorität) | aktiv |
| **CardCollectors** | Watchlist → „In den Warenkorb“ + Suche Delta Reign/Herrschaft | aktiv |
| **Manor** | Suche Pokemon → 30th / 30 Jahre / Delta Reign / Delta Herrschaft | aktiv |
| **Ryu.land** | 30th Celebration + Delta Reign/Herrschaft / Pre-Orders | aktiv |
| **Pokecard** | [Vorbestellungen](https://pokecard.store/collections/vorbestellung) neu + Restock (Delta = Priorität) | aktiv |
| **ManaShop** | [Vorverkauf](https://themanashop.ch/de/237-vorverkauf) neu + Restock (Delta = Priorität) | aktiv |
| **SparkLeaf** | Pre-Order/Deals: **30th + Delta Reign/Herrschaft** neu + Restock | aktiv |
| **Brack** | oft blockiert → Google Alert (30th + Delta) | teils |

## Wichtig: zuverlässiger Timer

GitHub-Cron allein verzögert oft stark (bis 1h+).  
Für echte ~5-Minuten-Checks folge **`CRON_SETUP.md`** (cron-job.org).
