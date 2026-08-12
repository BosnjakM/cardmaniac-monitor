# Cardmaniac Pre-Order Monitor

Prüft alle **10 Minuten** die Pre-Order-Seite von [cardmaniac.ch](https://cardmaniac.ch/collections/pre-order) und schickt eine Mail an **mab151204@gmail.com**, sobald ein **neues Produkt** erscheint.

Bei Treffern zu z. B. „30th Celebration“ / „Tech-Sticker“ steht **PRIORITÄT** im Betreff.

## Setup (einmalig, ca. 5 Minuten)

### 1. Repo auf GitHub erstellen

Im Terminal im Ordner `cardmaniac`:

```bash
git init
git add .
git commit -m "Initial cardmaniac pre-order monitor"
gh repo create cardmaniac-monitor --private --source=. --remote=origin --push
```

(Oder manuell auf github.com ein leeres Repo anlegen und pushen.)

### 2. Gmail App-Passwort erzeugen

1. Google-Konto → [Sicherheit](https://myaccount.google.com/security)
2. **2-Schritt-Bestätigung** muss an sein
3. Suche nach **App-Passwörter** → neues Passwort für „Mail“ erzeugen
4. Das 16-stellige Passwort kopieren (ohne Leerzeichen)

### 3. GitHub Secrets setzen

Im Repo: **Settings → Secrets and variables → Actions → New repository secret**

| Name         | Wert                          |
|--------------|-------------------------------|
| `SMTP_USER`  | `mab151204@gmail.com`         |
| `SMTP_PASS`  | dein 16-stelliges App-Passwort |

### 4. Testen

**Actions → Cardmaniac Pre-Order Monitor → Run workflow**

Wenn nichts Neues da ist, kommt keine Mail (aktuell sind die 3 Tin-Boxen schon als „gesehen“ gespeichert). Der Lauf sollte trotzdem grün sein.

## Lokal testen (optional)

```bash
export SMTP_USER="mab151204@gmail.com"
export SMTP_PASS="dein-app-passwort"
python3 monitor.py
```

## Hinweis

GitHub-Cron-Jobs laufen oft nicht exakt auf die Minute — Verzögerungen von ein paar Minuten sind normal. Für Pre-Orders reicht das in der Regel.
