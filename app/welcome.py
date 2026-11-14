# Weiterleitung: der Code liegt seit 5.0 in core/welcome.py (GTK-frei). Gleiches Modulobjekt, damit Änderungen/Tests überall wirken.
import sys
from core import welcome as _m
sys.modules[__name__] = _m
