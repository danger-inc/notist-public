# Zentrale Pfade. NOTES_DATA_DIR / NOTES_HOME überschreiben sie (für Tests oder eine portable Installation).
import os

from core import plat

HOME = plat.data_home()          # NOTES_HOME gewinnt; Mac: ~/Library/Application Support/notist
DATA = os.environ.get("NOTES_DATA_DIR") or os.path.join(HOME, "data")
NOTES = os.path.join(DATA, "notes")
DOCS = os.path.join(DATA, "docs")
LATEX = os.path.join(DATA, "latex")
LATEX_FILES = os.path.join(DATA, "latex-files")
HISTORY = os.path.join(DATA, "history")
PREFS = os.path.join(DATA, "prefs.json")
WORDS = os.path.join(DATA, "words.txt")
BACKUPS = os.path.join(HOME, "backups")        # bewusst außerhalb von data/
TOOLS = os.path.join(HOME, "tools")


def read_file(path, binary=False):
    """Datei ganz lesen und sofort schließen (open(...).read() ließ das Schließen dem Müllsammler: ResourceWarning)."""
    if binary:
        with open(path, "rb") as f:
            return f.read()
    with open(path, encoding="utf-8") as f:
        return f.read()
