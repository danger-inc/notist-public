# Bewusste Verluste je Format (Stand Schritt 3, 2026-11-13)

Der Rundlauftest (`python tests/roundtrip.py`) entfernt diese Merkmale vor dem Vergleich (`MASK`/`EXEMPT` in roundtrip.py).
Alles, was hier **nicht** steht, muss verlustfrei zurückkommen. Mac und Handy müssen dieselben Gold-Modelle bestehen
(Handy: nur die Spalte der Formate, die es kennt).

## DOCX (schreiben + lesen)
- Seiteneinstellungen: `track` (Änderungen verfolgen an/aus), `author`, `page_color`, `watermark` gehen nicht in die Datei.
- PDF-Blöcke und Tabellen-Anhänge: PDF-Block wird nicht geschrieben (nur im PDF-Export); XLSX-Block wird zur Tabelle.
- Tabellenstil: `accent` nur mit Kopfzeile erkennbar; `stripes` erst ab 2 Inhaltszeilen; einspaltige Tabelle mit
  „erste Spalte betont“ wird als Kopfzeile gelesen (alles fett).
- Unterstreichen auf Link-Text: Links sind in Word ohnehin unterstrichen, `u` am Link bleibt nicht erhalten.
- Kommentar-Ids werden beim Speichern neu vergeben (Inhalt/Autor bleiben).

## ODT
- Keine Kommentare, keine Änderungsverfolgung (`cm`, `tc`), keine schwebenden Bilder (`fl`), keine Zeilennummern
  (`lnum`), kein Wasserzeichen, keine Seitenfarbe, kein `author`/`track`.
- Tabellenstil (Kopfzeile, Rahmen, Akzent, Streifen, Spaltenbreiten, Ausrichtung, Abstand) geht verloren – Tabelle bleibt.
- Änderungen werden beim Schreiben angenommen (gelöschter Text entfällt).

## Markdown
- Nur: Überschriften (Titel wird „Überschrift 1“), Listen, Zitat, Code, Tabellen (ohne Stil, Zeilenumbruch in Zelle → Leerzeichen),
  fett/kursiv/durchgestrichen/Link, `---`.
- Weg: unterstrichen, hoch/tief, Schrift, Größe, Farbe, Markierung, Ausrichtung, Abstand, Einzug (außer Liste), Seitenumbruch,
  Inhaltsverzeichnis (wird zur Linkliste), Bilder, schwebende Bilder, Kommentare, Änderungen (angenommen), PDF-/Sheet-Block (→ „[Name]“).
- Code-Absätze behalten keine Auszeichnung. Fußnoten werden `[^n]` + Anhang-Absätze (kein Rücklauf zur Fußnote).
- Sonderzeichen (`* _ # [ ] | \ ` > -`) werden nicht maskiert → Text mit diesen Zeichen kommt nicht heil zurück
  (Zufallstest lässt Markdown bei solchen Modellen aus). Echte Lücke, aber niedrig.
- Leerabsätze entfallen (Leerzeile trennt nur).

## HTML
- Weg: Schriftart, Größe, Farbe, Markierung (Lesen nimmt nur Struktur + b/i/u/s/hoch/tief/Link/Bilder/Tabellen),
  Seitenumbruch, Inhaltsverzeichnis, Fußnoten (→ Nummern + Liste), schwebende Bilder, Kommentare, Änderungen (angenommen),
  Tabellenstil, Leerabsätze, Zeilenabstand; Leerraum wird zusammengefasst, Tab → Leerzeichen.

## RTF / EPUB
- Nur Schreiben (kein Leser). Test prüft: Datei lässt sich öffnen/entpacken und Wörter des Textes stecken drin.

## .notes-Bündel
- Verlustfrei (JSON): Blöcke, Seite, Notizfelder. Datei-Anhänge (PDF/XLSX) nur wenn sie in `data/pdfs|sheets` liegen.

## Notizen ⇄ Markdown
- Platzhalter (Bilder/Tabellen in Notizen, U+FFFC) werden in Markdown nicht getestet; Rundlauf nur für Text-Notizen:
  fett/kursiv/durchgestrichen, ☐/☑, Listen. Unterstrichen und Schrift (außer Mono) gehen verloren.
