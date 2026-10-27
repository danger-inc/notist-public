# notist – Änderungen

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
