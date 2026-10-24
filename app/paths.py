# Zentrale Pfade. NOTES_DATA_DIR / NOTES_HOME überschreiben sie (für Tests oder eine portable Installation).
import os

HOME = os.environ.get("NOTES_HOME") or os.path.expanduser("~/.local/share/notes")
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
