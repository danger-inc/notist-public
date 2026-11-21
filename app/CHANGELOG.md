# notist – Änderungen

## 5.3.1 (2026-11-20)
- **Kursordner aus studist**: Ein Klick auf einen Kurstitel in studist öffnet notist mit dem passenden Ordner, schon aufgeklappt (`notist --folder words:Ordner` geht auch von Hand).

## 5.3.0 (2026-11-19)
- **Gemeinsam bearbeiten – so einfach wie möglich**: Der Knopf „gemeinsam“ sitzt jetzt oben neben „öffnen“, Anmelden geht mit einem großen, eindeutigen Knopf. Deine musicalist-Freunde stehen beim Einladen gleich zum Antippen da. Eine Einladung erscheint als Fenster mit „Beitreten“ – auch direkt ins gerade offene Dokument (eine Version davor bleibt im Verlauf).
- **Sofort sichtbar, mit wem du schreibst**: Über dem Dokument zeigt eine Leiste „● Live“ und alle Beteiligten mit ihrer Farbe. Wo die anderen gerade schreiben, steht eine Cursor-Linie mit Namen; was sie markieren, ist in ihrer Farbe hinterlegt – am PC und am Handy, überall dieselbe Farbe pro Person.
- **Verbindung bleibt**: Eine freigegebene Verbindung läuft weiter, auch wenn das Dokument zu ist (Änderungen landen dann im gespeicherten Eintrag), und endet nur, wenn du oder die Einladende sie trennt – mit klarer Warnung, was dann passiert. Der neueste Stand liegt immer verschlüsselt auf dem Server, auch nach einem Neustart geht nichts verloren.
- **Bereiche wie Modi**: Alt+1/2/3 und die Reiter oben zeigen jetzt immer die Liste aller Einträge des Bereichs, statt die zuletzt offene Datei zu öffnen. Von dort öffnest du, was du brauchst.
- **LaTeX ohne Ruckeln**: Die Vorschau rendert im Hintergrund (die sichtbare Seite zuerst), und beim Öffnen wird nur kompiliert, wenn sich seit dem letzten PDF etwas geändert hat. Vorher konnte das Öffnen bis zu 2,5 Sekunden hängen.

## 5.2.0 (2026-11-18)
- **Gemeinsam bearbeiten (neu)**: Notizen, Words-Dokumente und LaTeX live zusammen bearbeiten – mit Freunden oder zwischen den eigenen Geräten (PC, Mac, Handy). Unten auf „gemeinsam“ (Handy: Menü → „Gemeinsam bearbeiten …“) mit dem musicalist-Konto anmelden (gleicher Name, gleiches Passwort) und Namen einladen; leer lassen heißt: nur die eigenen Geräte. Eine Einladung wird erst nach Freigabe aktiv („wartet auf Freigabe“). Danach kommen Änderungen sofort bei allen an, gleichzeitiges Tippen an verschiedenen Stellen geht, und farbig markiert sieht man, wo die anderen gerade schreiben. LaTeX kompiliert weiterhin jedes Gerät selbst. Für alles andere in notist braucht es kein Konto. Alles ist Ende-zu-Ende verschlüsselt – auch der Server kann nichts lesen: Eingeladene bekommen von dir einen Sitzungs-Code (wird beim Einladen kopiert, z. B. per WhatsApp weitergeben) und tippen ihn einmal beim Öffnen ein; deine eigenen Geräte brauchen keinen. Ändern zwei Leute gleichzeitig verschiedene Zellen einer Tabelle, bleiben beide Änderungen erhalten. Vor jeder gemeinsamen Sitzung legt notist eine Version im Verlauf an, und bei „Änderungen verfolgen“ steht, wer was geändert hat (auch in exportierten DOCX-Dateien).
- **Zoom in „fließend“**: Die fließende Ansicht hat jetzt ihren eigenen Zoom und lässt „Seitenbreite“ der Seitenansicht in Ruhe. Strg+Mausrad und Touchpad zoomen weich statt ruckelnd. Tabellen und Tabellen-Blöcke wachsen beim Zoomen mit (auch in der Seitenansicht).
- **Alle Einträge eines Bereichs**: Ein zweiter Klick auf den offenen Bereich oben (¹ notizen, ² words, ³ latex) oder Alt+1/2/3 ein zweites Mal öffnet die Übersicht mit allen Einträgen dieses Bereichs.
- **Löschen fragt nach**: Vor dem Papierkorb kommt jetzt „wirklich löschen?“ (auch am Handy). Die Frage, ob eine Datei außerhalb von notist mitgelöscht werden soll, erscheint im notist-Stil.
- **LaTeX-Vorschau**: lässt sich im Vollbild öffnen (󰊓 unter der Vorschau, Esc oder F11 beendet) oder ganz ausblenden (󰈙 in der Werkzeugleiste) – kompiliert wird trotzdem.
- **Abgleich ohne lästige Konflikte**: Bisher hat jedes Gerät das bloße Abspeichern eines empfangenen Stands als eigene Änderung gezählt. Dadurch entstanden bei fast jeder Bearbeitung „(konflikt)“-Kopien, teils Kopien von Kopien. Das ist behoben. Stehen auf beiden Seiten derselbe Titel und Text, gibt es keine Kopie mehr.
- **Handy**: „[] “ bzw. „[x] “ am Zeilenanfang wird in Notizen und Words zum Kästchen ☐/☑, Antippen hakt ab. Die Leisten unten und die Knöpfe auf der Startseite sehen jetzt aus wie am PC; scrollende Leisten blenden am Rand aus, statt Knöpfe abzuschneiden. Die Startseite zeigt neue und abgeglichene Einträge sofort. Neu ist ein Update-Knopf auf der Startseite (und in den Einstellungen): notist sucht neue Versionen und installiert sie direkt.

## 5.1.0 (2026-11-14)
- **Neue Handy-App 1.0 (Android)**: Notizen, Words und LaTeX auf dem Handy mit demselben Kern wie am PC – Formatierung, Tabellen, Bilder, Fußnoten, Kommentare, Änderungen verfolgen, PDF-/Tabellen-Blöcke, Rechtschreibung, Übersetzer, Verlauf, Erinnerungen, Sicherung, Export in alle Formate, 9 Designs und Englisch. Gekoppelt wird wie zwischen Rechnern: Einstellungen → Geräte → „Koppeln“, Code in der App eintippen.
- **LaTeX am Handy**: Das Handy lässt am gekoppelten Rechner bauen und zeigt PDF, Fehlerliste und die Sprünge Quelle ↔ PDF (SyncTeX). Dafür versteht der Abgleich jetzt die Anfragen „kompilieren“, „Zeile → PDF“ und „PDF → Zeile“.
- **Altes Verfahren für die Handy-App 0.1.0 entfernt**: Die alte Handy-App muss neu gekoppelt werden (ihre Daten bleiben beim Update erhalten).
- **Intern**: GTK-freie Handy-Module im Kern (mobile.py, spellmob.py, backupcore.py), Abgleich-Erweiterungen für zusätzliche Anfragen.

## 5.0.0 (2026-11-14)
- **notist für macOS (neu, experimentell)**: `./install-mac.sh` richtet notist auf einem Apple-Silicon-Mac ein (Homebrew-GTK, eigenes `notist.app` in ~/Applications, Wörterbücher de/en). Auf dem Mac gilt ⌘ statt Strg (⌘1–3 wechseln Notizen/Words/LaTeX, ⌘Q beendet, ⌘W schließt den Reiter), es gibt eine Menüleiste, Hell/Dunkel folgt dem System, Erinnerungen laufen über launchd (Klick auf die Meldung öffnet den Eintrag, mit terminal-notifier), auf Wunsch Start bei der Anmeldung, der Papierkorb ist der Finder-Papierkorb, LaTeX geht mit Tectonic, MacTeX oder Homebrew. CSV-Tabellen lassen sich ohne Gnumeric öffnen. Auf dem Mac fehlen bewusst die Nachbar-Apps (deren Knöpfe bleiben unsichtbar) und der Glas-Effekt. Getestet wurde bisher nur unter Linux (Plattform vorgetäuscht); ein echter Lauf auf dem Mac steht noch aus.
- **Gemeinsamer Kern**: Speicher, Formate, Teilen, Abgleich und LaTeX-Daten liegen jetzt in einem GTK-freien Kern (core/), der auf PC, Mac und später im Handy läuft. Die Plattform-Unterschiede stehen an einer Stelle (core/plat.py).
- **Abgleich zwischen Rechnern** (aus 4.31): PC↔PC/Mac, mit Quittung, Anhängen und Zähler statt Uhrzeit. Die Handy-App 0.1.0 gleicht weiter nach dem alten Verfahren ab.
- **Kleinigkeiten**: Zoom in Words ruhiger (4.30), UTF-8 überall, Rundlauf-Test über 526 Dokumentmodelle ohne Abweichung.

