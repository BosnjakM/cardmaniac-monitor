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
| **Ricardo** | Pokémon-Auktionen ≤30 Min vor Ende, Deal vs. Schätzwert | aktiv |
| **Brack** | oft blockiert → Google Alert (30th + Delta) | teils |

## Ricardo-Deals

Jede Minute: Pokémon-Auktionen die in **≤30 Minuten** enden. Mail nur wenn Gebot + Versand klar unter dem Live-Marktwert liegt:

- mind. **25 CHF** Differenz **und**
- **2× Marktwert** (100%+) **oder** ≥50 CHF Differenz

**Marktpreis (live, ohne deine API-Keys):** TCGPlayer-Dumps via [tcgcsv.com](https://tcgcsv.com) (wenn Sealed-Market da ist), sonst [PriceCharting](https://www.pricecharting.com) Ungraded, USD→CHF. Deutsche/FR/IT-Lots werden gegen US-EN-Comps abgewertet (Ricardo ist oft DE). `ricardo_market.json` ist nur Fallback.

Cardmarket und CollectHolo gehen ohne Login/API-Token nicht (Cloudflare bzw. 401). Resealed/geöffnet im **Titel** → 55%. Singles (`123/456`) werden ignoriert.

GitHub-Cron allein verzögert oft stark (bis 1h+).  
Für echte ~5-Minuten-Checks folge **`CRON_SETUP.md`** (cron-job.org).
