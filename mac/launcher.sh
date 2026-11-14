#!/bin/bash
# Startskript im Bündel notist.app (Contents/MacOS/notist). Finder startet Apps ohne Shell-Umgebung:
# Homebrew-Pfade, Typelibs und UTF-8 müssen hier gesetzt werden.
BREW=/opt/homebrew; [ -x "$BREW/bin/python3" ] || BREW=/usr/local
[ -x "$BREW/bin/python3" ] || BREW="$(brew --prefix 2>/dev/null || echo /opt/homebrew)"
export PATH="$BREW/bin:$BREW/sbin:/Library/TeX/texbin:$HOME/Library/Application Support/notist/tools:$PATH"
export XDG_DATA_DIRS="$BREW/share:${XDG_DATA_DIRS:-/usr/local/share:/usr/share}"
export GI_TYPELIB_PATH="$BREW/lib/girepository-1.0${GI_TYPELIB_PATH:+:$GI_TYPELIB_PATH}"
export DYLD_FALLBACK_LIBRARY_PATH="$BREW/lib:${DYLD_FALLBACK_LIBRARY_PATH:-/usr/lib}"
if [ -z "${LANG:-}" ] || [ "$LANG" = C ] || [ "$LANG" = POSIX ]; then          # Finder-Start: keine Sprache gesetzt
    loc="$(defaults read -g AppleLocale 2>/dev/null | sed 's/@.*//')"
    export LANG="${loc:-en_US}.UTF-8"
fi
export PYTHONUTF8=1
MAIN="${NOTIST_APP_DIR:-$HOME/Library/Application Support/notist/app}/notes.py"
exec "$BREW/bin/python3" -X utf8 "$MAIN" "$@"