## 4.31.0 (2026-11-14)
- **Abgleich zwischen Rechnern (neu)**: Mehrere notist-Rechner lassen sich koppeln – Einstellungen → Geräte → „Mit einem anderen Rechner koppeln“ (Adresse und Code eintippen; am anderen Rechner „Gerät hierher koppeln“ drücken). Die Suche im Netz findet Rechner auch selbst. Notizen und Words-Dokumente werden dann automatisch abgeglichen, standardmäßig alle 10 Minuten und beim Wechsel in notist. Intervall, Entkoppeln und Abgleich von Hand gibt es auf der gleichen Seite.
- **Anhänge und LaTeX mit abgleichen**: PDF- und Tabellen-Anhänge sowie LaTeX-Projektdateien kommen beim Abgleich mit. Große Dateien werden in Teilen übertragen und nach einem Abbruch dort fortgesetzt, wo sie aufgehört haben.
- **Nichts geht bei Verbindungsabbruch verloren**: Ein Eintrag gilt erst als abgeglichen, wenn die Gegenstelle den Empfang bestätigt hat. Löschungen werden genauso gesichert.
- **Konflikte ohne Uhrzeit**: Welche Fassung neuer ist, entscheidet ein Zähler je Eintrag statt der Uhrzeit des Rechners. Eine falsch gestellte Uhr bringt also keine alten Stände mehr nach vorn. Bei echtem Konflikt bleibt die andere Fassung als Kopie „(konflikt)“ erhalten.
- **Handy**: Die Handy-App 0.1.0 gleicht weiter nach dem bisherigen Verfahren ab; der neue Abgleich zwischen Rechnern ersetzt das nicht. Die neue Handy-App folgt.
- **Ruhiger Start**: Das Vergleichen der Einträge wird zwischengespeichert, deshalb ist ein erneuter Abgleich deutlich schneller.

## 4.30.0 (2026-11-14)
- **Zoom in Words und PDF ruhiger**: Strg+Mausrad und Touchpad-Gesten zoomen gleichmäßig, ohne hin und her zu springen. Die Stelle unter dem Zeiger bzw. zwischen den Fingern bleibt stehen, auch bei Knöpfen, Regler und Strg+±. Beim Zoomen gleitet die Seite weich mit; die scharfe Darstellung kommt nach einem kurzen Moment der Ruhe.
- **Datensicherheit**: Änderungen, die während des Speicherns im Hintergrund noch liefen, gehen nicht mehr verloren. Wiederherstellen einer Sicherung, Umbenennen und Verschieben während des Speicherns sind abgesichert. Erinnerungen melden sich nicht mehr für gelöschte Einträge.
- **Dateien und Sicherungen**: Zwei neue Einträge mit gleichem Titel bekommen unterschiedliche Dateien. Anhänge (PDF, Tabellen) werden beim Teilen nicht mehr überschrieben. Sicherungen enthalten jetzt auch den Dateiordner; ein Wiederherstellen holt fehlende Dateien zurück.
- **Kaputte Dateien**: Eine beschädigte Notiz wird nicht mehr stillschweigend übersprungen, sondern in den Ordner „kaputt“ verschoben, mit Hinweis.
- **Umlaute und Sonderzeichen**: Alle Dateien werden einheitlich als UTF-8 gelesen und geschrieben. Das betrifft vor allem Systeme mit anderer Spracheinstellung.
- **Export und Import**: Zeilenabstand bleibt beim Speichern als ODT stabil (kein Anwachsen mehr). Zitate, Seitenumbrüche vor Tabellen und Listen bleiben erhalten. HTML-Dateien mit Doctype, Tabellen, Links und Bildern werden vollständig gelesen. Markdown: Leerzeilen erzeugen keine doppelten Absätze mehr; verschachtelte Auszeichnung wie ***fett kursiv*** wird richtig erkannt.
- **Fix**: Export nach Markdown, HTML, Text, RTF und EPUB stürzte bei eingebetteten PDFs ab. Das ist behoben.
- **Fehlermeldungen**: Fehler bei Sicherung und Übersetzung wurden nicht angezeigt; jetzt erscheinen sie.
- **Englische Oberfläche**: Einige Texte (Energiesparmodus, Wechsel-Animation, Handy-Kopplung, Update-Suche) sind jetzt übersetzt.

## 4.29.0 (2026-11-09)
- **/sheet – Tabellen einfügen**: Im Words-Dokument (auch „fließend“) fügt `/sheet` eine Tabelle (XLSX; XLS/ODS/CSV werden mit Gnumerics ssconvert umgewandelt) als Karte ein – wie bei `/pdf`. Die Datei liegt im notist-Ordner (data/sheets), gleiche Dateien nur einmal.
- Die Karte zeigt Blattanzahl, Größe und auf Knopfdruck eine **Vorschau** (Blätter umschaltbar, Zahlen rechtsbündig, Datumswerte als Datum, Formeln mit ihrem berechneten Wert). Weitere Knöpfe: in **Gnumeric öffnen**, das Blatt als **echte Words-Tabelle einfügen**, Kopie speichern, umbenennen, entfernen.
- Export (DOCX, PDF, HTML, Markdown, ODT, RTF, EPUB, LaTeX) und Teilen als .notes-Datei nehmen die Tabelle mit; Sicherungen holen fehlende PDF-/Tabellen-Anhänge zurück.

## 4.28.0 (2026-11-07)
- **Handy-App**: notist gibt es jetzt auch fürs Handy. Notizen und Words-Dokumente werden im WLAN in beide Richtungen abgeglichen – gekoppelt wird wie bei musicalist: Einstellungen → Handy → „Handy koppeln“, Code in der App eintippen. Verschlüsselt, nur gekoppelte Geräte, Port 37527/tcp.
- Ändern PC und Handy denselben Eintrag, bleibt der neuere Stand und der andere als Kopie „(konflikt)“ – es geht nichts verloren. Vom Handy überschriebene Stände landen vorher im Versionsverlauf.
- Neue Einträge vom Handy bekommen wie gewohnt ihre Datei im notist-Ordner (.md / .docx); außerhalb geänderte Dateien werden vor dem Abgleich frisch eingelesen. LaTeX bleibt am PC.

## 4.27.0 (2026-11-05)
- **PDF-Ansicht gestochen scharf**: Gerendert wird jetzt mit dem echten Skalierungsfaktor (z. B. 1,5) in ganzen Geräte-Pixeln, ohne das frühere Auf-2-Runden und weiche Herunterrechnen.
- **Suche in der PDF** (Strg+F in der PDF, „suchen“): Treffer auf allen Seiten markiert, „3 / 12“, Enter/Umschalt+Enter springt.
- **Seitenanzeige „3 / 18“** schwebt mit; **Zoom, Seite, Lesemodus und Seitenmodus werden je PDF gemerkt**. Neu: „breite“, „ganze seite“.
- **Lesemodus**: dunkles, ans Thema getöntes Papier mit heller Schrift und dunklem Block-Rahmen; farbige Abbildungen und Schrift behalten ihre Farben.
- **Werkzeugleiste nur noch mit Symbolen** im Stil der Words-Leiste; ein Klick auf die Prozentzahl setzt auf Seitenbreite zurück. Zwei Seiten nutzen mehr Breite als eine.
- **Fix**: Beim Klick in eine PDF (z. B. Suche) erschien ein riesiger farbiger Balken – der Text-Cursor des Dokuments, der auf der Blockzeile saß, ist jetzt ausgeblendet, solange der Fokus in der PDF liegt.
- **Markieren & Anmerken**: Markierter Text → gelb/grün/blau/rosa/unterstrichen (bleibt im Dokument), „als zitat“ setzt den Text mit Seitenzahl unter die PDF. Rechtsklick auf eine Markierung entfernt sie.
- **Zwei Seiten nebeneinander** und **Vollbild** (Esc beendet, Bild↑/↓ blättert).
- **Links in der PDF** sind klickbar (Webadressen, Sprünge innerhalb der PDF).

## 4.26.0 (2026-11-03)
- **Eingebettete PDFs (Words, auch „fließend“)**: Aufgeklappte PDFs lassen sich jetzt zoomen (Pinch auf der PDF, Strg+Mausrad, Knöpfe − / % / + neben „ausblenden“); der Zoom gilt nur für die PDF, nicht fürs Dokument. Ist sie breiter als der Block (Zoom oder halbes Fenster), wischt man waagerecht darin; das 2-Finger-Zurück bleibt dabei aus dem Weg.
- **Text markieren und kopieren**: Ziehen markiert, Doppelklick ein Wort, Dreifachklick die Zeile; Strg+C, Rechtsklick (Kopieren / Alles auswählen) oder Mittelklick-Ablage.

