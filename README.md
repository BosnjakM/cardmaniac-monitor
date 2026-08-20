# Stock & Pre-Order Monitor

Alerts gehen an die Adresse in GitHub Secret `MAIL_TO` (nicht öffentlich).

| Shop | Was | Status |
|------|-----|--------|
| **Cardmaniac** | jedes neue Pre-Order-Produkt | aktiv |
| **CardCollectors** | Watchlist → „In den Warenkorb“ | aktiv |
| **Manor** | Suche Pokemon → 30th / 30 Jahre | aktiv |
| **Ryu.land** | 30th Celebration Collection / Pre-Orders | aktiv |
| **Pokecard** | [Vorbestellungen](https://pokecard.store/collections/vorbestellung) neu + Restock | aktiv |
| **ManaShop** | [Vorverkauf](https://themanashop.ch/de/237-vorverkauf) neu + Restock | aktiv |
| **SparkLeaf** | Pre-Order/Deals, nur **30th** neu + Restock | aktiv |
| **Brack** | oft blockiert → Google Alert | teils |

## Wichtig: zuverlässiger Timer

GitHub-Cron allein verzögert oft stark (bis 1h+).  
Für echte ~5-Minuten-Checks folge **`CRON_SETUP.md`** (cron-job.org).
