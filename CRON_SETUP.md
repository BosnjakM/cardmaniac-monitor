# Externer Cron (cron-job.org) — zuverlässig alle 5 Minuten

GitHub-Schedule allein reicht nicht (Verzögerungen bis 1h+).  
Deshalb stößt **cron-job.org** den Workflow per API an.

## 1) GitHub Token (einmalig)

1. Öffne: https://github.com/settings/personal-access-tokens/new
2. Name: `cardmaniac-cron`
3. Expiration: z. B. 90 days (oder länger)
4. Repository access: **Only select repositories** → `cardmaniac-monitor`
5. Permissions → Repository → **Actions: Read and write**
6. Generate → Token kopieren (`github_pat_…` oder `ghp_…`)

## 2) cron-job.org Account

1. https://cron-job.org/en/signup/ (gleiche Mail ok)
2. Einloggen → **Create cronjob**

## 3) Job eintragen (Copy-Paste)

| Feld | Wert |
|------|------|
| Title | `cardmaniac-monitor` |
| URL | `https://api.github.com/repos/BosnjakM/cardmaniac-monitor/actions/workflows/monitor.yml/dispatches` |
| Schedule | every **5** minutes |
| Request method | **POST** |
| Timeout | 30s |

**Request headers** (Custom):

```text
Authorization: Bearer DEIN_GITHUB_TOKEN
Accept: application/vnd.github+json
Content-Type: application/json
X-GitHub-Api-Version: 2022-11-28
```

**Request body**:

```json
{"ref":"main"}
```

Enable job → Save.

## 4) Test

Nach ≤5 Min sollte unter  
https://github.com/BosnjakM/cardmaniac-monitor/actions  
ein neuer Run mit Event `repository_dispatch` oder `workflow_dispatch` erscheinen  
(bei diesem Setup: **workflow_dispatch**).

---

Optional: Wenn du mir den **cron-job.org API-Key** + **GitHub-PAT** schickst, richte ich den Job per API für dich ein.