## 4.25.0 (2026-11-01)
- **Scroll-Ende**: Wer am Ende einer Seite weiterscrollt, sieht aus der Kante einen Verlauf aus ░ ▒ ▓ █ aufsteigen, am Mauszeiger am höchsten. Die Liste bewegt sich dabei nicht und der Effekt läuft ohne Überschwingen aus. Er erscheint nur, wenn kein umgebendes Scroll-Fenster mehr weiterscrollen kann. Abschalten: `"scroll_end": false` in ~/.config/rice-apps/settings.json oder Energiesparmodus.

## 4.24.0 (2026-11-01)
- **Seitenumbrüche hängen nicht mehr vom Zoom ab**: Bilder landeten je nach Zoomstufe auf Seite 3 oder 4. Ursachen: Waagerechte Linien hatten feste Abstände und Tabulatoren feste Breite (beide wuchsen nicht mit dem Zoom), und Rundungen von ±1–2 px entschieden bei Grenzfällen anders. Linien und Tabs skalieren jetzt mit; beim reinen Zoomen bleiben die Seitenumbrüche exakt erhalten (neu berechnet wird erst nach einer Änderung am Text oder an der Seite).

## 4.23.2 (2026-11-01)
- **Pinch-Zoom: Ansicht und Scrollleiste springen nicht mehr** (v. a. beim Rauszoomen): Die Textstelle bleibt auch beim späteren Neuberechnen der Seiten und beim Scharfsetzen der Bilder festgehalten; das Scharfsetzen läuft hinter einem Standbild. Seitenabstände oberhalb der Ansicht schieben die Ansicht gleich mit.

## 4.23.1 (2026-11-01)
- **Pinch-Zoom flüssig**: Bilder wurden bei jedem Schritt neu dekodiert (bis 1 s pro Schritt bei großen Bildern). Jetzt werden sie währenddessen grob aus dem Vorhandenen skaliert und nach dem Loslassen wieder scharf gesetzt; Schritte dauern ~40 statt 250–1000 ms.

## 4.23.0 (2026-11-01)
- **Pinch-Zoom in Words** (Touchscreen und Touchpad): Zoom folgt den Fingern stufenlos von 30 bis 300 %, die Ansicht bleibt an derselben Textstelle; schaltet „an Fensterbreite anpassen“ aus wie der Zoom-Regler.

## 4.22.0 (2026-11-01)
- **Zeilenumbruch ohne Sprung**: Nach Enter am Seitenende stand die neue Zeile ~0,4 s auf der falschen Seite und sprang dann hinterher. Der Seitenumbruch wird jetzt sofort neu gerechnet.
- **Strg+Tab macht exakt dort weiter**, wo man aufgehört hat (Cursor und Bildausschnitt, auch nach Neustart); die Stelle wird nachgeführt, bis das Layout steht, und der Cursor ist gleich aktiv.
- **Strg+Z in Notizen springt nicht mehr** (Standbild wie in Words, der neu aufgebaute Text scheint nicht mehr durch das Standbild – das war das kurze Hoch-und-Runter); das Mitscrollen funkt beim Rückgängig nicht mehr dazwischen.
- **Rechtsklick auf ein Bild** öffnet dieselben Bildeinstellungen wie der Linksklick (Words und Notizen).
- **Vollbild (F11)**: nur Dokument und Werkzeugleiste; Esc oder F11 beendet es.

## 4.21.2 (2026-10-29)
- **PDF und Drucken stimmen jetzt mit dem Dokument überein**: Mehrere Bilder in einem Absatz standen im PDF/Ausdruck untereinander (und rissen große Lücken); jetzt stehen sie wie im Editor nebeneinander und brechen bei Platzmangel um. Angehängte PDFs fehlten im Export und Ausdruck komplett – jetzt kommt jede Seite des Anhangs auf eine eigene Seite.
- **Layout wie im Editor**: Text hinter einem Bild (z. B. die Linien „––––“) steht in derselben Zeile auf der Unterkante des Bildes; Leerzeichen zwischen Bildern bleiben als Abstand erhalten; Zeilenhöhe, Absatz- und Überschriftenabstände, Tabstopps (alle 8 Leerzeichen), Linien und Glyphenbreiten entsprechen der Seitenansicht. Das Quiz hat im PDF jetzt dieselben fünf Seiten und Seitenumbrüche wie im Editor.
- **Drucken im Teilen-Menü** (Notizen und Words); Notizen lassen sich nun ebenfalls drucken.

## 4.21.1 (2026-10-28)
- **Strg+Z springt nicht mehr**: Beim Rückgängig baut notist die Seite neu auf, und für einzelne Bilder fiel die Dokumenthöhe kurz zusammen (z. B. 7174 → 1663 px), sodass die Ansicht für ein, zwei Bilder ganz woanders stand. Jetzt bleibt währenddessen ein Standbild der Seite stehen, und die Ansicht wird erst verschoben, wenn das Layout steht.
- **.docx öffnen**: Enthält die Datei Textfelder, Diagramme, SmartArt, Formeln oder Formen, sagt notist beim Öffnen, dass diese nicht übernommen werden.
- **Große Bilder** werden beim Start im Hintergrund vordekodiert; das erste Öffnen eines Dokuments mit vielen Bildern blockiert dadurch weniger.

## 4.21.0 (2026-10-28)
- **Strg+Z ohne Springen**: Rückgängig/Wiederholen hält die Ansicht an derselben Stelle (Notizen und Words). Vorher sprang der Bildschirm kurz nach oben/unten, weil beim Neuaufbau die Seitenabstände fehlten und das Mitscrollen dazwischenfunkte. Bilder werden dabei nicht mehr jedes Mal neu dekodiert (spürbar schneller bei Dokumenten mit großen Bildern).
- **Strg+Z überall ein Schritt**: „Formatierung löschen“ (Zeichen- und Absatzformat) und „Fußnote einfügen“ brauchten zwei Schritte – jetzt je einer. Geprüft für Tippen, Fett, Farbe, Schrift, Größe, Überschriften, Listen, Ausrichtung, Abstand, Tabellen, Fußnoten, Linie, Seitenumbruch, Inhaltsverzeichnis, Bilder (einfügen, Größe, schweben, verschieben, löschen), Markdown und in Notizen Text, Format, Checkliste, Bild, Tabelle, Löschen.
- **Bilder komprimieren** ist jetzt standardmäßig auf „Mittel“ und zeigt beim Einfügen, wie viel gespart wurde. „Jetzt anwenden“ hat ein „Rückgängig“ im Hinweis.
- **Speichern im Hintergrund**: Die Datei (.docx/.odt) wird bei großen Dokumenten in einem eigenen Thread geschrieben – kein Anhalten mehr beim Tippen.
- **Willkommens-Eintrag** beim ersten Start (Kürzel, Words-Tipps; löschbar) und zwei einmalige Tipps (Bild anklicken, Strg+Tab).
- **Englisch**: alle neuen Texte (Bild-Menü, Komprimierung, Hinweise) und ~90 bisher fehlende Beschriftungen sind übersetzt.
- **Barrierefreiheit**: Knöpfe, die nur ein Symbol zeigen, bekommen ihren Tooltip als Beschriftung für Screenreader.
- Die Scrollleiste neben dem Papier sieht aus wie die übrigen und verschwindet, wenn nichts zu scrollen ist.

## 4.20.0 (2026-10-28)
- **Strg+Tab**: springt zur zuletzt geöffneten Datei (egal ob Notiz, Words oder LaTeX); nochmal drücken springt zurück. Strg+Umschalt+Tab macht dasselbe. Es öffnet sich nichts darüber – der Wechsel passiert direkt. Auf Home öffnet es die zuletzt benutzte Datei; die Liste bleibt auch nach einem Neustart erhalten.
- **Zoom in Words**: Papier und Schrift wachsen jetzt gemeinsam. Vorher wurde das Papier an die Fensterbreite geklemmt, die Schrift aber nicht mitgenommen – Zeilenumbrüche und Seitenlänge wichen dadurch vom Druck ab. Jetzt brechen die Zeilen bei jedem Zoom an derselben Stelle um.
  - Ist das Papier breiter als das Fenster, lässt sich waagerecht scrollen.
  - „Seitenbreite“ ist ein Modus: Der Zoom folgt der Fensterbreite, bis du selbst zoomst.
  - Absatzabstände und Überschriften-Abstände skalieren mit.

