# Weiterleitung: der Code liegt seit 5.0 in core/share.py (GTK-frei). Gleiches Modulobjekt, damit Änderungen/Tests überall wirken.
import sys
from core import share as _m
sys.modules[__name__] = _m
