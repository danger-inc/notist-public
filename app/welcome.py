# Willkommens-Eintrag beim allerersten Start: kurz zeigen, was notist kann und wo die Kürzel stecken.
import docfmt as df

DE = ("Willkommen bei notist", [
    ("p", "Drei Wege zu schreiben in einer App: Alt+1 Notizen · Alt+2 Words · Alt+3 LaTeX. Alles speichert sich von selbst."),
    ("h2", "Die wichtigsten Kürzel"),
    ("b", "Strg+Tab – zur zuletzt geöffneten Datei springen (nochmal drücken = zurück)"),
    ("b", "Strg+Z – Rückgängig, auch für Formatierung, Bilder und Tabellen"),
    ("b", "Strg+F – im Eintrag suchen · Strg+Umschalt+F – in allen suchen"),
    ("b", "Strg+Umschalt+T – Übersetzer Deutsch ⇄ Englisch"),
    ("b", "F1 – alle Tastenkürzel"),
    ("h2", "In Words ausprobieren"),
    ("b", "Bild anklicken: an den Ecken ziehen ändert die Größe; „vor Text“ oder „hinter Text“ lässt es frei schweben."),
    ("b", "Oben rechts „fließend“: schreiben wie in Notion – tippe „/“ für Blöcke."),
    ("b", "Ansicht → Seitenbreite: Papier und Schrift zoomen immer gemeinsam."),
    ("b", ".docx-Dateien einfach hineinziehen oder mit Strg+O öffnen; Export als Word, PDF oder Markdown."),
    ("h2", "Gut zu wissen"),
    ("b", "Versionsverlauf je Eintrag: Strg+Umschalt+H · tägliche Sicherung: Einstellungen (Strg+,)"),
    ("b", "Bilder werden beim Einfügen verkleinert, damit Dokumente schnell bleiben – abschaltbar in den Einstellungen."),
    ("b", "Design und Sprache (Deutsch/English) findest du ebenfalls in den Einstellungen."),
    ("p", "Diesen Eintrag kannst du jederzeit löschen."),
])

EN = ("Welcome to notist", [
    ("p", "Three ways to write in one app: Alt+1 notes · Alt+2 words · Alt+3 latex. Everything saves itself."),
    ("h2", "The most useful shortcuts"),
    ("b", "Ctrl+Tab – jump to the last opened file (press again to go back)"),
    ("b", "Ctrl+Z – undo, also for formatting, images and tables"),
    ("b", "Ctrl+F – search in this entry · Ctrl+Shift+F – search everywhere"),
    ("b", "Ctrl+Shift+T – translator German ⇄ English"),
    ("b", "F1 – all keyboard shortcuts"),
    ("h2", "Try in Words"),
    ("b", "Click an image: drag a corner to resize; “in front of text” or “behind text” lets it float freely."),
    ("b", "Top right “flow”: write like in Notion – type “/” for blocks."),
    ("b", "View → Page width: paper and text always zoom together."),
    ("b", "Drop .docx files in or open them with Ctrl+O; export as Word, PDF or Markdown."),
    ("h2", "Good to know"),
    ("b", "Version history per entry: Ctrl+Shift+H · daily backup: settings (Ctrl+,)"),
    ("b", "Images are shrunk when inserted so documents stay fast – can be turned off in the settings."),
    ("b", "Theme and language (German/English) are in the settings, too."),
    ("p", "You can delete this entry at any time."),
])


def blocks(lang):
    title, rows = EN if lang == "en" else DE
    out = []
    for kind, text in rows:
        if kind == "b":
            out.append(df.para(text, list="bullet"))
        elif kind == "h2":
            out.append(df.para(text, style="h2"))
        else:
            out.append(df.para(text))
    return title, out
