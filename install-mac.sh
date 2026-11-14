#!/usr/bin/env bash
# notist für macOS (Apple Silicon): installiert die App und baut ~/Applications/notist.app.
#   ./install-mac.sh              installieren (fragt vor Homebrew-Paketen)
#   ./install-mac.sh --update     nur Programmcode + .app neu (keine Pakete, keine Rückfragen)
#   ./install-mac.sh --yes        alle Rückfragen mit Ja (CI)
#   ./install-mac.sh uninstall    entfernen (Notizen bleiben, außer du sagst Ja)
# Homebrew-GTK/PyGObject (dieselbe App wie unter Linux). Keine libadwaita nötig. Daten: ~/Library/Application Support/notist
# (macOS-bash 3.2-kompatibel: kein ${x,,}, kein timeout.)
# Test ohne Mac: NOTIST_FORCE_MAC=1 (dann müssen brew/iconutil/curl o. Ä. als Stubs im PATH stehen).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$HERE"                                                  # Ordner mit app/: Paket-Wurzel, Repo-Wurzel oder (Quelle) packaging/..
for c in "$HERE" "$HERE/.." "$HERE/../.."; do [[ -d "$c/app" ]] && { SRC="$(cd "$c" && pwd)"; break; }; done
[[ -d "$SRC/app" ]] || SRC="$(cd "$HERE/../.." && pwd)"
MACDIR="$HERE"; [[ -f "$MACDIR/Info.plist.in" ]] || MACDIR="$HERE/mac"       # Info.plist.in + launcher.sh
SUP="$HOME/Library/Application Support/notist"
APP_DIR="$SUP/app"
BUNDLE="$HOME/Applications/notist.app"
BIN="$HOME/.local/bin"
FONTS="$HOME/Library/Fonts"
DICT_BASE="https://raw.githubusercontent.com/LibreOffice/dictionaries/master"

say()  { printf '\033[1;38;5;216m%s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m%s\033[0m\n' "$*"; }
YES=0; UPDATE=0; MODE=install
for a in "$@"; do
    case "$a" in
        --yes|-y) YES=1;; --update) UPDATE=1; YES=1;; uninstall|--uninstall) MODE=uninstall;;
        -h|--help) sed -n 2,9p "${BASH_SOURCE[0]}"; exit 0;;
        *) echo "Unbekannte Option: $a" >&2; exit 2;;
    esac
done
ask() { (( YES )) && return 0; read -rp "$1 [J/n] " ans; [[ ! "$ans" =~ ^[nN] ]]; }

if [[ "$(uname -s)" != Darwin && -z "${NOTIST_FORCE_MAC:-}" ]]; then
    echo "Dieser Installer ist für macOS. Unter Linux: ./install.sh" >&2; exit 1
fi

# ---------------------------------------------------------------- Entfernen
if [[ "$MODE" == uninstall ]]; then
    "$BUNDLE/Contents/MacOS/notist" --quit >/dev/null 2>&1 || true
    for p in "$HOME"/Library/LaunchAgents/de.notist.*.plist; do
        [[ -e "$p" ]] || continue
        launchctl unload "$p" >/dev/null 2>&1 || true; rm -f "$p"
    done
    rm -rf "$BUNDLE" "$APP_DIR" "$SUP/tools" "$HOME/Library/Caches/notist"
    rm -f "$BIN/notist" "$BIN/notes" "$FONTS/notes-icons.ttf"
    read -rp "Auch alle Notizen und Dokumente löschen ($SUP/data)? [j/N] " ans
    if [[ "$ans" =~ ^[jJyY] ]]; then rm -rf "$SUP"; echo "Alles entfernt."
    else echo "notist entfernt. Deine Daten liegen weiter in $SUP/data (und ~/Documents/notist)."; fi
    exit 0
fi

say "== notist für macOS installieren (Notizen · Words · LaTeX) =="
[[ "$(uname -m)" == arm64 || -n "${NOTIST_FORCE_MAC:-}" ]] || warn "Hinweis: getestet nur auf Apple Silicon (arm64)."

