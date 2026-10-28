# Bilder verkleinern/neu kodieren (Einstellungen → Words → Bilder komprimieren).
import base64

import gi

gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf, GLib  # noqa: E402

# Stufe → (längste Seite in Pixeln, Format, Qualität)
LEVELS = {"off": None, "low": (1400, "png", 6), "mid": (1600, "jpeg", 88), "high": (1000, "jpeg", 78)}
NAMES = [("off", "Aus (Originale behalten)"), ("low", "Leicht – höchstens 1400 px, PNG bleibt PNG (Schrift bleibt scharf)"),
         ("mid", "Mittel – höchstens 1600 px, Fotos/Screenshots als JPEG"),
         ("high", "Stark – höchstens 1000 px, JPEG")]


def _opaque(pb):
    if not pb.get_has_alpha():
        return True
    px = pb.get_pixels()
    if pb.get_rowstride() != pb.get_width() * 4:
        return False
    a = px[3::4]
    return a.count(255) == len(a)


def shrink(data, level):
    """(bytes, mime) des verkleinerten Bildes – oder (data, None), wenn nichts gewonnen wird."""
    spec = LEVELS.get(level)
    if not spec or not data:
        return data, None
    if data[:3] == b"GIF" or data[:4] == b"RIFF":          # Animationen/WebP lassen wir in Ruhe
        return data, None
    try:
        loader = GdkPixbuf.PixbufLoader()
        loader.write(data)
        loader.close()
        pb = loader.get_pixbuf()
        if pb is None:
            return data, None
        maxpx, fmt, quality = spec
        w, h = pb.get_width(), pb.get_height()
        scale = min(1.0, maxpx / max(w, h))
        if scale < 1:
            pb = pb.scale_simple(max(1, round(w * scale)), max(1, round(h * scale)), GdkPixbuf.InterpType.HYPER)
        if fmt == "jpeg" and _opaque(pb):
            if pb.get_has_alpha():
                pb = GdkPixbuf.Pixbuf.new_from_bytes(GLib.Bytes.new(_drop_alpha(pb)), GdkPixbuf.Colorspace.RGB, False, 8,
                                                     pb.get_width(), pb.get_height(), pb.get_width() * 3)
            ok, out = pb.save_to_bufferv("jpeg", ["quality"], [str(quality)])
            mime = "image/jpeg"
        else:
            ok, out = pb.save_to_bufferv("png", ["compression"], [str(quality or 6)])
            mime = "image/png"
    except (GLib.Error, ValueError):
        return data, None
    if ok and len(out) < len(data) * 0.9:
        return bytes(out), mime
    return data, None


def _drop_alpha(pb):
    px = pb.get_pixels()
    out = bytearray(pb.get_width() * pb.get_height() * 3)
    out[0::3], out[1::3], out[2::3] = px[0::4], px[1::4], px[2::4]
    return bytes(out)


def shrink_blocks(blocks, level):
    """Alle Bilder in den Blöcken (in place) verkleinern. Gibt die gesparten Bytes zurück."""
    saved = 0
    for b in blocks or ():
        for r in b.get("runs", ()) if b.get("t") == "p" else ():
            if not r.get("img"):
                continue
            old = base64.b64decode(r["img"])
            new, mime = shrink(old, level)
            if mime:
                r["img"], r["mime"] = base64.b64encode(new).decode(), mime
                saved += len(old) - len(new)
    return saved
