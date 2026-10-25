#!/usr/bin/env bash
# notist-Installer. Installiert die App ins eigene Benutzerverzeichnis (~/.local).
# Kein root nötig außer für die Systempakete (fragt vorher nach).
# Gehört ins Weitergabe-Paket, das packaging/make-dist.sh baut (notes-dist/install.sh).
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$HOME/.local/share/notes/app"           # Daten liegen daneben in ~/.local/share/notes/data
BIN="$HOME/.local/bin"
APPS="$HOME/.local/share/applications"
FONTS="$HOME/.local/share/fonts"
ICONS="$HOME/.local/share/icons/hicolor/scalable/apps"

. "$SRC/pkg.sh"

say "== notist installieren (Notizen · Words · LaTeX) =="
[[ "${1:-}" == "--update" ]] && echo "Update-Modus: Systempakete werden nicht angefasst."
echo

# ---------------------------------------------------------------- Systempakete
# ./install.sh --update (von update.sh): keine Rückfrage, Pakete nicht anfassen
UPDATE=0; [[ "${1:-}" == "--update" ]] && UPDATE=1
if ask "Systemabhängigkeiten jetzt per Paketmanager installieren?"; then
    pkg_install \
        "gtk4 python python-gobject python-cairo glib2 poppler-glib hunspell hunspell-de hunspell-en_us fontconfig adwaita-icon-theme xdg-utils libnotify" \
        "python3 python3-gi python3-gi-cairo python3-cairo gir1.2-gtk-4.0 libglib2.0-bin gir1.2-poppler-0.18 libhunspell-1.7-0 hunspell-de-de hunspell-en-us fontconfig adwaita-icon-theme xdg-utils libnotify-bin" \
        "python3 python3-gobject python3-cairo gtk4 glib2 poppler-glib hunspell hunspell-de hunspell-en-US fontconfig adwaita-icon-theme xdg-utils libnotify" \
        "python3 python3-gobject python3-gobject-cairo python3-gobject-Gdk python3-pycairo typelib-1_0-Gtk-4_0 typelib-1_0-Poppler-0_18 glib2-tools libhunspell-1_7-0 myspell-de_DE myspell-en_US fontconfig adwaita-icon-theme xdg-utils libnotify-tools" \
        || warn "Paketinstallation nicht vollständig – weiter."
elif (( ! UPDATE )); then
    echo "Übersprungen. (Bei fehlenden Paketen: siehe README.md)"
fi
echo

# ---------------------------------------------------------------- Daten sichern (nur Sicherheitsnetz)
# Der Installer fasst ~/.local/share/notes/data, die Einstellungen und ~/Documents/notist nie an – er kopiert nur den
# Programmcode. Trotzdem legt er vorher eine ZIP-Sicherung der Daten an (die letzten 5 bleiben).
DATA_DIR="${NOTES_DATA_DIR:-$HOME/.local/share/notes/data}"
if [[ -d "$DATA_DIR" ]] && [[ -n "$(ls -A "$DATA_DIR" 2>/dev/null)" ]]; then
    BK="$HOME/.local/share/notes/backups"
    mkdir -p "$BK"
    python3 - "$DATA_DIR" "$BK/vor-installation-$(date +%Y%m%d-%H%M%S).zip" <<'PY' && echo "Daten gesichert in $BK" || warn "Datensicherung nicht möglich – Daten bleiben trotzdem unangetastet."
import os, sys, zipfile
src, dest = sys.argv[1:3]
with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
    for root, _d, files in os.walk(src):
        for f in files:
            p = os.path.join(root, f)
            z.write(p, os.path.relpath(p, os.path.dirname(src)))
PY
    ls -1t "$BK"/vor-installation-*.zip 2>/dev/null | tail -n +6 | xargs -r rm -f
fi

# ---------------------------------------------------------------- App kopieren
say "Kopiere notist nach $APP_DIR ..."
case "$APP_DIR" in "$DATA_DIR"|"$DATA_DIR"/*) echo "Abbruch: Programmordner liegt im Datenordner." >&2; exit 1;; esac
mkdir -p "$APP_DIR" "$BIN" "$APPS" "$FONTS" "$ICONS"
cp -rf "$SRC/app/." "$APP_DIR/"
chmod +x "$APP_DIR/notes.py"
rm -f "$BIN/notist"                                # früher eine Verknüpfung auf notes.py
install -m 755 "$SRC/notist.sh" "$BIN/notist"      # Starter: läuft notist schon, öffnet er das Fenster sofort
ln -sf "$BIN/notist" "$BIN/notes"                  # alter Befehl funktioniert weiter
# läuft eine alte Version im Hintergrund, beenden – der nächste Aufruf startet die neue
timeout 5 python3 "$APP_DIR/notes.py" --quit >/dev/null 2>&1 || true

sed "s|@EXEC@|$BIN/notist|g" "$SRC/notist.desktop.in" > "$APPS/notist.desktop"
cp -f "$APP_DIR/logo/notist.svg" "$ICONS/notist.svg"
# Reste vom alten Namen „Notes“ aufräumen (Daten bleiben, wo sie sind)
rm -f "$APPS/notes.desktop" "$ICONS/notes.svg"
rm -f "$BIN/textwise" "$APPS/textwise.desktop" "$ICONS/textwise.svg"     # alter Name bis 2026-10
refresh_desktop

# ---------------------------------------------------------------- Schriftart (Symbole)
if ! fc-list 2>/dev/null | grep -qi "JetBrainsMono Nerd Font"; then
    say "Installiere JetBrainsMono Nerd Font (Schrift der Oberfläche) ..."
    cp -f "$SRC/fonts/"*.ttf "$FONTS/"
    fc-cache -f "$FONTS" >/dev/null 2>&1 || true
else
    echo "Nerd Font schon vorhanden – überspringe."
fi
echo

# ---------------------------------------------------------------- Selbsttest
say "Prüfe Abhängigkeiten ..."
check_gtk || true
{ python3 "$APP_DIR/notes.py" --check 2>&1 | grep -v "libenchant-WARNING"; } || warn "Siehe oben – notist startet trotzdem, nur die genannten Teile fehlen."
echo

path_hint
say "Fertig!  Starten mit:  notist   (oder über das Anwendungsmenü)"
echo "LaTeX: Beim ersten Öffnen des LaTeX-Modus bietet notist an, den Compiler (Tectonic) selbst einzurichten."
echo "Aktualisieren:   ./update.sh     Deinstallieren:  ./uninstall.sh"
