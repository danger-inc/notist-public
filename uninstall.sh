#!/usr/bin/env bash
# Entfernt notist wieder. Deine Notizen/Dokumente (~/.local/share/notes/data) bleiben, außer du sagst Ja.
set -euo pipefail
rm -rf "$HOME/.local/share/notes/app" "$HOME/.local/share/notes/tools" "$HOME/.cache/notes"
rm -f  "$HOME/.local/bin/notes" "$HOME/.local/bin/notist"
systemctl --user stop "notes-erinnerung-*.timer" 2>/dev/null || true
rm -f  "$HOME/.local/share/applications/notes.desktop" "$HOME/.local/share/applications/notist.desktop"
rm -f  "$HOME/.local/share/icons/hicolor/scalable/apps/notes.svg" "$HOME/.local/share/icons/hicolor/scalable/apps/notist.svg" \
       "$HOME/.local/share/icons/hicolor/scalable/mimetypes/application-x-notes-share.svg" \
       "$HOME/.local/share/mime/packages/notes-share.xml"
command -v update-mime-database >/dev/null 2>&1 && update-mime-database "$HOME/.local/share/mime" 2>/dev/null || true
command -v update-desktop-database >/dev/null 2>&1 && \
    update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
read -rp "Auch alle Notizen und Dokumente löschen (~/.local/share/notes/data)? [j/N] " ans
if [[ "${ans,,}" =~ ^j ]]; then
    rm -rf "$HOME/.local/share/notes"
    echo "Alles entfernt."
else
    echo "notist entfernt. Deine Daten liegen weiter in ~/.local/share/notes/data."
fi
