# Alle Module des Kerns auf einmal laden (Test: kein „gi“ nötig –
#   python -c "import sys; sys.modules['gi']=None; import core.all").
from core import (paths, store, linked, docfmt, odf, exports, mdnotes, notesconvert, share, latexdata,  # noqa: F401
                  reminders, handylink, sync2, pkgcmds, welcome, xlsx, autofix, dictdb, texcore, plat, api)  # noqa: F401