## 4.19.1 (2026-10-28)
- **Cursor-Spur flüssig**: Der animierte Textcursor wurde als Cairo-Fläche über das ganze Fenster neu gezeichnet (bei großen Fenstern ~15–30 fps). Er ist jetzt ein kleiner GPU-Pfad – volle Bildrate, auch beim Tippen mit Spur. Gilt für alle -ist-Apps (gemeinsames glass.py).
- **Bild-Menü**: Verschwindet beim Scrollen und beim Klick daneben (und mit Esc); Klicks im Menü selbst zählten vorher teils als Klick im Text.

## 4.19.0 (2026-10-28)
- **Bilder in Words anfassen**: Ein angeklicktes Bild hat Ziehgriffe an den vier Ecken – an einer Ecke ziehen ändert die Größe (Seitenverhältnis bleibt).
- **Schwebende Bilder**: Im Bild-Menü gibt es „im Text“, „vor Text“ und „hinter Text“. Vor/hinter dem Text lässt sich das Bild mit der Maus frei auf der Seite verschieben (auch über den Text), an den Ecken skalieren, links/mittig/rechts ausrichten, mit Entf/Rück entfernen und mit Esc abwählen. Hinter dem Text liegende Bilder fasst man dort an, wo kein Text steht. Beim Speichern als .docx werden sie als frei positionierte Bilder (vor/hinter dem Text, ohne Umfluss) geschrieben und beim Öffnen wieder erkannt.
- **Bilder komprimieren** (Einstellungen → Words): Stufen Aus / Leicht / Mittel / Stark verkleinern neu eingefügte Bilder (Einfügen, Ziehen, Zwischenablage). „Jetzt anwenden“ komprimiert auch alle vorhandenen Bilder in Words-Dokumenten (vorher wird eine Version im Verlauf gesichert).

## 4.18.0 (2026-10-28)
- **Words mit vielen Bildern flüssig**: Bisher fror notist bei jeder Tipp-Pause für ein bis zwei Sekunden ein (Cursor ruckelte, Löschen stockte), sobald ein Dokument große Bilder enthielt. Ursachen behoben:
  - Speichern kodiert die Bilder nur noch einmal (vorher bei jedem Speichern komplett neu, im langsamen Python-Pfad, zweimal) – 140 ms → 7 ms.
  - Die Datei (.docx/.odt) wird bei Dokumenten mit Bildern erst nach 4 s Tipp-Pause geschrieben (und sicher beim Wechseln/Beenden); Bilder darin werden nicht mehr nutzlos „komprimiert“.
  - Die Wörter-/Seitenanzeige und die Seitenberechnung laufen erst in der Tipp-Pause statt bei jedem Zeichen.
  - Schriftformat-Tags werden nicht mehr bei jedem Zeichen neu durchsucht.
- **Weniger Speicher**: Nach dem Speichern gibt notist freien Arbeitsspeicher ans System zurück (große Dokumente ließen den Prozess sonst auf über 1 GB anwachsen). Der Versionsverlauf behält bei sehr großen Dokumenten weniger Versionen (vorher bis zu 60 × 16 MB).

## 4.17.0 (2026-10-27)
- **Wechsel-Animation**: Der Wechsel zwischen Hell und Dunkel (und zwischen Designs) läuft als Scanbalken über den ganzen Bildschirm. Alle Fenster, die Leiste und das Terminal wechseln darunter im selben Moment, hinter dem Balken steht das neue Design. An/aus und Dauer (Standard 1,5 s) stehen in der Designauswahl der Einstellungen.

## 4.16.1 (2026-10-27)
- **„/link“** im Fließend-Menü: öffnet das Link-Fenster direkt am Cursor; steht eine Adresse in der Zwischenablage, ist sie schon eingetragen. Ist sie da, steht der Cursor gleich im „angezeigten Text“ und Enter fügt ein; sonst springt Enter aus der Adresse dorthin. Das Fenster ist im Explorer-Look.
- **Cursor flüssiger**: Die animierte Cursor-Spur fragt die Position jetzt in jedem Bild ab (vorher alle 40 ms) – er hinkt beim Wechsel zwischen Notizen/Words (Alt+1/Alt+2) nicht mehr hinterher.

## 4.16.0 (2026-10-27)
- **PDF in Words**: Einfügen → „PDF“ (oder „pdf“ im Fließend-Menü) legt die Datei sauber im notist-Ordner (data/pdfs) ab und zeigt im Dokument eine Karte mit Vorschau der ersten Seite. Knöpfe: **hier ansehen** (alle Seiten erst auf Klick in notist), **scourge-pdf** (öffnen/bearbeiten), **speichern unter**, Entfernen. Beim Teilen als .notes-Datei und in Backups ist die PDF enthalten. Nach dem Einfügen fragt notist, ob das **Original in den Papierkorb** soll, damit die Datei nicht doppelt liegt.
- **„DE“-Knopf** in der Statusleiste sitzt jetzt direkt bei den Knöpfen rechts.

## 4.15.1 (2026-10-26)
- **Tabellen in Notizen**: Neuer Knopf „Tabelle“ in der Notizen-Leiste (Größe wie in Words per Raster wählen). Die Tabelle steht mitten im Text, hat Zeilen/Spalten +/−, Design und Tab/Pfeile in den Zellen; sie wird mit der Notiz gespeichert und als Markdown-Tabelle exportiert (und von Markdown wieder als Tabelle erkannt).
- **Tabellen-Design**: Die Leiste oben (+ zeile, + spalte …) ist an den -ist-Look angepasst. Die Design-Fläche liegt jetzt **rechts neben der Tabelle** (bei schmalem Fenster darunter) und verdeckt nichts mehr; die Tabelle wird dafür schmaler. Schließen mit „design“, ✕ oder Esc.
- **Tab bei Markierung**: Markierter Text wird nicht mehr gelöscht, sondern eingerückt – auch über mehrere Zeilen (Umschalt+Tab rückt aus). In Notizen und Words.
- **Ubuntu**: Die Seitenleiste lässt sich wieder weit nach rechts ziehen (die Mindestbreite des Editors bremste den Trenner).

## 4.15.0 (2026-10-26)
- **Design für alle Apps**: In den Einstellungen gibt es die Designauswahl jetzt in jeder -ist-App; die Wahl gilt für alle Apps zugleich und wirkt sofort in allen offenen Fenstern. Bei „Automatisch“ (Desktop-Farben) lässt sich zwischen **Dunkel** und **Hell** umschalten.
- **Words „fließend“**: Das „+“ links neben der Zeile wird nicht mehr als Schriftzeichen, sondern als Vektor gezeichnet – unter Windows (und überall, wo die Icon-Schrift fehlt) erscheint es jetzt richtig.

## 4.14.2 (2026-10-25)
- **Windows**: Speichern brach bei Zeichen wie „☑“ oder manchen Umlauten mit einem Zeichensatz-Fehler ab; Textdateien
  werden dort jetzt immer als UTF-8 gelesen und geschrieben.
- **Windows**: Der Glas-Schalter funktioniert wieder.

## 4.14.1 (2026-10-25)
- **Update-Knopf**: Neben der Versionsnummer steht „󰑐“ – Klick sucht sofort nach einem Update. Gibt es eine neuere
  Version, wird daraus „󰚰 update“; ein Klick lädt und installiert sie (Linux und Windows), danach heißt er „󰑓 neu starten“.
- **Rückmeldung bei Umschalt-Knöpfen**: „An“ (z. B. „Ton behalten“) ist jetzt auch unter dem Mauszeiger zu sehen,
  Drücken färbt sofort – man muss die Maus nicht mehr wegbewegen, um zu sehen, ob der Klick angekommen ist.
- **2 Finger auch vorwärts**: Nach einem Zurück-Wischen bringt das Wischen in die andere Richtung zur verlassenen
  Seite zurück.

## 4.14.0 (2026-10-25)
- **Words: mehr Funktionen im Menüband** – neuer Reiter **Überprüfen** (Kommentare, Änderungen verfolgen, Sprache,
  Wörter zählen). Layout hat jetzt **Zeilennummern** (fortlaufend oder je Seite neu, jede n-te Zeile), **Wasserzeichen**,
  **Seitenfarbe** und **Seitenrahmen** – sichtbar in der Seitenansicht, im PDF und beim Drucken (Zeilennummern und
  Rahmen auch in DOCX). Start: **Aa** ändert die Groß-/Kleinschreibung, **󰃣 Format übertragen** kopiert Schrift- und
  Absatzformat auf anderen Text.
- **Kommentare** (Strg+Alt+M) an markiertem Text: Klick auf die gelbe Stelle öffnet den Kommentar, „Alle“ listet sie;
  **Änderungen verfolgen** (Strg+Umschalt+E): Eingefügtes grün, Gelöschtes rot durchgestrichen, annehmen/ablehnen einzeln
  oder alle. Beides wird in DOCX gelesen und geschrieben; die anderen Ausgabeformate zeigen den angenommenen Text.
