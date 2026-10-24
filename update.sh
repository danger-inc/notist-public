#!/usr/bin/env bash
# Holt die neueste notist-Version aus dem Git-Repo und installiert sie. Deine Daten bleiben unberührt.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
old="$(cat app/VERSION 2>/dev/null || echo '?')"
git pull --ff-only
new="$(cat app/VERSION 2>/dev/null || echo '?')"
./install.sh --update
if [[ "$old" != "$new" ]]; then
    echo "notist $old → $new. Was neu ist: app/CHANGELOG.md"
else
    echo "notist $new ist aktuell."
fi
# Läuft notist im Hintergrund weiter, wird es beendet (alles ist gespeichert) – der nächste Start nimmt die neue Version
"$HOME/.local/bin/notist" --quit >/dev/null 2>&1 || true
echo "Fertig – beim nächsten Öffnen läuft die neue Version."
