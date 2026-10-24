#!/usr/bin/env bash
# Starter für notist. Läuft notist schon (auch unsichtbar im Hintergrund), geht der Aufruf direkt per D-Bus
# hin – ohne Python-/GTK-Start, das Fenster ist sofort da. Sonst wird notist gestartet.
#   notist [datei …]   notist --daemon   notist --quit   notist --check
APP=de.invincible.Notist
MAIN="${NOTIST_APP_DIR:-$HOME/.local/share/notes/app}/notes.py"
if [ $# -eq 0 ] && gdbus call --session --dest org.freedesktop.DBus --object-path /org/freedesktop/DBus \
        --method org.freedesktop.DBus.NameHasOwner "$APP" 2>/dev/null | grep -q true; then
    gdbus call --session --dest "$APP" --object-path /de/invincible/Notist \
        --method org.freedesktop.Application.Activate "{}" >/dev/null 2>&1 && exit 0
fi
exec python3 "$MAIN" "$@"