# ---------------------------------------------------------------- Homebrew + Pakete
BREW="$(command -v brew || true)"
[[ -z "$BREW" && -x /opt/homebrew/bin/brew ]] && BREW=/opt/homebrew/bin/brew
if [[ -z "$BREW" ]]; then
    cat >&2 <<'T'
Homebrew fehlt. notist braucht GTK 4 und Python-Bindungen, die Homebrew liefert.
Einmalig installieren (Skript von https://brew.sh prüfen und im Terminal ausführen):
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
Danach diesen Installer erneut starten.
T
    exit 1
fi
PREFIX="$("$BREW" --prefix)"
if (( ! UPDATE )); then
    PKGS="gtk4 pygobject3 py3cairo poppler hunspell librsvg adwaita-icon-theme terminal-notifier"
    if ask "Per Homebrew installieren: $PKGS ?"; then
        # shellcheck disable=SC2086
        "$BREW" install $PKGS || warn "Homebrew meldet Fehler – weiter (notist --check zeigt, was fehlt)."
    else
        echo "Übersprungen – ohne diese Pakete startet notist nicht."
    fi
fi
PY="$PREFIX/bin/python3"; [[ -x "$PY" ]] || PY="$(command -v python3)"

# ---------------------------------------------------------------- Datensicherung (Sicherheitsnetz, wie unter Linux)
DATA_DIR="${NOTES_DATA_DIR:-$SUP/data}"
if [[ -d "$DATA_DIR" && -n "$(ls -A "$DATA_DIR" 2>/dev/null)" ]]; then
    BK="$SUP/backups"; mkdir -p "$BK"
    "$PY" -I - "$DATA_DIR" "$BK/vor-installation-$(date +%Y%m%d-%H%M%S).zip" <<'PYE' && echo "Daten gesichert in $BK" || warn "Datensicherung nicht möglich – Daten bleiben unangetastet."
import os, sys, zipfile
src, dest = sys.argv[1:3]
with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
    for root, _d, files in os.walk(src):
        for f in files:
            p = os.path.join(root, f)
            z.write(p, os.path.relpath(p, os.path.dirname(src)))
PYE
    ls -1t "$BK"/vor-installation-*.zip 2>/dev/null | tail -n +6 | while read -r f; do rm -f "$f"; done
fi

# ---------------------------------------------------------------- Programmcode
case "$APP_DIR" in "$DATA_DIR"|"$DATA_DIR"/*) echo "Abbruch: Programmordner liegt im Datenordner." >&2; exit 1;; esac
say "Kopiere notist nach $APP_DIR ..."
mkdir -p "$APP_DIR" "$BIN" "$FONTS" "$HOME/Applications"
[[ -x "$BUNDLE/Contents/MacOS/notist" ]] && "$BUNDLE/Contents/MacOS/notist" --quit >/dev/null 2>&1 || true
cp -Rf "$SRC/app/." "$APP_DIR/"
chmod +x "$APP_DIR/notes.py"
VERSION="$(cat "$APP_DIR/VERSION" 2>/dev/null || echo 0)"

# Symbolschrift: die mitgelieferte Schrift lädt notist selbst; die Nerd Font nur, falls sie fehlt
if ! ls "$FONTS"/JetBrainsMono*Nerd* /Library/Fonts/JetBrainsMono*Nerd* >/dev/null 2>&1 && [[ -d "$SRC/fonts" ]]; then
    cp -f "$SRC/fonts/"*.ttf "$FONTS/" 2>/dev/null || true
fi

# ---------------------------------------------------------------- Wörterbücher (de/en) – nur laden, wenn sie fehlen
HUN="$SUP/hunspell"; mkdir -p "$HUN"
get_dict() {   # Name, Pfad im LibreOffice-Dictionaries-Repo
    [[ -s "$HUN/$1.aff" && -s "$HUN/$1.dic" ]] && return 0
    curl -fsSL --max-time 60 -o "$HUN/$1.aff.part" "$DICT_BASE/$2.aff" \
        && curl -fsSL --max-time 60 -o "$HUN/$1.dic.part" "$DICT_BASE/$2.dic" \
        && mv "$HUN/$1.aff.part" "$HUN/$1.aff" && mv "$HUN/$1.dic.part" "$HUN/$1.dic" \
        || { rm -f "$HUN/$1".*.part; warn "Wörterbuch $1 nicht geladen (offline?) – Rechtschreibung für diese Sprache fehlt."; return 0; }
}
if [[ ! -s "$HUN/de_DE_frami.dic" || ! -s "$HUN/en_US.dic" ]]; then
    echo "Lade Wörterbücher von LibreOffice (Lizenzen: de_DE_frami GPL-2.0/GPL-3.0, en_US BSD/MIT-artig; Texte liegen dem Quell-Repo bei)."
    get_dict de_DE_frami de/de_DE_frami
    get_dict en_US en/en_US
fi

# ---------------------------------------------------------------- notist.app bauen
say "Baue $BUNDLE ..."
rm -rf "$BUNDLE"
mkdir -p "$BUNDLE/Contents/MacOS" "$BUNDLE/Contents/Resources"
sed -e "s|@VERSION@|$VERSION|g" "$MACDIR/Info.plist.in" > "$BUNDLE/Contents/Info.plist"
install -m 755 "$MACDIR/launcher.sh" "$BUNDLE/Contents/MacOS/notist"

# Symbol: SVG → iconset → .icns (rsvg-convert kommt mit librsvg; sips kann kein SVG)
ICONSET="$(mktemp -d)/notist.iconset"; mkdir -p "$ICONSET"
LOGO="$APP_DIR/logo/notist.svg"
if command -v rsvg-convert >/dev/null 2>&1 || [[ -x "$PREFIX/bin/rsvg-convert" ]]; then
    RSVG="$(command -v rsvg-convert || echo "$PREFIX/bin/rsvg-convert")"
    for sz in 16 32 128 256 512; do
        "$RSVG" -w $sz -h $sz "$LOGO" -o "$ICONSET/icon_${sz}x${sz}.png" 2>/dev/null || true
        "$RSVG" -w $((sz*2)) -h $((sz*2)) "$LOGO" -o "$ICONSET/icon_${sz}x${sz}@2x.png" 2>/dev/null || true
    done
fi
if ls "$ICONSET"/*.png >/dev/null 2>&1 && command -v iconutil >/dev/null 2>&1; then
    iconutil -c icns "$ICONSET" -o "$BUNDLE/Contents/Resources/notist.icns" || warn "Symbol nicht erzeugt – .app hat das Standardsymbol."
else
    warn "Symbol nicht erzeugt (rsvg-convert/iconutil fehlt) – .app hat das Standardsymbol."
fi
rm -rf "$(dirname "$ICONSET")"

# Befehl „notist“ im Terminal
cat > "$BIN/notist" <<EOF
#!/usr/bin/env bash
exec "$BUNDLE/Contents/MacOS/notist" "\$@"
EOF
chmod +x "$BIN/notist"; ln -sf "$BIN/notist" "$BIN/notes"
LSREG=/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister
[[ -x "$LSREG" ]] && "$LSREG" -f "$BUNDLE" >/dev/null 2>&1 || true
touch "$BUNDLE"

# ---------------------------------------------------------------- Selbsttest
say "Prüfe Abhängigkeiten ..."
"$BUNDLE/Contents/MacOS/notist" --check || warn "Siehe oben – notist startet trotzdem, nur die genannten Teile fehlen."
case ":$PATH:" in *":$BIN:"*) ;; *) echo "Tipp: $BIN in den PATH aufnehmen, damit „notist“ im Terminal geht.";; esac
say "Fertig!  Öffnen: ~/Applications/notist.app (oder Spotlight „notist“)"
echo "Beim ersten Start fragt macOS evtl. nach Zugriff auf Dokumente und Mitteilungen."
echo "LaTeX: beim ersten Öffnen des LaTeX-Modus richtet notist den Compiler (Tectonic) selbst ein."
echo "Aktualisieren: ./install-mac.sh --update     Entfernen: ./install-mac.sh uninstall"
