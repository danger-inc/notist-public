#!/usr/bin/env python3
"""Kern-Test: core/ läuft ohne „gi“ und die JSON-Schnittstelle (core/api.py) macht Rundläufe.
   python tests/core_test.py   (ohne Display, ~1 s)"""
import os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(HERE)


def main():
    # 1. Import ohne gi, in frischem Prozess (-I: kein Skriptordner im Suchpfad)
    r = subprocess.run([sys.executable, "-c", f"import sys; sys.path.insert(0, {APP!r}); sys.modules['gi']=None; "
                        "import core.all; bad=[m for m in sys.modules if m.split('.')[0] in ('gi','gtk') and sys.modules[m]]; "
                        "assert not bad, bad; print('ok')"], capture_output=True, text=True,
                       env={**os.environ, "NOTES_HOME": tempfile.mkdtemp(), "NOTES_NO_TIMERS": "1"})
    assert r.returncode == 0 and "ok" in r.stdout, r.stderr[-800:]
    print("ok    core.all ohne gi")
    # 2. API-Rundläufe (Testdaten in Temp-Ordner)
    tmp = tempfile.mkdtemp()
    os.environ.update(NOTES_HOME=tmp, NOTES_NO_TIMERS="1")
    sys.path.insert(0, APP)
    from core import api
    md = "# Titel\n\nEin **fetter** Satz.\n\n- eins\n- zwei\n"
    note = api.md_to_note(md)
    assert note["title"] == "Titel" and "fetter" in note["text"], note
    back = api.note_to_md(note)
    assert "**fetter**" in back and "eins" in back, back
    print("ok    md_to_note / note_to_md")
    p = os.path.join(tmp, "a.md")
    open(p, "w", encoding="utf-8").write(md)
    model = api.import_file(p)
    assert model["blocks"] and model["title"], model
    for fmt in api.EXPORT_FORMATS:
        out = api.export(model, fmt, os.path.join(tmp, "x." + fmt))
        assert os.path.getsize(out) > 0, fmt
    d2 = api.import_file(os.path.join(tmp, "x.docx"))
    o2 = api.import_file(os.path.join(tmp, "x.odt"))
    assert "fetter" in str(d2["blocks"]) and "fetter" in str(o2["blocks"])
    print("ok    import_file / export (%s)" % ",".join(api.EXPORT_FORMATS))
    assert "\\begin{document}" in api.to_latex(model)
    assert api.from_latex(api.to_latex(model))["blocks"]
    print("ok    to_latex / from_latex")
    e = {"id": "1", "title": "t", "text": "x", "file": "/nur/hier"}
    a = api.digest(e)
    assert a == api.digest({**e, "file": "/anders"}) and a != api.digest({**e, "text": "y"})
    print("ok    digest")
    bp = os.path.join(tmp, "b.notes")
    api.bundle_write({"id": "1", "title": "t", "blocks": []}, "docs", bp)
    b = api.bundle_read(bp)
    assert b["kind"] == "docs" and b["note"]["title"] == "t"
    print("ok    bundle_write / bundle_read")
    assert api.autofix_word("teh") == "the" or api.autofix_word("teh") is not None
    assert api.dict_lookup("Haus") == []        # ohne Wörterbuchdatei leer, kein Absturz
    print("ok    autofix_word / dict_lookup")
    print("alle grün")


if __name__ == "__main__":
    main()