- **Sprache je Dokument** (Notizen, Words, LaTeX): Knopf **DE/EN** unten in der Leiste. Er steuert Rechtschreibung und
  Anführungszeichen („…“ oder “…”); die Standardsprache für neue Dokumente steht in den Einstellungen.
- **Teilen → Als Datei speichern** mit vielen Formaten: PDF, TXT, DOCX, Markdown, Webseite (angeheftet, Rechtsklick heftet
  an/löst) und darunter ODT, RTF, E-Book (EPUB); bei LaTeX auch .tex und das ganze Projekt als ZIP.
- **LaTeX-Pakete**: neuer Paket-Manager (Knopf 󰏗 / Datei → LaTeX-Pakete): suchen, vorab herunterladen (danach offline),
  Speicherordner öffnen. Die Befehle benutzter und geladener Pakete (z. B. `\linenumbers` aus lineno) kommen
  automatisch in Vorschläge und Befehlsübersicht; „nach befehlen suchen“ liest alle geladenen Pakete ein.
- **LaTeX: Enter übernimmt den markierten Vorschlag** nach `\` (auch per Maus-Hover), statt eine neue Zeile zu beginnen.
- **Strg+F in drei Stufen**: öffnen · erneut (Cursor im Text) springt ins Suchfeld und markiert es · nochmal schließt.
  Neues Aussehen wie die Suche in Code-Editoren (Karte oben rechts), in Notizen, Words und LaTeX.
- **Neuer Look**: Notizliste wie die Dateiliste in filist (flache Zeilen, Pfadleiste darüber), die obere Werkzeugleiste
  in Notizen, Words-Fließend und LaTeX ebenfalls. **Rechtsklick** auf einen Eintrag öffnet dasselbe Menü wie „Mehr“
  (Anheften, Öffnen oben).
- **Behoben**: Words-Fließend springt beim Wechsel Notizen ↔ Words (Alt+1/Alt+2) wieder an die letzte Stelle; Kopieren
  und Einfügen innerhalb von notist behält Überschriften, Listen und Links; die Format-Leiste bei Markierung bleibt beim
  Scrollen am Text; „übersetzer“ sitzt auf einer Linie mit den anderen Knöpfen; Kästchen (☐) und Links wechseln die
  Farbe mit dem Hintergrundbild; kleine weiße Punkte beim Scrollen (Cursor-Griffe) sind aus, außer bei echter Touch-Bedienung.
- **Installation**: notist legt vor jedem Installieren/Aktualisieren eine ZIP-Sicherung der Daten an
  (`~/.local/share/notes/backups/vor-installation-…zip`); Einstellungen werden atomar geschrieben, eine beschädigte
  Einstellungsdatei wird gesichert statt überschrieben.

## 4.13.0 (2026-10-25)
- **Tabs statt Dropdown**: oben in der Mitte stehen jetzt die geöffneten Einträge als Tabs im -ist-Look (wie bei filist):
  ¹²³-Nummern, ✕ zum Schließen (auch Mittelklick/Strg+W), „+“ für neu, Strg+Bild↑/↓ wechselt. Der letzte Tab
  führt zurück auf Home. Die Liste mit Suche (Words, LaTeX, schmales Fenster) öffnet der ≡-Knopf rechts davon (Strg+T).
- **Keine Suchleiste mehr oben**: Strg+F sucht im Eintrag, auf Home (Alt+0) gibt es die Suchleiste über alle Bereiche.
  Die Listensuche („in allen …“, Strg+Umschalt+F) erscheint nur bei Bedarf oben in der Seitenleiste.

## 4.12.0 (2026-10-24)
- **Hover-Übersetzer von linguist**: Ist er in linguist eingeschaltet, zeigt der Knopf „übersetzer ◢“ unten rechts,
  ob er an ist – Klick schaltet ihn an/aus, Rechtsklick öffnet die linguist-Einstellungen, Strg+Umschalt+T zeigt
  die Karte mit dem markierten Text. Ohne linguist (oder mit Hover aus, Standard) bleibt alles wie bisher.

## 4.11.0 (2026-10-22)
- **Übersetzer: Enter übersetzt online**, wenn das Wörterbuch nichts findet oder du einen ganzen Satz eingibst
  (der Knopf zeigt dann „⏎“). Danach kopiert Enter die Online-Übersetzung.
- **Übersetzer: weitere Sprachen** – über den Sprachknopf oben (󰗊 en ▾) lassen sich Wörterbücher für Französisch,
  Spanisch, Italienisch, Niederländisch, Polnisch, Russisch, Japanisch und 14 weitere laden (je ~35 MB, aus
  Wiktionary über WikDict, danach offline). Online-Übersetzung von Sätzen geht in jeder geladenen Sprache.
  Englisch bleibt eingebaut (TU Chemnitz).
- **Übersetzer: Textfeld** – nach einer Suche markiert der erste Klick ins Feld alles, sodass du gleich das nächste
  Wort tippen kannst; ein Doppelklick markiert ebenfalls den ganzen Text. Nach dem Löschen mit ✕ steht der Cursor
  sofort wieder im Feld.
- Der Knopf „übersetzer“ unten rechts ist jetzt genauso hoch wie die anderen Knöpfe der Statusleiste.

## 4.10.0 (2026-10-22)
- **Übersetzer Deutsch ⇄ Englisch**: Unten rechts in der Statusleiste (oder **Strg+Umschalt+T**) öffnet sich ein
  kleines Fenster in der Ecke. Wort eintippen – notist erkennt die Sprache selbst (oder du wählst „de → en“ /
  „en → de“) und zeigt alle Treffer nach Wortart und Bedeutung geordnet, darunter Wendungen und Beispiele.
  Ein Klick auf eine Übersetzung kopiert sie, Enter kopiert die erste. Markierter Text wird beim Öffnen gleich
  übernommen. Das Wörterbuch (TU Chemnitz, frei) lädt notist einmalig (~6 MB), danach geht alles offline.
  Ganze Sätze lassen sich auf Klick online übersetzen.
- **Rechtsklick in allen Listen**: In der Liste, im Aufklapp-Menü, auf Home und in der Zuletzt-Leiste gibt es jetzt
  dasselbe Menü – öffnen, anheften, als Text kopieren, per E-Mail senden, als Datei speichern, im Dateimanager
  zeigen, Pfad kopieren, in Ordner verschieben, löschen (auf dem Touchscreen: lange drücken). Auch die Dateien
  eines LaTeX-Projekts haben eins.
- **Rückfrage beim Löschen fremder Dateien**: Liegt die Datei nicht in notist (z. B. in Downloads), fragt notist
  vorher: nur aus notist entfernen oder die Datei mit in den Papierkorb legen. Rückgängig holt sie zurück.
  LaTeX-Projektdateien landen beim Löschen ebenfalls im Papierkorb statt sofort weg zu sein.
- **Strg+F schließt die Suche wieder**, wenn sie schon offen ist (Notizen, Words, LaTeX).
- **„Speichert …“ hängt nicht mehr**: Ging nach dem Speichern etwas schief (passierte auf Ubuntu), blieb die Anzeige
  ewig auf „Speichert …“, obwohl gespeichert war. Jetzt stimmt sie; echte Fehler zeigt sie als „Nicht gespeichert“
  und schreibt Details nach `~/.cache/notes/fehler.log`.
- **Tabellen**: Über „+ zeile“, „− spalte“ usw. zeigt der Mauszeiger jetzt die Hand statt des Textstrichs.
- **Keine weißen Punkte mehr beim Schreiben**: Nach einem Fingertipp blieben die runden Touch-Griffe am Cursor
  stehen und wanderten beim Tippen mit. Sie verschwinden jetzt, sobald du tippst.

## 4.9.3 (2026-10-22)
- **Absturz beim Löschen einer Tabelle behoben**: Ein Tipp auf den Mülleimer der Tabelle (ebenso beim
  Inhaltsverzeichnis) ließ notist abstürzen. Jetzt verschwindet sie sauber – und Strg+Z holt sie samt Inhalt zurück.

## 4.9.2 (2026-10-22)
- **Tabellengröße direkt wählen**: Beim Einfügen einer Tabelle (Menüband „Einfügen → Tabelle“, in „fließend“ über
  „/“, „+“ oder „einfügen …“) erscheint ein Raster wie in Word – zeigen oder mit dem Finger ziehen markiert die
  Größe, antippen fügt ein. Für größere Tabellen gibt es darunter Felder für Zeilen und Spalten.
- **Spalte wechseln bei offenem Design**: Einfach in eine andere Zelle tippen – „Spalte N“ (Ausrichtung, Breite)
  bezieht sich dann auf diese Spalte, die gerade gewählte Spalte ist umrahmt. Das Design-Fenster liegt dafür jetzt
  unter (oder über) der Tabelle statt auf ihr und wandert mit, wenn die Tabelle wächst.

## 4.9.1 (2026-10-22)
- **Tabellen-Design bleibt beim Antippen offen** (Seiten und fließend): Tippte man eine Einstellung an – vor allem
  per Touchscreen –, verschwand das Fenster, bevor sich etwas ändern ließ. Es schließt jetzt nur noch, wenn du
  neben die Tabelle tippst, nochmal auf „design“ drückst, Esc drückst oder die Tabelle aus dem Bild scrollst.
  Beim Scrollen wandert es mit. Die Leiste „+ zeile … design“ klappt beim Öffnen nicht mehr weg, und der Cursor
  bleibt in der Zelle.
- **Tabellenleiste lässt sich wieder öffnen**: Nach dem Verlassen der Tabelle klappte die Leiste beim erneuten
  Antippen einer Zelle gleich wieder zu. Jetzt erscheint sie sofort, und der Cursor landet in der angetippten Zelle.
- **Design-Fenster deckend** (auch im Glas-Modus) und Tipps hinein werden sicher erkannt – es schließt sich nicht
  mehr, wenn es über normalem Text liegt.

## 4.9.0 (2026-10-22)
- **Strg+F sucht im geöffneten Eintrag**: Die Suchleiste erscheint über dem Text (jetzt auch in Notizen), markiert
  alle Treffer und springt mit Enter/Umschalt+Enter durch. Rechts daneben steht als zweiter Teil
  **„in allen notizen · 3“** – ein Klick (oder **Strg+Umschalt+F**) übernimmt die Suche in die Liste und
  filtert alle Einträge. Gilt genauso für Words und LaTeX.
- **Tabellen-Design repariert**: Der Knopf „design“ öffnete ein Fenster, das sofort wieder verschwand bzw. gar
  nicht zu sehen war. Jetzt bleibt es offen, alle Einstellungen greifen sofort, und danach steht der Cursor
  wieder in der Tabelle.
- **Schlagwörter leichter entfernen**: Jedes Schlagwort hat ein eigenes, abgetrenntes ✕ (vorher klebte es am Text
  und die Chips liefen ineinander). Rücktaste im leeren Feld entfernt das letzte Schlagwort. Lange Namen werden
  gekürzt, die Chips brechen sauber um.
- **Satzanfang groß**: Löschst du den gerade groß gemachten Buchstaben und tippst ihn klein, bleibt er klein.
- **Fließend**: Die kleine Formatleiste über einer Markierung verschwindet, sobald der markierte Text gelöscht
  oder überschrieben wird.

## 4.8.0 (2026-10-22)
- **„Schlagwörter vergeben“ repariert**: Ins Feld ließ sich nichts tippen. Ursache war ein Fehler, der alle
  Aufklapp-Fenster mit Eingabefeldern betraf – deshalb gehen jetzt auch wieder **Links** (Strg+K), **Fußnoten**
  (Text bearbeiten), die Zahlenfelder beim **Tabelle einfügen** und die Seitenränder. Nach dem Schließen landet
  der Cursor wieder im Text.
- **Strg+F im halben Fenster**: In Notizen klappt jetzt die Liste oben auf und der Cursor steht in der Suche
  (vorher landete er in einem unsichtbaren Feld).
- **Words fließend mit eigener Leiste oben**: Fett, Kursiv, Unterstrichen, Durchgestrichen, Überschriften 1–3,
  Aufzählung, Nummerierung, Zitat, Code, Link und „einfügen …“ (Tabelle, Bild, Linie, Inhaltsverzeichnis, Datum,
  Fußnote). Rechts schalten zwei Knöpfe **Autokorrektur** und **Rechtschreibung** direkt um, das Zahnrad hat alle
  Schreibhilfen (Typografie, Satzanfang groß, Markdown, Mitscrollen) und den Zoom. Im schmalen Fenster bricht die
  Leiste in eine zweite Zeile um. Der Link in der Formatleiste und Strg+K funktionieren jetzt auch hier.
- **Tabellen gestalten** (Knopf **„design“** über der Tabelle): Kopfzeile, erste Spalte betont, Streifen,
  Rahmen (Gitter, nur Zeilen, außen, ohne), 8 Farben, Abstand (eng/normal/weit), Ausrichtung und Breite je Spalte.
  Das Design bleibt beim Export nach Word, PDF, HTML und Markdown (Ausrichtung) erhalten und kommt beim Öffnen
  einer Word-Datei zurück.
- **Tabellen bedienen**: Tab/Umschalt+Tab springen durch die Zellen, Tab in der letzten Zelle hängt eine Zeile an,
  Pfeil hoch/runter wechselt die Zeile und verlässt die Tabelle am Rand, Esc springt in den Text darunter.
- **Bilder anklicken**: Ein Klick auf ein Bild markiert es und zeigt eine kleine Leiste – Größe (25–100 %,
  Original), links/mittig/rechts, anderes Bild wählen, kopieren, entfernen. Über „/“ oder „einfügen“ landet ein
  Bild in einer eigenen Zeile statt mitten im Satz.
- „1. “ in einer Aufzählung macht daraus eine Nummerierung (und umgekehrt mit „- “).

## 4.7.0 (2026-10-22)
- **Stelle merken**: Wechselst du zwischen Home, Notizen, Words und LaTeX hin und her, landest du beim Zurückkommen
  wieder genau dort, wo du warst (Cursor und Scrollstand). Öffnest du einen Eintrag anders (Liste, nach Neustart),
  erscheint unten kurz ein Knopf **„zur letzten stelle“**, der nach ein paar Sekunden von selbst verschwindet.
  Beides lässt sich unter Einstellungen → Allgemein abschalten.
- **Markierten Text zählen**: Wörter und Zeichen unten in der Leiste zählen live nur die Markierung mit
  („markiert: 12 von 1.200 Wörtern“) – in Words und Notizen, auch in der Statistik.
- Words fließend: das **„+“** links neben einer Zeile sitzt jetzt mittig auf der Zeile (auch bei Überschriften),
  darüber erscheint ein normaler Mauszeiger statt des Text-Cursors, und im Blockmenü ist der Eintrag unter der Maus
  vorgewählt.
- Der Knopf **seiten/fließend** hat jetzt dieselbe Schrift wie „anheften“ und „löschen“ daneben.

## 4.6.1 (2026-10-21)
- **Rechtsklick im Suite-Look**: Das Kontextmenü in Notizen, Words und LaTeX ist jetzt ein eigenes Menü im Stil
  des Datei-Menüs (Rubriken mit Linie, Symbol links, Kürzel rechts) statt GTKs grauem Standardmenü.
  Bei einem roten Wort stehen die Vorschläge oben, Bearbeiten (rückgängig, ausschneiden, kopieren, einfügen …)
  darunter als Symbolreihe. „Rückgängig“ nutzt notists eigenen Verlauf (inkl. Formatierung).
- Auch die übrigen Rechtsklick-Menüs (z. B. in Suchfeldern) tragen jetzt den Suite-Rahmen.

## 4.6.0 (2026-10-21)
- **Rechtschreibprüfung repariert**: Der Schalter sprang sofort wieder auf „aus“, weil notist eine Bibliothek
  (enchant) brauchte, die fehlen kann. notist nutzt jetzt hunspell direkt – Deutsch und Englisch werden zusammen
  geprüft, jede Sprache lässt sich unter Einstellungen → Rechtschreibung einzeln abschalten.
- **Smarte Korrekturen** in Notizen und Words: nach Leerzeichen oder Satzzeichen wird `SChreibstift` zu
  `Schreibstift`, `hALLO` zu `Hallo`, `Tset` zu `Test`, `schreibstift` zu `Schreibstift` und häufige Tippfehler
  (`teh` → `the`, `nciht` → `nicht`) werden verbessert. **Rücktaste direkt danach** macht die Korrektur rückgängig.
  Eigene Ersetzungen („falsch = richtig“) unter Einstellungen → Rechtschreibung; an/aus auch im Mehr-Menü.

## 4.5.0 (2026-10-21)
- **Words in zwei Ansichten**: oben rechts schaltest du je Dokument zwischen **seiten** (wie Word, mit Papier und
  Menüband) und **fließend** (wie Notion) um. Fließend gibt es keine Seiten, nur eine ruhige Textspalte: „/“ am
  Zeilenanfang öffnet das Blockmenü (Überschriften, Listen, Zitat, Code, Tabelle, Bild, Inhaltsverzeichnis …),
  markierter Text bekommt eine kleine Formatleiste, und „+“ links neben einer Zeile fügt einen Block ein. Datei,
  Export und Drucken bleiben gleich.
- **Ordner überall**: Ordner gibt es jetzt in Notizen, Words und LaTeX – auch verschachtelt („uni/mathe“) und direkt
  auf Home (Knopf „ordner“, aufklappbar, Einträge per Ziehen oder Rechtsklick verschieben). Selbst angelegte Dateien
  liegen im passenden Unterordner von Dokumente/notist. Rechtsklick auf einen Ordner: neu hier, Unterordner,
  umbenennen, auflösen. Das Ordner-Fenster sieht jetzt aus wie der Rest der Suite.
- **Neu überall erreichbar**: „neu“ und „öffnen“ stehen auch in der Leiste am linken Rand und unten neben „neuer
  Ordner“.
- **Kopfleiste im halben Fenster ganz sichtbar** – „neu“, „öffnen“ und die Versionsnummer rücken dort in die
  Leiste links bzw. die Einstellungen.
- **Anheften und Löschen** stehen jetzt oben rechts neben dem Titel. **Teilen** hat einen eigenen Knopf – mit
  „In LaTeX umwandeln“ (Notizen und Words) und „In Words umwandeln“ (Notizen und LaTeX); das Original bleibt.
- **Mehr-Menü mit Optionen**: Markdown beim Tippen, Listen fortsetzen, Typografie („…“, –, …, →), Satzanfang groß,
  Mitscrollen, Rechtschreibung – jeweils mit an/aus. Dazu „Notiz jetzt aufräumen“ (Leerzeichen, Leerzeilen).
- **Mitscrollen beim Schreiben**: die Ansicht folgt dem Cursor sofort, auch direkt nach Enter, und unten ist immer
  eine halbe Seite Luft.
- **Spaltenbreite verstellbar**: Liste und Editor im großen Fenster lassen sich am Trenner ziehen; die Breite bleibt.
- **Home im Vollbild** zeigt so viele Einträge, wie Platz ist (nicht mehr fest zehn).
- **Schlagwörter** repariert und neu gestaltet: Eingabe mit Knopf (Enter oder Komma fügt hinzu, beim Schließen wird
  Getipptes übernommen), Vorschläge aus allen Bereichen, „#wort“ in der Suche findet Schlagwörter, Home zeigt sie an.
- **Erinnerungen** mit Kalender im datist-Look (KW gerade/ungerade, heute markiert).
- Das „keine Farbe“-Zeichen sitzt mittig im Punkt.
- Strg+Entf schiebt nichts mehr in den Papierkorb – im Text löscht es wie gewohnt das nächste Wort.

## 4.4.3 (2026-10-20)
- **Farben nach Wallpaper-Wechsel**: notist blieb manchmal in den alten Farben hängen (Knöpfe, der Chip oben
  links), sobald einmal das Changelog-Fenster offen gewesen war. Behoben – und notist übernimmt neue Farben jetzt
  wie scourge erst, wenn sie vollständig geschrieben sind, auch in selbst gezeichneten Kartentiteln.

## 4.4.2 (2026-10-20)
- **Neues Zurück-Wischen im -ist-Design**: Beim Wischen mit zwei Fingern schiebt sich die vorige Seite als Rahmen vom Rand herein – mit einem echten Bild davon und ihrem Namen im Chip. Ist der Rahmen durchgezogen, führt Loslassen zurück, und die Seite klappt über das ganze Fenster auf.
- Nach dem Zurück-Wischen springt die Seite nicht mehr ein Stück nach oben (der erste Millimeter der Geste scrollte noch mit und lief nach).

## 4.4.1 (2026-10-20)
- `notist --settings` öffnet direkt die Einstellungen (genutzt von scourge → software → suite-apps).
- Die Zuletzt-Leiste schließt jetzt auch, wenn die Maus über den linken Rand aus dem Fenster fährt.
- Ein eigenes App-Icon (in scourge hinterlegt) wird beim Start nicht mehr mit dem Standardlogo überschrieben.

## 4.4.0 (2026-10-20)
- **Dateien direkt bearbeiten**: Wer eine Datei mit notist öffnet (z. B. aus Downloads), bearbeitet genau diese
  Datei – es entsteht keine Kopie mehr, Änderungen landen beim automatischen Speichern direkt im Original. Home ist
  jetzt eine Sammlung von Verknüpfungen; unten im Editor steht, in welcher Datei ein Eintrag liegt. Wird die Datei
  außerhalb geändert, liest notist sie beim nächsten Öffnen neu ein. Vor dem ersten Überschreiben legt notist eine
  Sicherung des Originals an, bei Word/LibreOffice-Dateien fragt es einmal nach.
- **Neue Einträge sind echte Dateien** im Ordner Dokumente/notist (Notizen als .md, Words als .docx, LaTeX als
  Ordner mit main.tex); der Dateiname folgt dem Titel. Dateien, die du dort hineinlegst, erscheinen automatisch.
  Ordner, Abschalten und „ältere Einträge als Dateien ablegen“ unter Einstellungen → Dateien & datist.
- **Passender Bereich beim Öffnen**: .tex → LaTeX, .docx/.odt/.doc → Words, kurze .txt/.md → Notizen; bei langen
  Textdateien fragt notist, ob Notiz oder Words. Der Öffnen-Dialog zeigt alle Formate auf einmal.
- **Erinnerungen in datist**: jede Erinnerung erscheint dort als Termin „󰂚 Titel“ – Kalender (lokal oder Google)
  wählbar; „öffnen“ im Termin springt zurück zum Eintrag.
- **Zuletzt-Leiste anheften**: Klick auf den „notist“-Chip oben links heftet die Leiste als eigene Spalte an (der
  Inhalt rückt zur Seite, nichts wird verdeckt); nochmal klicken blendet sie aus. Home bleibt unter ⁰ bzw. Alt+0.

## 4.3.0 (2026-10-20)
- **Zuletzt-Leiste**: Fährt die Maus an den linken Fensterrand, gleitet eine Liste der zuletzt benutzten Einträge
  herein – immer nur aus dem oben gewählten Bereich (Notizen, Words oder LaTeX), auf Home aus allen drei.
  Klick öffnet, Esc oder Wegfahren schließt.
- **Zurück wischen**: Zwei Finger nach rechts auf dem Touchpad (oder die Zurück-Taste der Maus) gehen einen Schritt
  zurück – durch die zuletzt geöffneten Einträge, am Ende landest du auf Home.
- **Markdown**: `**fett**`, `*kursiv*`, `~~durch~~` und `` `code` `` werden beim Tippen sofort formatiert, `[ ] ` wird
  zur Checkliste; in Words zusätzlich `# ` Überschrift, `- ` / `1. ` Liste und `> ` Zitat. Eingefügtes Markdown
  kommt formatiert an, `.md`-Dateien öffnen Notizen mit Formatierung, und Notizen lassen sich als Markdown kopieren
  und speichern. Abschaltbar unter Einstellungen → Allgemein.
