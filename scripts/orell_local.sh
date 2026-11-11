#!/bin/zsh
# Runs on this Mac, where Orell Füssli answers. GitHub's servers are blocked.
set -u
export GIT_TERMINAL_PROMPT=0
export PATH="/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:/usr/local/bin:$PATH"

# Desktop is blocked for background jobs. This checkout lives outside it.
ROOT="$HOME/Library/Application Support/cardmaniac-monitor/repo"
LOCK="/tmp/cardmaniac-orell.lock"
VENV="$HOME/Library/Application Support/cardmaniac-monitor/py"
cd "$ROOT" || exit 1

if ! mkdir "$LOCK" 2>/dev/null; then
  echo "$(date -u +%H:%M:%S) Orell-Check läuft schon"
  exit 0
fi
trap 'rmdir "$LOCK"' EXIT

if [[ ! -x "$VENV/bin/python" ]]; then
  echo "$(date -u +%H:%M:%S) richte Python ein"
  mkdir -p "$(dirname "$VENV")"
  python3 -m venv "$VENV" || exit 1
  "$VENV/bin/pip" install -q playwright || exit 1
fi

git pull --rebase --autostash origin main || {
  echo "$(date -u +%H:%M:%S) git pull fehlgeschlagen"
  exit 1
}

"$VENV/bin/python" monitor.py --orell-only || exit 1

if git diff --quiet -- seen_orell.json; then
  exit 0
fi
git add seen_orell.json
git commit -m "chore: update Orell state" || exit 0
for i in 1 2 3 4 5 6; do
  git pull --rebase --autostash origin main || true
  if git push origin HEAD:main; then
    echo "$(date -u +%H:%M:%S) Orell-State gepusht"
    exit 0
  fi
  sleep "$i"
done
echo "$(date -u +%H:%M:%S) Orell-State nicht gepusht"
exit 0
