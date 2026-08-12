# Externer Cron (cron-job.org) — alle 1 Minute

GitHub-Schedule allein reicht nicht (Verzögerungen bis 1h+).  
Deshalb stößt **cron-job.org** den Workflow per API an.

## Warum nicht nur GitHub-Cron?

| Trigger | Zuverlässigkeit |
|---------|-----------------|
| GitHub `schedule` | oft 20–60+ Min Verspätung |
| cron-job.org → `workflow_dispatch` | typisch ± wenige Sekunden |

## Sperren / Rate-Limits — ehrlich

**Was der Monitor macht:** wenige leichte Requests (Shopify `products.json`, WooCommerce Store API, Manor-Suche). Kein Login, kein Cart-Spam.

| Risiko | Realität |
|--------|----------|
| Shop sperrt dich | Unwahrscheinlich bei 1×/Min und öffentlichen JSON-APIs. Möglich: kurz 429 / Captcha (besonders Brack/Akamai — deshalb Brack aus CI aus). |
| GitHub-Runner-IP | Viele Leute teilen sich die IP → Shops blocken eher die **IP-Range** als dich persönlich (schon bei Brack passiert). |
| GitHub Actions-Minuten | **Wichtig bei privatem Repo:** Free ≈ 2000 Min/Monat. Alle 1 Min ≈ 1440 Runs/Tag. Dauert ein Run ~1 Min → Quota in ~1–2 Tagen leer. |

**So lösen das „Profis“:**

1. Leichte Endpoints pollen (wie wir) — nicht ganze HTML-Seiten scrapen  
2. State merken → nur bei Änderung Mail  
3. Aggressive Shops: Google Alert / offizielle Feeds (Brack)  
4. Drop-Bots: Proxies + eigene Server — Overkill für dich  
5. Für 24/7 × 1 Min langfristig: kleines VPS/Always-on **oder** Repo öffentlich (Actions-Minuten dann praktisch unbegrenzt auf Standard-Runnern) **oder** GitHub Pro

**Praktischer Sweet-Spot:** 1 Min ist ok für Drops; wenn Actions-Quota knapp wird → 2 Min oder außerhalb von GitHub hosten.

Concurrent: Workflow bricht alte Runs ab (`cancel-in-progress`), damit sich Minuten-Jobs nicht stapeln.

---

## 1) GitHub Token (einmalig)

1. https://github.com/settings/personal-access-tokens/new  
2. Name: `cardmaniac-cron`  
3. Expiration: z. B. 90 days  
4. Repository access: **Only select repositories** → `cardmaniac-monitor`  
5. Permissions → Repository → **Actions: Read and write**  
6. Generate → Token kopieren

## 2) cron-job.org

1. https://cron-job.org/en/signup/  
2. **Create cronjob**

## 3) Job (jede Minute)

| Feld | Wert |
|------|------|
| Title | `cardmaniac-monitor` |
| URL | `https://api.github.com/repos/BosnjakM/cardmaniac-monitor/actions/workflows/monitor.yml/dispatches` |
| Schedule | every **1** minute |
| Request method | **POST** |
| Timeout | 30s |

**Headers:**

```text
Authorization: Bearer DEIN_GITHUB_TOKEN
Accept: application/vnd.github+json
Content-Type: application/json
X-GitHub-Api-Version: 2022-11-28
```

**Body:**

```json
{"ref":"main"}
```

Enable → Save.

## 4) Test

Unter https://github.com/BosnjakM/cardmaniac-monitor/actions  
sollten ca. jede Minute Runs mit Event **workflow_dispatch** erscheinen.

Wenn die Minute-Quota knapp wird: Schedule auf **2 Minuten** stellen oder Repo öffentlich machen / Monitor auf eigenem Mini-Server laufen lassen.