- Alle Aufklappmenüs in Words und LaTeX im Suite-Stil wie das Datei-Menü: ohne Pfeil, dünner Rahmen, kleine
  Überschriften, Hover gefüllt. „Mehr“ unten rechts ist jetzt ebenfalls so ein Menü.

## 4.2.0 (2026-10-19)
- **Changelog** im Suite-Look: oben rechts steht jetzt die Version – Klick darauf zeigt, was sich geändert hat
  (auch unter Einstellungen → Über). Nach einem Update ist sie hervorgehoben und notist sagt einmal Bescheid.

## 4.1.2 (2026-10-19)
- Installer: `notify-send` (Paket libnotify-bin/libnotify) wird mitinstalliert – ohne erschienen Erinnerungen unter
  GNOME nicht. `notist --check` zeigt jetzt auch, ob Erinnerungen angezeigt werden können.
- Startgröße passt sich kleinen Bildschirmen an (z. B. 1366×768) – das Fenster ragt nicht mehr über den Rand.

## 4.1.1 (2026-10-18)
- Kleine Fenster (z. B. Viertel-Kachel): Das Fenster wurde unten abgeschnitten – Textfeld bis zum Rand, Statuszeile
  mit den Symbolen fehlte. Notizen brauchen jetzt viel weniger Mindesthöhe, das Words-Menüband klappt in niedrigen
  Fenstern ein (Klick auf einen Reiter öffnet es), LaTeX-Editor und Vorschau dürfen schmaler werden.
- Die Dokumentauswahl sitzt auch im schmalen Fenster mittig mit fester Breite.

## 4.1.0 (2026-10-18)
- **Schneller Start**: Schließen blendet notist nur aus, der nächste Start ist sofort da (abschaltbar unter
  Einstellungen → Allgemein). `notist --daemon` lädt es schon beim Anmelden vor, `notist --quit` beendet wirklich.
- **Ordner** für die Notizen-Seitenleiste: 󰉗 unten legt einen an, Notizen per Ziehen oder „Mehr → In Ordner
  verschieben“ einsortieren, Klick klappt auf/zu, Rechtsklick benennt um oder löscht den Ordner (Notizen bleiben).
- Home: Einträge lassen sich direkt löschen (Papierkorb-Symbol beim Überfahren oder Rechtsklick).
- Home: „alle“ zeigt jetzt wirklich alle Einträge eines Bereichs (Esc oder „zurück“ führt zur Übersicht).
- **Esc** und **Strg+W** führen aus einem Eintrag zurück nach Home; Strg+Q schließt das Fenster.
- Der Name „notist“ steht oben links jetzt auch im schmalen Fenster; die Dokumentauswahl bei Words/LaTeX
  sitzt mittig in der Kopfleiste; der Rahmen um das Textfeld hält unten etwas Abstand zur Statuszeile.
- Einstellungen öffnen auf Hyprland mittig (Fensterregel siehe README).
- Englisch: „Notes“ hieß versehentlich „textwise“.

## 4.0.0 (2026-10-18)
- **Neuer Name: notist** (vorher „Notes“). Befehl `notist`, der alte Befehl `notes` funktioniert weiter.
  Deine Daten bleiben, wo sie sind.
- Einstellungen im Suite-Look: Seiten als Tabs (Tasten 1–7), Abschnitte als Kästen, schlanke Regler.
  Alle Nebenfenster haben dieselbe Kopfzeile.
- Fenster lässt sich jetzt sauber von Vollbild auf halbe Breite verkleinern (vorher wurde rechts abgeschnitten).

## 3.2.0 (2026-10-18)
- **Home**: neue Startansicht mit allen drei Bereichen auf einen Blick (zuletzt geändert, Suche über alles,
  „+ neu“ je Bereich). Alt+0 oder der „notes“-Chip oben links führt jederzeit zurück. Start-Ansicht in den
  Einstellungen wählbar.
- Words und LaTeX: die Dokumentliste sitzt immer oben im Aufklapp-Menü (Strg+T) – mehr Platz für die Seite.
- Neuer Look für Kopf- und Fußleiste: Tabs ⁰ home ¹ notizen ² words ³ latex, schmale Knöpfe, Statuszeile mit
  Tastenhinweisen, ✕ zum Schließen auf Kachel-Desktops.

## 3.1.3 (2026-10-18)
- Symbole fehlten auf Rechnern ohne (oder mit älterer) Nerd Font. Notes bringt jetzt eine eigene Symbolschrift mit
  (`app/fonts/notes-icons.ttf`) und lädt sie selbst – es muss nichts installiert werden.
- Updates per Git: `./update.sh` holt die neueste Version und installiert sie, ohne Rückfragen.

## 3.1.2 (2026-10-18)
- Words: jede Formatänderung (Schriftart, Größe, Fett, Farbe, Formatvorlage, Ausrichtung …) ist ein eigener
  Rückgängig-Schritt. Vorher sprang Strg+Z zu weit zurück und nahm auch Getipptes mit.
- Notizen: eigener Verlauf für Text **und** Formatierung (Strg+Z / Strg+Umschalt+Z / Pfeile in der Leiste).

## 3.1.1 (2026-10-18)
- Alle Auswahllisten, Zahlenfelder und Schalter im App-Stil (Akzent-Rahmen, gestaltete Aufklapp-Liste,
  Plus/Minus in Akzentfarbe). Schriftlisten zeigen jede Schrift in ihrem eigenen Aussehen und sind durchsuchbar.

## 3.1.0 (2026-10-18)
- **Designs**: neun Farbschemata (dunkel: Nacht, Glut, Wald, Rosé, Lavendel, Mitternacht; hell: Papier, Sand, Minze)
  oder „Automatisch“ (Desktop-Farben) – Einstellungen → Allgemein, wirkt sofort.
- Nebenfenster (Einstellungen, Verlauf, Befehle, Quellen, Tabellen-Editor, Tastenkürzel) mit Kopfzeile,
  Schließen-Knopf und Glas-Schalter.
- **.notes-Dateien** sind ein eigener Dateityp: Doppelklick im Dateimanager öffnet sie in Notes.
- Dropdown im halben Fenster neu gestaltet (Kopfzeile, passt sich an, Glas, kein Grau mehr).
- Notizen: neue Werkzeugleiste im Stil von Words (Rückgängig, F/K/U/Durchgestrichen, Schrift, Listen, Bild,
  Rechtschreibung); **automatische Listen**: „- “ oder „* “ startet eine Aufzählung, „1. “ eine Nummerierung,
  Enter setzt fort, Enter auf leerem Punkt beendet, Tab rückt ein.

## 3.0.0 (2026-10-18)
- **Sicherheit**: automatische Sicherungen als ZIP (Ziel frei wählbar, z. B. Cloud-Ordner), Wiederherstellen mit
  Sicherheitskopie; **Versionsverlauf** für jede Notiz und jedes Dokument (Mehr → Verlauf, Strg+Umschalt+H).
- **Ordnung**: Archiv, Schlagwörter mit Filter links, Farben für Notizen, Suche findet auch in den anderen Bereichen.
- **Notizen**: Bilder (Knopf, Strg+V, Hineinziehen; Klick für Größe/Speichern/Entfernen), **Erinnerungen** mit
  Benachrichtigung – dank systemd-Timer auch bei geschlossener App.
- **Words**: echte getrennte Seiten, Papierformat (A4/A5/Letter), Hoch-/Querformat, Seitenränder (Vorlagen + eigene),
  Kopf- und Fußzeile mit Platzhaltern, Seitenzahlen (Position, Format, ab Seite …), automatisches
  **Inhaltsverzeichnis** mit Seitenzahlen, **Fußnoten** (im PDF unten auf der Seite, in DOCX/ODT als echte Fußnoten),
  **ODT** (LibreOffice) öffnen und speichern, Umwandeln in ein LaTeX-Dokument.
- **LaTeX**: **Befehlsübersicht** mit 278 Befehlen/Umgebungen (F1, durchsuchbar, Klick fügt ein, als PDF-Spickzettel
  speicherbar), **SyncTeX** (Doppelklick ins PDF springt in den Quelltext, Strg+J zeigt die Zeile im PDF),
  **mehrere Dateien** pro Projekt (Reiter über dem Editor, \input wird ergänzt), **Literaturverwaltung** (.bib per
  Formular, \cite-Vorschläge, Literaturverzeichnis automatisch), Vorschläge für \ref, **Rechtschreibung** im
  Fließtext, **Formel-Vorschau** am Cursor, **Tabellen-Editor**, Umwandeln in ein Words-Dokument.
- **Allgemein**: Einstellungsfenster (Strg+,), Tastenkürzel-Übersicht (F1), Teilen (kopieren, E-Mail mit Anhang,
  .notes-Dateien für Freunde mit Notes), **englische Oberfläche** (Einstellungen → Sprache).

## 2.0.0 (2026-10-18)
- **Words** (vorher „Dokumente“): Menüband mit Reitern Start / Einfügen / Layout / Ansicht wie in Word,
  Formatvorlagen-Galerie, große Knöpfe zum Einfügen, Sonderzeichen, Navigationsbereich mit allen
  Überschriften, Statistik (Wörter, Zeichen, Lesezeit), Zoom-Regler und „Seitenbreite“,
  Seite x von y, Schatten unter dem Papier. Menüband einklappbar (Strg+F1 oder Doppelklick auf einen Reiter).
- **LaTeX** als dritter Modus (Alt+3): Editor mit Hervorhebung, Zeilennummern und Klammer-Markierung,
  Live-PDF-Vorschau, Fehlerliste auf Deutsch mit Sprung in die Zeile, Vorlagen (Lern-Dokument, Hausarbeit,
  Übungsblatt, Präsentation, Brief), Anleitung + durchsuchbarer Spickzettel, Vorschläge beim Tippen
  (Tab übernimmt), automatisches \end{…}, fehlende \usepackage werden ergänzt, Bilder landen im Projektordner.
  Alle Schreibhilfen einzeln abschaltbar. Tectonic lässt sich mit einem Klick einrichten.
- Weitergabe vorbereitet: läuft ohne Scourge/rice-apps (mitgelieferte Kopien), normale Titelleiste auf
  GNOME/KDE, App-Symbol wird selbst installiert, `notes datei.docx` öffnet Dateien, `notes --check`.
