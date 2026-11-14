# Inhalte für den LaTeX-Modus: Befehle mit deutschen Erklärungen (für Vorschläge, Statuszeile und
# Spickzettel), Umgebungen, Vorlagen, Anleitung und verständliche Fehlermeldungen.
# Schnipsel: "\x01" markiert Eingabefelder. Das erste Feld bekommt den Cursor (oder markierten Text),
# mit Tab springt man ins nächste.
import re

F = "\x01"

# (Befehl, Schnipsel, Erklärung, Rubrik, Paket oder None)
COMMANDS = [
    # Struktur
    ("\\section", "\\section{" + F + "}\n" + F, "Abschnittsüberschrift (nummeriert, im Inhaltsverzeichnis)", "Struktur", None),
    ("\\subsection", "\\subsection{" + F + "}\n" + F, "Unterabschnitt (1.1, 1.2 …)", "Struktur", None),
    ("\\subsubsection", "\\subsubsection{" + F + "}\n" + F, "Unter-Unterabschnitt (1.1.1 …)", "Struktur", None),
    ("\\section*", "\\section*{" + F + "}\n" + F, "Überschrift ohne Nummer (nicht im Inhaltsverzeichnis)", "Struktur", None),
    ("\\chapter", "\\chapter{" + F + "}\n" + F, "Kapitel – nur in den Klassen report und book", "Struktur", None),
    ("\\paragraph", "\\paragraph{" + F + "} " + F, "Kleine Zwischenüberschrift im Fließtext", "Struktur", None),
    ("\\tableofcontents", "\\tableofcontents\n", "Inhaltsverzeichnis an dieser Stelle (braucht oft zwei Durchläufe)", "Struktur", None),
    ("\\maketitle", "\\maketitle\n", "Druckt Titel, Autor und Datum (aus \\title, \\author, \\date)", "Struktur", None),
    ("\\title", "\\title{" + F + "}", "Titel des Dokuments (Präambel, erscheint bei \\maketitle)", "Struktur", None),
    ("\\author", "\\author{" + F + "}", "Autor:in (Präambel)", "Struktur", None),
    ("\\date", "\\date{" + F + "}", "Datum – \\date{\\today} für heute, \\date{} für keins", "Struktur", None),
    ("\\today", "\\today", "Heutiges Datum", "Struktur", None),
    ("\\newpage", "\\newpage\n", "Neue Seite beginnen", "Struktur", None),
    ("\\clearpage", "\\clearpage\n", "Neue Seite, vorher alle offenen Bilder/Tabellen ausgeben", "Struktur", None),
    ("\\appendix", "\\appendix\n", "Ab hier Anhang (Abschnitte heißen A, B, …)", "Struktur", None),
    ("\\label", "\\label{" + F + "}", "Unsichtbare Marke, auf die man mit \\ref verweisen kann", "Struktur", None),
    ("\\ref", "\\ref{" + F + "}", "Nummer eines \\label (Abschnitt, Bild, Gleichung)", "Struktur", None),
    ("\\pageref", "\\pageref{" + F + "}", "Seitenzahl eines \\label", "Struktur", None),
    ("\\footnote", "\\footnote{" + F + "}", "Fußnote unten auf der Seite", "Struktur", None),
    ("\\documentclass", "\\documentclass{" + F + "}", "Art des Dokuments: article, report, book, beamer, scrartcl …", "Struktur", None),
    ("\\usepackage", "\\usepackage{" + F + "}", "Zusatzpaket laden (nur in der Präambel)", "Struktur", None),
    ("\\input", "\\input{" + F + "}", "Andere .tex-Datei hier einfügen", "Struktur", None),
    # Text
    ("\\textbf", "\\textbf{" + F + "}", "Fett", "Text", None),
    ("\\textit", "\\textit{" + F + "}", "Kursiv", "Text", None),
    ("\\underline", "\\underline{" + F + "}", "Unterstrichen", "Text", None),
    ("\\emph", "\\emph{" + F + "}", "Hervorheben (meist kursiv) – der „richtige“ Weg statt \\textit", "Text", None),
    ("\\texttt", "\\texttt{" + F + "}", "Schreibmaschinenschrift (für Code, Dateinamen)", "Text", None),
    ("\\textsc", "\\textsc{" + F + "}", "Kapitälchen", "Text", None),
    ("\\textcolor", "\\textcolor{" + F + "red}{" + F + "}", "Farbiger Text (red, blue, green, …)", "Text", "xcolor"),
    ("\\small", "{\\small " + F + "}", "Kleinere Schrift (innerhalb der geschweiften Klammern)", "Text", None),
    ("\\large", "{\\large " + F + "}", "Größere Schrift", "Text", None),
    ("\\Large", "{\\Large " + F + "}", "Noch größere Schrift", "Text", None),
    ("\\huge", "{\\huge " + F + "}", "Riesige Schrift", "Text", None),
    ("\\centering", "\\centering\n", "Inhalt der aktuellen Umgebung zentrieren", "Text", None),
    ("\\par", "\\par\n", "Absatz beenden (eine Leerzeile macht dasselbe)", "Text", None),
    ("\\noindent", "\\noindent ", "Diesen Absatz nicht einrücken", "Text", None),
    ("\\vspace", "\\vspace{" + F + "1cm}", "Senkrechter Abstand", "Text", None),
    ("\\hspace", "\\hspace{" + F + "1cm}", "Waagerechter Abstand", "Text", None),
    ("\\hfill", "\\hfill ", "Schiebt den Rest der Zeile ganz nach rechts", "Text", None),
    ("\\linebreak", "\\linebreak\n", "Zeilenumbruch (Blocksatz bleibt)", "Text", None),
    ("\\url", "\\url{" + F + "}", "Internetadresse (anklickbar)", "Text", "hyperref"),
    ("\\href", "\\href{" + F + "https://}{" + F + "Linktext}", "Link mit eigenem Text", "Text", "hyperref"),
    ("\\enquote", "\\enquote{" + F + "}", "Text in passenden Anführungszeichen („…“)", "Text", "csquotes"),
    ("\\LaTeX", "\\LaTeX{}", "Schreibt das LaTeX-Logo", "Text", None),
    ("\\ldots", "\\ldots{}", "Auslassungspunkte …", "Text", None),
    ("\\item", "\\item ", "Neuer Punkt in einer Liste", "Listen", None),
    # Bilder & Tabellen
    ("\\includegraphics", "\\includegraphics[width=" + F + "0.8\\textwidth]{" + F + "}", "Bild einfügen (Dateiname ohne Pfad, liegt im Projektordner)", "Bilder & Tabellen", "graphicx"),
    ("\\caption", "\\caption{" + F + "}", "Bild-/Tabellenunterschrift (nummeriert)", "Bilder & Tabellen", None),
    ("\\hline", "\\hline\n", "Waagerechte Linie in einer Tabelle", "Bilder & Tabellen", None),
    ("\\toprule", "\\toprule\n", "Obere Tabellenlinie (schöner als \\hline)", "Bilder & Tabellen", "booktabs"),
    ("\\midrule", "\\midrule\n", "Mittlere Tabellenlinie unter dem Kopf", "Bilder & Tabellen", "booktabs"),
    ("\\bottomrule", "\\bottomrule\n", "Untere Tabellenlinie", "Bilder & Tabellen", "booktabs"),
    ("\\multicolumn", "\\multicolumn{" + F + "2}{" + F + "c}{" + F + "}", "Zelle über mehrere Spalten", "Bilder & Tabellen", None),
    ("\\textwidth", "\\textwidth", "Breite des Textbereichs (z. B. 0.5\\textwidth = halbe Breite)", "Bilder & Tabellen", None),
    # Literatur
    ("\\cite", "\\cite{" + F + "}", "Quelle zitieren (Schlüssel aus dem Literaturverzeichnis)", "Literatur", None),
    ("\\bibitem", "\\bibitem{" + F + "schluessel} " + F, "Eintrag im Literaturverzeichnis (thebibliography)", "Literatur", None),
    # Mathe
    ("\\frac", "\\frac{" + F + "}{" + F + "}", "Bruch: \\frac{Zähler}{Nenner}", "Mathe", None),
    ("\\sqrt", "\\sqrt{" + F + "}", "Wurzel – \\sqrt[3]{x} für dritte Wurzel", "Mathe", None),
    ("\\sum", "\\sum_{" + F + "i=1}^{" + F + "n} " + F, "Summenzeichen mit Grenzen", "Mathe", None),
    ("\\prod", "\\prod_{" + F + "i=1}^{" + F + "n} " + F, "Produktzeichen", "Mathe", None),
    ("\\int", "\\int_{" + F + "a}^{" + F + "b} " + F + " \\,dx", "Integral mit Grenzen", "Mathe", None),
    ("\\lim", "\\lim_{" + F + "x \\to \\infty} " + F, "Grenzwert", "Mathe", None),
    ("\\infty", "\\infty", "Unendlich ∞", "Mathe", None),
    ("\\cdot", "\\cdot ", "Malpunkt ·", "Mathe", None),
    ("\\times", "\\times ", "Malkreuz ×", "Mathe", None),
    ("\\div", "\\div ", "Geteilt ÷", "Mathe", None),
    ("\\pm", "\\pm ", "Plus-minus ±", "Mathe", None),
    ("\\leq", "\\leq ", "Kleiner gleich ≤", "Mathe", None),
    ("\\geq", "\\geq ", "Größer gleich ≥", "Mathe", None),
    ("\\neq", "\\neq ", "Ungleich ≠", "Mathe", None),
    ("\\approx", "\\approx ", "Ungefähr ≈", "Mathe", None),
    ("\\equiv", "\\equiv ", "Identisch / kongruent ≡", "Mathe", None),
    ("\\to", "\\to ", "Pfeil → (z. B. bei Grenzwerten)", "Mathe", None),
    ("\\Rightarrow", "\\Rightarrow ", "Folgepfeil ⇒", "Mathe", None),
    ("\\Leftrightarrow", "\\Leftrightarrow ", "Äquivalenzpfeil ⇔", "Mathe", None),
    ("\\in", "\\in ", "Element von ∈", "Mathe", None),
    ("\\notin", "\\notin ", "Kein Element von ∉", "Mathe", None),
    ("\\subseteq", "\\subseteq ", "Teilmenge ⊆", "Mathe", None),
    ("\\cup", "\\cup ", "Vereinigung ∪", "Mathe", None),
    ("\\cap", "\\cap ", "Schnitt ∩", "Mathe", None),
    ("\\emptyset", "\\emptyset", "Leere Menge ∅", "Mathe", None),
    ("\\forall", "\\forall ", "Für alle ∀", "Mathe", None),
    ("\\exists", "\\exists ", "Es existiert ∃", "Mathe", None),
    ("\\partial", "\\partial ", "Partielle Ableitung ∂", "Mathe", None),
    ("\\nabla", "\\nabla ", "Nabla ∇", "Mathe", None),
    ("\\vec", "\\vec{" + F + "}", "Vektorpfeil über einem Buchstaben", "Mathe", None),
    ("\\overline", "\\overline{" + F + "}", "Strich über dem Ausdruck", "Mathe", None),
    ("\\hat", "\\hat{" + F + "}", "Dach über einem Buchstaben", "Mathe", None),
    ("\\mathbb", "\\mathbb{" + F + "R}", "Zahlbereiche ℝ, ℕ, ℤ, ℚ, ℂ", "Mathe", "amssymb"),
    ("\\mathrm", "\\mathrm{" + F + "}", "Aufrechte Schrift in Formeln (z. B. Einheiten)", "Mathe", None),
    ("\\text", "\\text{" + F + "}", "Normaler Text innerhalb einer Formel", "Mathe", "amsmath"),
    ("\\left(", "\\left( " + F + " \\right)", "Klammern, die mit dem Inhalt mitwachsen", "Mathe", None),
    ("\\sin", "\\sin ", "Sinus", "Mathe", None),
    ("\\cos", "\\cos ", "Kosinus", "Mathe", None),
    ("\\tan", "\\tan ", "Tangens", "Mathe", None),
    ("\\log", "\\log ", "Logarithmus", "Mathe", None),
    ("\\ln", "\\ln ", "Natürlicher Logarithmus", "Mathe", None),
    ("\\exp", "\\exp ", "Exponentialfunktion", "Mathe", None),
    ("\\binom", "\\binom{" + F + "n}{" + F + "k}", "Binomialkoeffizient", "Mathe", "amsmath"),
    ("\\quad", "\\quad ", "Großer Abstand in Formeln", "Mathe", None),
    ("\\dots", "\\dots ", "Pünktchen … (passt sich an)", "Mathe", None),
]

COMMANDS += [
    # Struktur & Dokument
    ("\\part", "\\part{" + F + "}\n", "Teil (über Kapiteln) – für sehr lange Dokumente", "Struktur", None),
    ("\\subparagraph", "\\subparagraph{" + F + "} ", "Kleinste Zwischenüberschrift", "Struktur", None),
    ("\\include", "\\include{" + F + "}", "Andere Datei einbinden und davor eine neue Seite beginnen", "Struktur", None),
    ("\\listoffigures", "\\listoffigures\n", "Abbildungsverzeichnis", "Struktur", None),
    ("\\listoftables", "\\listoftables\n", "Tabellenverzeichnis", "Struktur", None),
    ("\\pagenumbering", "\\pagenumbering{" + F + "arabic}", "Art der Seitenzahlen: arabic, roman, Roman, alph", "Struktur", None),
    ("\\thispagestyle", "\\thispagestyle{" + F + "empty}", "Seitenstil nur dieser Seite (empty = ohne Seitenzahl)", "Struktur", None),
    ("\\pagestyle", "\\pagestyle{" + F + "plain}", "Seitenstil: plain, empty, headings, fancy", "Struktur", None),
    ("\\newcommand", "\\newcommand{\\" + F + "name}{" + F + "}", "Eigenen Befehl festlegen (Abkürzung)", "Struktur", None),
    ("\\renewcommand", "\\renewcommand{\\" + F + "}{" + F + "}", "Bestehenden Befehl umdefinieren", "Struktur", None),
    ("\\setlength", "\\setlength{\\" + F + "parindent}{" + F + "0pt}", "Länge setzen (z. B. Absatzeinzug)", "Struktur", None),
    ("\\eqref", "\\eqref{" + F + "}", "Verweis auf eine Gleichung, mit Klammern: (3)", "Struktur", "amsmath"),
    ("\\autoref", "\\autoref{" + F + "}", "Verweis mit Wort davor: „Abbildung 2“", "Struktur", "hyperref"),
    ("\\nameref", "\\nameref{" + F + "}", "Verweis mit dem Namen der Überschrift", "Struktur", "hyperref"),
    ("\\bibliography", "\\bibliography{" + F + "literatur}", "Literaturverzeichnis aus einer .bib-Datei", "Literatur", None),
    ("\\bibliographystyle", "\\bibliographystyle{" + F + "plain}", "Zitierstil: plain, alpha, abbrv, unsrt", "Literatur", None),
    ("\\addbibresource", "\\addbibresource{" + F + "literatur.bib}", "biblatex: .bib-Datei angeben (Präambel)", "Literatur", "biblatex"),
    ("\\printbibliography", "\\printbibliography\n", "biblatex: Literaturverzeichnis ausgeben", "Literatur", "biblatex"),
    ("\\citep", "\\citep{" + F + "}", "Zitat in Klammern (natbib)", "Literatur", "natbib"),
    ("\\nocite", "\\nocite{" + F + "*}", "Quelle ins Verzeichnis, ohne sie im Text zu zitieren", "Literatur", None),
    # Text
    ("\\textsuperscript", "\\textsuperscript{" + F + "}", "Hochgestellt im Text", "Text", None),
    ("\\textsubscript", "\\textsubscript{" + F + "}", "Tiefgestellt im Text", "Text", None),
    ("\\textsf", "\\textsf{" + F + "}", "Serifenlose Schrift", "Text", None),
    ("\\textrm", "\\textrm{" + F + "}", "Normale Serifenschrift", "Text", None),
    ("\\textnormal", "\\textnormal{" + F + "}", "Zurück zur Standardschrift", "Text", None),
    ("\\sout", "\\sout{" + F + "}", "Durchgestrichen", "Text", "ulem"),
    ("\\tiny", "{\\tiny " + F + "}", "Winzige Schrift", "Text", None),
    ("\\scriptsize", "{\\scriptsize " + F + "}", "Sehr kleine Schrift", "Text", None),
    ("\\footnotesize", "{\\footnotesize " + F + "}", "Schrift so groß wie Fußnoten", "Text", None),
    ("\\normalsize", "{\\normalsize " + F + "}", "Normale Schriftgröße", "Text", None),
    ("\\LARGE", "{\\LARGE " + F + "}", "Sehr große Schrift", "Text", None),
    ("\\Huge", "{\\Huge " + F + "}", "Größte Schrift", "Text", None),
    ("\\smallskip", "\\smallskip\n", "Kleiner senkrechter Abstand", "Text", None),
    ("\\medskip", "\\medskip\n", "Mittlerer senkrechter Abstand", "Text", None),
    ("\\bigskip", "\\bigskip\n", "Großer senkrechter Abstand", "Text", None),
    ("\\vfill", "\\vfill\n", "Schiebt den Rest der Seite nach unten", "Text", None),
    ("\\raggedright", "\\raggedright\n", "Flattersatz (linksbündig, ohne Blocksatz)", "Text", None),
    ("\\onehalfspacing", "\\onehalfspacing\n", "1,5-facher Zeilenabstand (Präambel)", "Text", "setspace"),
    ("\\doublespacing", "\\doublespacing\n", "Doppelter Zeilenabstand", "Text", "setspace"),
    ("\\newline", "\\newline\n", "Neue Zeile (ohne neuen Absatz)", "Text", None),
    ("\\textbackslash", "\\textbackslash{}", "Backslash \\ als Zeichen", "Text", None),
    ("\\S", "\\S{} ", "Paragrafzeichen §", "Text", None),
    ("\\copyright", "\\copyright{} ", "Copyright ©", "Text", None),
    ("\\dag", "\\dag{} ", "Kreuz †", "Text", None),
    ("\\TeX", "\\TeX{}", "TeX-Logo", "Text", None),
    ("\\verb", "\\verb|" + F + "|", "Code im Text, genau wie geschrieben", "Text", None),
    ("\\lstinline", "\\lstinline|" + F + "|", "Code im Text mit Hervorhebung", "Text", "listings"),
    ("\\SI", "\\SI{" + F + "}{" + F + "\\meter}", "Zahl mit Einheit: \\SI{3}{\\meter}", "Text", "siunitx"),
    # Bilder & Tabellen
    ("\\cline", "\\cline{" + F + "2-3}", "Linie nur unter bestimmten Spalten", "Bilder & Tabellen", None),
    ("\\multirow", "\\multirow{" + F + "2}{*}{" + F + "}", "Zelle über mehrere Zeilen", "Bilder & Tabellen", "multirow"),
    ("\\rotatebox", "\\rotatebox{" + F + "90}{" + F + "}", "Inhalt drehen", "Bilder & Tabellen", "graphicx"),
    ("\\resizebox", "\\resizebox{" + F + "\\textwidth}{!}{" + F + "}", "Inhalt auf Breite skalieren", "Bilder & Tabellen", "graphicx"),
    ("\\linewidth", "\\linewidth", "Breite der aktuellen Zeile (in Spalten/Boxen)", "Bilder & Tabellen", None),
    ("\\subcaption", "\\subcaption{" + F + "}", "Unterschrift eines Teilbilds", "Bilder & Tabellen", "subcaption"),
    # Mathe
    ("\\mathbf", "\\mathbf{" + F + "}", "Fett in Formeln (z. B. Vektoren)", "Mathe", None),
    ("\\mathcal", "\\mathcal{" + F + "}", "Schreibschrift-Buchstaben: 𝒜, ℬ", "Mathe", None),
    ("\\boldsymbol", "\\boldsymbol{" + F + "}", "Fettes Symbol (auch griechisch)", "Mathe", "amsmath"),
    ("\\operatorname", "\\operatorname{" + F + "}", "Eigener Funktionsname (aufrecht)", "Mathe", "amsmath"),
    ("\\underbrace", "\\underbrace{" + F + "}_{" + F + "}", "Geschweifte Klammer unter einem Ausdruck", "Mathe", None),
    ("\\overbrace", "\\overbrace{" + F + "}^{" + F + "}", "Geschweifte Klammer über einem Ausdruck", "Mathe", None),
    ("\\overset", "\\overset{" + F + "}{" + F + "}", "Etwas über ein Zeichen setzen", "Mathe", "amsmath"),
    ("\\tilde", "\\tilde{" + F + "}", "Tilde über einem Buchstaben", "Mathe", None),
    ("\\bar", "\\bar{" + F + "}", "Strich über einem Buchstaben", "Mathe", None),
    ("\\dot", "\\dot{" + F + "}", "Punkt über einem Buchstaben (Ableitung)", "Mathe", None),
    ("\\ddot", "\\ddot{" + F + "}", "Zwei Punkte (zweite Ableitung)", "Mathe", None),
    ("\\max", "\\max ", "Maximum", "Mathe", None),
    ("\\min", "\\min ", "Minimum", "Mathe", None),
    ("\\sup", "\\sup ", "Supremum", "Mathe", None),
    ("\\inf", "\\inf ", "Infimum", "Mathe", None),
    ("\\det", "\\det ", "Determinante", "Mathe", None),
    ("\\iint", "\\iint ", "Doppelintegral", "Mathe", "amsmath"),
    ("\\oint", "\\oint ", "Kurvenintegral", "Mathe", None),
    ("\\langle", "\\langle " + F + " \\rangle", "Spitze Klammern ⟨ ⟩", "Mathe", None),
    ("\\lfloor", "\\lfloor " + F + " \\rfloor", "Abrunden ⌊ ⌋", "Mathe", None),
    ("\\lceil", "\\lceil " + F + " \\rceil", "Aufrunden ⌈ ⌉", "Mathe", None),
    ("\\left|", "\\left| " + F + " \\right|", "Betragsstriche, die mitwachsen", "Mathe", None),
    ("\\cdots", "\\cdots ", "Pünktchen mittig ⋯", "Mathe", None),
    ("\\vdots", "\\vdots ", "Pünktchen senkrecht ⋮", "Mathe", None),
    ("\\ddots", "\\ddots ", "Pünktchen schräg ⋱", "Mathe", None),
    ("\\neg", "\\neg ", "Nicht ¬", "Mathe", None),
    ("\\land", "\\land ", "Und ∧", "Mathe", None),
    ("\\lor", "\\lor ", "Oder ∨", "Mathe", None),
    ("\\setminus", "\\setminus ", "Mengendifferenz ∖", "Mathe", None),
    ("\\subset", "\\subset ", "Echte Teilmenge ⊂", "Mathe", None),
    ("\\supseteq", "\\supseteq ", "Obermenge ⊇", "Mathe", None),
    ("\\mid", "\\mid ", "Senkrechter Strich (teilt, „mit“)", "Mathe", None),
    ("\\propto", "\\propto ", "Proportional ∝", "Mathe", None),
    ("\\sim", "\\sim ", "Ähnlich / verteilt nach ∼", "Mathe", None),
    ("\\cong", "\\cong ", "Kongruent ≅", "Mathe", None),
    ("\\perp", "\\perp ", "Senkrecht ⊥", "Mathe", None),
    ("\\parallel", "\\parallel ", "Parallel ∥", "Mathe", None),
    ("\\angle", "\\angle ", "Winkel ∠", "Mathe", None),
    ("\\circ", "\\circ ", "Verkettung ∘ / Grad (^\\circ)", "Mathe", None),
    ("\\leftarrow", "\\leftarrow ", "Pfeil nach links ←", "Mathe", None),
    ("\\Leftarrow", "\\Leftarrow ", "Doppelpfeil links ⇐", "Mathe", None),
    ("\\mapsto", "\\mapsto ", "Abbildungspfeil ↦", "Mathe", None),
    ("\\uparrow", "\\uparrow ", "Pfeil nach oben ↑", "Mathe", None),
    ("\\downarrow", "\\downarrow ", "Pfeil nach unten ↓", "Mathe", None),
    ("\\displaystyle", "\\displaystyle ", "Formel im Text so groß wie abgesetzt", "Mathe", None),
    ("\\,", "\\,", "Kleiner Abstand in Formeln (z. B. vor dx)", "Mathe", None),
    ("\\qquad", "\\qquad ", "Sehr großer Abstand in Formeln", "Mathe", None),
    ("\\tag", "\\tag{" + F + "}", "Eigene Gleichungsnummer", "Mathe", "amsmath"),
    ("\\nonumber", "\\nonumber", "Diese Zeile in align ohne Nummer", "Mathe", None),
    # Präsentation
    ("\\frametitle", "\\frametitle{" + F + "}", "Titel einer Folie (beamer)", "Präsentation", None),
    ("\\titlepage", "\\titlepage", "Titelfolie (beamer)", "Präsentation", None),
    ("\\pause", "\\pause ", "Folie schrittweise aufdecken", "Präsentation", None),
    ("\\usetheme", "\\usetheme{" + F + "Madrid}", "Design der Präsentation", "Präsentation", None),
    ("\\alert", "\\alert{" + F + "}", "Hervorheben auf Folien (rot)", "Präsentation", None),
    # Zeichnen
    ("\\draw", "\\draw " + F + "(0,0) -- (1,1);", "Linie zeichnen (in tikzpicture)", "Zeichnen", "tikz"),
    ("\\node", "\\node at (" + F + "0,0) {" + F + "};", "Text an eine Stelle setzen (TikZ)", "Zeichnen", "tikz"),
    ("\\fill", "\\fill[" + F + "blue] (0,0) circle (1);", "Gefüllte Form (TikZ)", "Zeichnen", "tikz"),
]
ENVIRONMENTS_EXTRA = [
    ("tikzpicture", "  \\draw " + F + "(0,0) -- (2,1);", "Zeichnung mit TikZ", "tikz"),
    ("lstlisting", F, "Programmcode mit Hervorhebung – [language=Python]", "listings"),
    ("titlepage", "  " + F, "Eigene Titelseite ohne Seitenzahl", None),
    ("subfigure", "  " + F, "Teilbild nebeneinander – {0.45\\textwidth}", "subcaption"),
    ("multicols", F, "Mehrspaltiger Text – {2} = zwei Spalten", "multicol"),
    ("gather", "  " + F + " \\\\\n  ", "Mehrere zentrierte Formeln", "amsmath"),
    ("matrix", "  " + F + " & \\\\\n  & ", "Matrix ohne Klammern", "amsmath"),
    ("vmatrix", "  " + F + " & \\\\\n  & ", "Determinante (senkrechte Striche)", "amsmath"),
    ("block", "  " + F, "Kasten mit Überschrift auf einer Folie – {Titel}", None),
    ("columns", "  \\column{0.5\\textwidth}\n  " + F, "Spalten auf einer Folie", None),
    ("letter", F, "Ein Brief (scrlttr2) – {Empfänger}", None),
    ("flushleft", "  " + F, "Inhalt linksbündig", None),
    ("quotation", "  " + F, "Längeres eingerücktes Zitat (mit Absätzen)", None),
]
EXAMPLES = {
    "\\section": "\\section{Einleitung}", "\\textbf": "Das ist \\textbf{wichtig}.", "\\frac": "$\\frac{1}{2}$",
    "\\sqrt": "$\\sqrt{2}$, $\\sqrt[3]{8}$", "\\sum": "$\\sum_{i=1}^{n} i$", "\\int": "$\\int_0^1 x\\,dx$",
    "\\footnote": "Text\\footnote{Quelle}", "\\label": "\\section{X}\\label{sec:x}", "\\ref": "siehe Abschnitt~\\ref{sec:x}",
    "\\cite": "wie gezeigt \\cite{mueller2020}", "\\href": "\\href{https://x.de}{Webseite}",
    "\\includegraphics": "\\includegraphics[width=0.5\\textwidth]{bild.png}", "\\textcolor": "\\textcolor{red}{rot}",
    "\\mathbb": "$x \\in \\mathbb{R}$", "\\vec": "$\\vec{v}$", "\\lim": "$\\lim_{x\\to 0} f(x)$",
    "\\item": "\\item Erster Punkt", "\\usepackage": "\\usepackage{amsmath}", "\\newcommand": "\\newcommand{\\R}{\\mathbb{R}}",
    "\\vspace": "\\vspace{1cm}", "\\SI": "\\SI{9.81}{\\meter\\per\\second\\squared}", "\\binom": "$\\binom{n}{k}$",
}

GREEK = ["alpha", "beta", "gamma", "delta", "epsilon", "varepsilon", "zeta", "eta", "theta", "lambda", "mu",
         "nu", "xi", "pi", "rho", "sigma", "tau", "phi", "varphi", "chi", "psi", "omega",
         "Gamma", "Delta", "Theta", "Lambda", "Pi", "Sigma", "Phi", "Psi", "Omega"]
GREEK_CHARS = "αβγδεεζηθλμνξπρστφφχψωΓΔΘΛΠΣΦΨΩ"
for _g, _c in zip(GREEK, GREEK_CHARS):
    COMMANDS.append(("\\" + _g, "\\" + _g + " ", f"Griechisch {_c}", "Griechisch", None))

# (Name, Inhalt, Erklärung, Paket)
ENVIRONMENTS = [
    ("document", F, "Der eigentliche Inhalt – alles Sichtbare steht hier drin", None),
    ("itemize", "  \\item " + F, "Aufzählung mit Punkten", None),
    ("enumerate", "  \\item " + F, "Nummerierte Liste", None),
    ("description", "  \\item[" + F + "Begriff] " + F, "Liste mit Begriffen und Erklärungen", None),
    ("equation", "  " + F, "Nummerierte Formel in eigener Zeile", None),
    ("equation*", "  " + F, "Formel in eigener Zeile ohne Nummer", "amsmath"),
    ("align", "  " + F + " &= " + F + " \\\\\n  &= ", "Mehrere Formeln, an & ausgerichtet (\\\\ = neue Zeile)", "amsmath"),
    ("align*", "  " + F + " &= " + F + " \\\\\n  &= ", "Wie align, aber ohne Nummern", "amsmath"),
    ("figure", "  \\centering\n  \\includegraphics[width=0.8\\textwidth]{" + F + "}\n  \\caption{" + F + "}\n  \\label{fig:" + F + "}",
     "Bild mit Unterschrift (gleitet an eine passende Stelle)", "graphicx"),
    ("table", "  \\centering\n  \\caption{" + F + "}\n  \\begin{tabular}{lll}\n    " + F + " & & \\\\\n  \\end{tabular}",
     "Tabelle mit Unterschrift (gleitet an eine passende Stelle)", None),
    ("tabular", "  " + F + " & & \\\\\n", "Die Tabelle selbst: {lcr} = Spalten links/zentriert/rechts, & trennt Zellen, \\\\ beendet die Zeile", None),
    ("center", "  " + F, "Inhalt zentrieren", None),
    ("flushright", "  " + F, "Inhalt rechtsbündig", None),
    ("quote", "  " + F, "Eingerücktes Zitat", None),
    ("abstract", "  " + F, "Zusammenfassung (nur article/report)", None),
    ("verbatim", F, "Text genau so ausgeben, wie er dasteht (für Code)", None),
    ("minipage", F, "Kleiner Kasten mit fester Breite – \\begin{minipage}{0.45\\textwidth}", None),
    ("thebibliography", "  \\bibitem{" + F + "schluessel} " + F, "Einfaches Literaturverzeichnis – {9} = Platz für die Nummern", None),
    ("frame", "  \\frametitle{" + F + "}\n  " + F, "Eine Folie (nur in beamer-Präsentationen)", None),
    ("cases", "  " + F + " & \\text{wenn } " + F + " \\\\\n  ", "Fallunterscheidung in einer Formel", "amsmath"),
    ("pmatrix", "  " + F + " & \\\\\n  & ", "Matrix mit runden Klammern", "amsmath"),
    ("bmatrix", "  " + F + " & \\\\\n  & ", "Matrix mit eckigen Klammern", "amsmath"),
]
ENV_ARGS = {"tabular": "{lll}", "minipage": "{0.45\\textwidth}", "thebibliography": "{9}", "figure": "[htbp]",
            "table": "[htbp]"}

ENVIRONMENTS += ENVIRONMENTS_EXTRA
ENV_ARGS.update({"subfigure": "{0.45\\textwidth}", "multicols": "{2}", "block": "{" + F + "Titel}", "letter": "{Empfänger}",
                 "lstlisting": "[language=Python]"})
CMD_INFO = {c[0]: c for c in COMMANDS}
ENV_INFO = {e[0]: e for e in ENVIRONMENTS}
CATEGORIES = ["Struktur", "Text", "Listen", "Literatur", "Bilder & Tabellen", "Mathe", "Griechisch", "Präsentation",
              "Zeichnen"]


def env_snippet(name):
    body = ENV_INFO[name][1] if name in ENV_INFO else "  " + F
    return f"\\begin{{{name}}}{ENV_ARGS.get(name, '')}\n{body}\n\\end{{{name}}}\n"


# Spickzettel: Rubrik → [(Beschriftung, Schnipsel, Erklärung, Paket)]
CHEATS = [
    ("Grundgerüst", [
        ("Abschnitt", "\\section{" + F + "}\n", "Überschrift erster Ebene", None),
        ("Unterabschnitt", "\\subsection{" + F + "}\n", "Überschrift zweiter Ebene", None),
        ("Inhaltsverzeichnis", "\\tableofcontents\n", "Wird beim zweiten Kompilieren gefüllt", None),
        ("Titel ausgeben", "\\maketitle\n", "Nutzt \\title, \\author, \\date aus der Präambel", None),
        ("Neue Seite", "\\newpage\n", "", None),
        ("Fußnote", "\\footnote{" + F + "}", "", None),
        ("Kommentar", "% " + F, "Alles nach % ignoriert LaTeX – Notizen für dich", None),
    ]),
    ("Text", [
        ("Fett", "\\textbf{" + F + "}", "", None),
        ("Kursiv", "\\textit{" + F + "}", "", None),
        ("Unterstrichen", "\\underline{" + F + "}", "", None),
        ("Hervorheben", "\\emph{" + F + "}", "", None),
        ("Code-Schrift", "\\texttt{" + F + "}", "", None),
        ("Farbe", "\\textcolor{red}{" + F + "}", "", "xcolor"),
        ("Link", "\\href{https://" + F + "}{" + F + "Text}", "", "hyperref"),
        ("Anführungszeichen", "\\enquote{" + F + "}", "Setzt „deutsche“ Zeichen", "csquotes"),
        ("Zentriert", env_snippet("center"), "", None),
    ]),
    ("Listen", [
        ("Aufzählung", env_snippet("itemize"), "Punkte mit •", None),
        ("Nummeriert", env_snippet("enumerate"), "1., 2., 3.", None),
        ("Begriffe", env_snippet("description"), "Begriff: Erklärung", None),
        ("Neuer Punkt", "\\item " + F, "", None),
    ]),
    ("Mathe", [
        ("Formel im Text", "$" + F + "$", "Mathe mitten im Satz: $a^2+b^2=c^2$", None),
        ("Formel abgesetzt", "\\[\n  " + F + "\n\\]\n", "Formel in eigener Zeile", None),
        ("Nummerierte Formel", env_snippet("equation"), "", None),
        ("Mehrzeilig ausgerichtet", env_snippet("align*"), "& markiert die Ausrichtung", "amsmath"),
        ("Bruch", "\\frac{" + F + "}{" + F + "}", "", None),
        ("Hochgestellt", "^{" + F + "}", "x^{2} → x²", None),
        ("Tiefgestellt", "_{" + F + "}", "a_{n} → aₙ", None),
        ("Wurzel", "\\sqrt{" + F + "}", "", None),
        ("Summe", "\\sum_{i=1}^{n} ", "", None),
        ("Integral", "\\int_{a}^{b} " + F + " \\,dx", "", None),
        ("Grenzwert", "\\lim_{x \\to \\infty} ", "", None),
        ("Fallunterscheidung", "f(x) = " + env_snippet("cases"), "", "amsmath"),
        ("Matrix", env_snippet("pmatrix"), "", "amsmath"),
        ("Zahlbereich ℝ", "\\mathbb{R}", "", "amssymb"),
        ("Text in Formel", "\\text{" + F + "}", "", "amsmath"),
    ]),
    ("Symbole", [
        ("≤", "\\leq ", "", None), ("≥", "\\geq ", "", None), ("≠", "\\neq ", "", None),
        ("≈", "\\approx ", "", None), ("±", "\\pm ", "", None), ("·", "\\cdot ", "", None),
        ("×", "\\times ", "", None), ("∞", "\\infty ", "", None), ("→", "\\to ", "", None),
        ("⇒", "\\Rightarrow ", "", None), ("⇔", "\\Leftrightarrow ", "", None), ("∈", "\\in ", "", None),
        ("∀", "\\forall ", "", None), ("∃", "\\exists ", "", None), ("∂", "\\partial ", "", None),
        ("…", "\\ldots ", "", None), ("€", "\\euro{}", "", "eurosym"), ("°", "^\\circ", "In Mathe: $90^\\circ$", None),
        ("%", "\\% ", "% allein wäre ein Kommentar", None), ("&", "\\& ", "& allein trennt Tabellenzellen", None),
        ("$", "\\$ ", "", None), ("#", "\\# ", "", None), ("_", "\\_", "", None),
    ]),
    ("Griechisch", [(c, "\\" + g + " ", g, None) for g, c in zip(GREEK, GREEK_CHARS)]),
    ("Bilder & Tabellen", [
        ("Bild mit Unterschrift", env_snippet("figure"), "Bild über „Einfügen → Bild“ landet im Projektordner", "graphicx"),
        ("Tabelle", env_snippet("table"), "l/c/r = Ausrichtung je Spalte", None),
        ("Tabellenlinie", "\\hline\n", "", None),
        ("Verweis", "\\ref{" + F + "}", "Nummer eines \\label", None),
    ]),
]

# ---------------------------------------------------------------------------------------------------
# Vorlagen
# ---------------------------------------------------------------------------------------------------
_PRE = "\\usepackage[ngerman]{babel}\n"

TEMPLATES = [
    ("lernen", "󰑴", "LaTeX lernen", "Ein Übungsdokument, das dir die Grundlagen Schritt für Schritt zeigt",
     r"""% ===================================================================
% Willkommen! Dieses Dokument erklärt LaTeX an Beispielen.
% Alles hinter einem %-Zeichen ist ein Kommentar und erscheint NICHT im PDF.
% Rechts siehst du das Ergebnis. Ändere einfach etwas und schau zu.
% ===================================================================

% --- TEIL 1: Die Präambel -------------------------------------------
% Vor \begin{document} legst du fest, WAS für ein Dokument es wird
% und welche Zusatzpakete du brauchst.
\documentclass[11pt]{article}   % article = kurzer Text, Bericht, Hausarbeit
\usepackage[ngerman]{babel}      % deutsche Silbentrennung, "Inhaltsverzeichnis" statt "Contents"
\usepackage{amsmath}             % bessere Mathe-Umgebungen
\usepackage{graphicx}            % Bilder einbinden

\title{Mein erstes \LaTeX-Dokument}
\author{Dein Name}
\date{\today}

% --- TEIL 2: Der Inhalt ---------------------------------------------
\begin{document}

\maketitle   % druckt Titel, Autor und Datum von oben

\section{Text schreiben}
Ganz normaler Text wird einfach getippt. Ein einzelner Zeilenumbruch
im Code ändert nichts -- LaTeX macht den Zeilenumbruch selbst.

Eine leere Zeile beginnt einen neuen Absatz.
Mit \textbf{fett}, \textit{kursiv} und \emph{hervorgehoben} formatierst du Wörter.

\section{Listen}
\begin{itemize}
  \item Ein Punkt
  \item Noch ein Punkt
\end{itemize}

\begin{enumerate}
  \item Erstens
  \item Zweitens
\end{enumerate}

\section{Mathe}
Formeln im Satz stehen zwischen Dollarzeichen: $a^2 + b^2 = c^2$.
Eine Formel in eigener Zeile:
\[
  \int_0^1 x^2 \, dx = \frac{1}{3}
\]

\section{Deine Aufgabe}
% Probiere: Schreibe unten einen Unterabschnitt mit \subsection{...}
% Tipp: Tippe \sub -- es erscheinen Vorschläge. Mit Tab übernehmen.


\end{document}
"""),
    ("artikel", "󰈙", "Einfaches Dokument", "Leeres Dokument mit deutschen Einstellungen",
     "\\documentclass[11pt,a4paper]{article}\n" + _PRE + "\\usepackage{amsmath}\n\\usepackage{graphicx}\n\n"
     "\\title{" + F + "Titel}\n\\author{Dein Name}\n\\date{\\today}\n\n\\begin{document}\n\n\\maketitle\n\n" + F + "\n\n\\end{document}\n"),
    ("hausarbeit", "󰂺", "Hausarbeit", "Titelseite, Inhaltsverzeichnis, Kapitel, Literaturverzeichnis",
     r"""\documentclass[12pt,a4paper]{article}
\usepackage[ngerman]{babel}
\usepackage[a4paper, margin=2.5cm]{geometry}  % Seitenränder
\usepackage{setspace}                          % Zeilenabstand
\onehalfspacing                                % 1,5-zeilig
\usepackage{amsmath}
\usepackage{graphicx}
\usepackage{csquotes}
\usepackage[hidelinks]{hyperref}               % klickbare Verweise im PDF

\begin{document}

% ---------- Titelseite ----------
\begin{titlepage}
  \centering
  {\Large Universität / Schule\par}
  \vspace{2cm}
  {\huge\bfseries \x01Titel der Arbeit\par}
  \vspace{1cm}
  {\large Hausarbeit im Fach …\par}
  \vfill
  Vorgelegt von: Dein Name\\
  Matrikelnummer: 123456\\
  Datum: \today
\end{titlepage}

\tableofcontents
\newpage

\section{Einleitung}
\x01

\section{Hauptteil}
\subsection{Erster Punkt}
Wie \enquote{Müller} schreibt \cite{mueller2020}, …

\section{Fazit}

% ---------- Literatur ----------
\begin{thebibliography}{9}
  \bibitem{mueller2020} Müller, A. (2020): \textit{Ein Buchtitel}. Verlag, Ort.
\end{thebibliography}

\end{document}
""".replace("\\x01", F)),
    ("mathe", "󰿈", "Mathe & Übungsblatt", "Aufgaben mit Formeln, Lösungsplatz",
     r"""\documentclass[11pt,a4paper]{article}
\usepackage[ngerman]{babel}
\usepackage[a4paper, margin=2cm]{geometry}
\usepackage{amsmath, amssymb}

\title{Übungsblatt \x01 1}
\author{Name}
\date{\today}

\begin{document}
\maketitle

\section*{Aufgabe 1}
Berechne $\displaystyle\lim_{x \to 0} \frac{\sin x}{x}$.

\section*{Aufgabe 2}
Löse das Gleichungssystem:
\begin{align*}
  2x + 3y &= 7 \\
  x - y   &= 1
\end{align*}

\section*{Lösung}
\x01

\end{document}
""".replace("\\x01", F)),
    ("praesentation", "󰐩", "Präsentation", "Folien mit beamer",
     r"""\documentclass{beamer}
\usepackage[ngerman]{babel}
\usetheme{Madrid}      % andere Designs: Berlin, Copenhagen, metropolis …

\title{\x01Titel der Präsentation}
\author{Dein Name}
\date{\today}

\begin{document}

\begin{frame}
  \titlepage
\end{frame}

\begin{frame}{Gliederung}
  \tableofcontents
\end{frame}

\section{Einleitung}
\begin{frame}{Erste Folie}
  \begin{itemize}
    \item \x01
    \item Zweiter Punkt
  \end{itemize}
\end{frame}

\end{document}
""".replace("\\x01", F)),
    ("brief", "󰇮", "Brief", "Deutscher Brief nach DIN (KOMA-Script)",
     r"""\documentclass[paper=a4, fromalign=right, parskip=half]{scrlttr2}
\usepackage[ngerman]{babel}

\setkomavar{fromname}{Dein Name}
\setkomavar{fromaddress}{Straße 1\\12345 Stadt}
\setkomavar{date}{\today}
\setkomavar{subject}{\x01Betreff}

\begin{document}
\begin{letter}{Empfänger\\Straße 2\\54321 Ort}

\opening{Sehr geehrte Damen und Herren,}

\x01

\closing{Mit freundlichen Grüßen}

\end{letter}
\end{document}
""".replace("\\x01", F)),
]

# ---------------------------------------------------------------------------------------------------
# Anleitung (kurze Kapitel; einfache Auszeichnung: Zeilen mit "  " vorn = Code)
# ---------------------------------------------------------------------------------------------------
GUIDE = [
    ("Wie funktioniert LaTeX?",
     "Du schreibst keinen fertig formatierten Text wie in Word, sondern einen Quelltext mit Befehlen. "
     "Der Compiler macht daraus ein PDF – rechts siehst du es live.\n\n"
     "Befehle beginnen mit einem Backslash \\ und bekommen ihren Inhalt in geschweiften Klammern:\n"
     "  \\textbf{fett}\n"
     "Optionale Einstellungen stehen in eckigen Klammern:\n"
     "  \\documentclass[12pt]{article}"),
    ("Aufbau eines Dokuments",
     "Jedes Dokument hat zwei Teile:\n\n"
     "1. Die Präambel (vor \\begin{document}): Dokumentklasse, Pakete, Titel.\n"
     "2. Den Inhalt zwischen \\begin{document} und \\end{document}.\n\n"
     "  \\documentclass{article}\n  \\usepackage[ngerman]{babel}\n  \\begin{document}\n  Hallo Welt!\n  \\end{document}"),
    ("Absätze & Leerzeichen",
     "Ein einfacher Zeilenumbruch im Quelltext wird ignoriert. Eine leere Zeile beginnt einen neuen Absatz. "
     "Mehrere Leerzeichen zählen wie eins.\n\nErzwungener Zeilenumbruch: \\\\ (sparsam benutzen)."),
    ("Sonderzeichen",
     "Diese Zeichen haben in LaTeX eine Bedeutung und brauchen einen Backslash davor, wenn du sie drucken willst:\n"
     "  \\%  \\&  \\$  \\#  \\_  \\{  \\}\n"
     "Umlaute (ä, ö, ü, ß) kannst du ganz normal tippen. Deutsche Anführungszeichen: \\enquote{…} oder „…“ direkt."),
    ("Umgebungen",
     "Manche Dinge haben einen Anfang und ein Ende – das sind Umgebungen:\n"
     "  \\begin{itemize}\n    \\item Punkt\n  \\end{itemize}\n"
     "Tipp: Tippe \\begin{itemize} und drück Enter – das passende \\end ergänzt notist automatisch."),
    ("Mathe",
     "Formeln im Text stehen zwischen $…$, abgesetzte Formeln zwischen \\[ und \\].\n"
     "  $x^2$   hochgestellt\n  $x_1$   tiefgestellt\n  $\\frac{1}{2}$   Bruch\n  $\\sqrt{x}$   Wurzel\n"
     "Mehr als ein Zeichen hoch/tief? Klammern: $x^{10}$."),
    ("Bilder",
     "Über „Einfügen → Bild“ wählst du eine Datei. notist kopiert sie in den Projektordner dieses Dokuments "
     "und setzt den passenden Code ein – inklusive \\usepackage{graphicx}, falls es fehlt."),
    ("Pakete",
     "Pakete erweitern LaTeX. Sie werden in der Präambel geladen:\n  \\usepackage{amsmath}\n"
     "Wenn du einen Vorschlag übernimmst, der ein Paket braucht, ergänzt notist die Zeile automatisch. "
     "Mit Tectonic werden fehlende Pakete beim ersten Kompilieren aus dem Internet geladen."),
    ("Fehler lesen",
     "Wenn etwas nicht klappt, erscheint unten eine Liste mit Fehlern – auf Deutsch erklärt. "
     "Ein Klick springt in die Zeile. Häufigste Ursachen:\n"
     "• Tippfehler im Befehlsnamen\n• vergessene } oder $\n• Sonderzeichen wie % oder & ohne \\\n"
     "Oft reicht es, den ersten Fehler zu beheben – die anderen sind Folgefehler."),
    ("Tastenkürzel",
     "  Strg+S / Strg+Enter   jetzt kompilieren\n  Strg+Leertaste   Vorschläge zeigen\n"
     "  Tab   Vorschlag übernehmen / nächstes Feld\n  Esc   Vorschläge schließen\n"
     "  Strg+B / Strg+I   fett / kursiv um die Markierung\n  Strg+M   Formel $…$ um die Markierung\n"
     "  Strg+7   Zeilen aus- oder einkommentieren\n  Strg+F   Suchen"),
]

# ---------------------------------------------------------------------------------------------------
# Fehlermeldungen → Deutsch
# ---------------------------------------------------------------------------------------------------
ERRORS = [
    (r"Undefined control sequence", "Unbekannter Befehl",
     "Diesen Befehl kennt LaTeX nicht. Tippfehler? Oder fehlt ein \\usepackage für den Befehl?"),
    (r"Missing \$ inserted", "Mathe außerhalb von $…$",
     "Ein Mathe-Zeichen (z. B. ^, _ oder \\frac) steht außerhalb einer Formel – oder ein $ fehlt. "
     "Setze die Formel in $…$. Ein Unterstrich im Text muss \\_ sein."),
    (r"Missing \} inserted", "Schließende Klammer fehlt", "Zu einer { fehlt das passende }."),
    (r"Missing \{ inserted", "Öffnende Klammer fehlt", "Hier erwartet LaTeX eine {."),
    (r"Too many \}'s|Extra \}, or forgotten", "Eine } zu viel", "Es gibt eine schließende Klammer ohne passende öffnende."),
    (r"Extra alignment tab has been changed", "Zu viele Spalten",
     "In dieser Tabellenzeile stehen mehr & als die Tabelle Spalten hat. Prüfe {lll} beim \\begin{tabular}."),
    (r"Misplaced alignment tab character &", "& an falscher Stelle",
     "Das & trennt nur in Tabellen/align Zellen. Im Text schreibst du \\&."),
    (r"Environment (\S+) undefined", "Unbekannte Umgebung",
     "Diese Umgebung gibt es nicht – Tippfehler oder fehlendes Paket (z. B. amsmath für align)."),
    (r"\\begin\{(\S+)\} on input line \d+ ended by \\end\{(\S+)\}|\\begin\{(\S+)\} ended by \\end", "Begin/End passen nicht",
     "Ein \\begin{…} wird mit einem anderen \\end{…} geschlossen. Prüfe, ob alle Umgebungen in der richtigen Reihenfolge enden."),
    (r"\\begin\{document\} ended by|ended by \\end\{document\}|Emergency stop.*\*\*\* \(job aborted, no legal \\end found\)",
     "Umgebung nicht geschlossen", "Eine Umgebung wurde vor \\end{document} nicht mit \\end{…} beendet."),
    (r"File `([^']+)' not found|File '([^']+)' not found|not found: (\S+)", "Datei nicht gefunden",
     "Die Datei (Paket oder Bild) wurde nicht gefunden. Bilder müssen im Projektordner liegen – nutze „Einfügen → Bild“."),
    (r"Missing \\begin\{document\}", "\\begin{document} fehlt",
     "Text steht schon in der Präambel, oder \\begin{document} fehlt ganz. Alles Sichtbare gehört hinter \\begin{document}."),
    (r"Can be used only in preamble", "Nur in der Präambel erlaubt",
     "Dieser Befehl (z. B. \\usepackage) muss vor \\begin{document} stehen."),
    (r"There's no line here to end", "Zeilenumbruch ohne Zeile",
     "\\\\ steht am Anfang eines Absatzes oder nach einer Leerzeile. Für Abstand lieber \\vspace{…} nehmen."),
    (r"Paragraph ended before (\S+) was complete", "Leerzeile in einem Befehl",
     "Innerhalb der {…} eines Befehls ist eine Leerzeile – oder eine } fehlt."),
    (r"Missing number, treated as zero", "Zahl erwartet",
     "Hier erwartet LaTeX eine Zahl oder Länge (z. B. 2cm). Oft steht ein [ direkt nach \\\\ in einer Tabelle."),
    (r"Illegal unit of measure", "Ungültige Einheit", "Längen brauchen eine Einheit: cm, mm, pt, em oder \\textwidth."),
    (r"Double (subscript|superscript)", "Doppelt hoch-/tiefgestellt",
     "Zwei ^ oder _ hintereinander. Klammere: x^{a^b} statt x^a^b."),
    (r"Display math should end with \$\$|Bad math environment delimiter", "Formel falsch beendet",
     "Eine abgesetzte Formel wurde nicht richtig geschlossen. \\[ braucht \\], $$ braucht $$."),
    (r"Option clash for package (\S+)", "Paket doppelt geladen", "Das Paket wurde zweimal mit verschiedenen Optionen geladen."),
    (r"LaTeX Error: Unknown option", "Unbekannte Option", "Eine Option in [ ] kennt das Paket oder die Klasse nicht."),
    (r"Lonely \\item|Something's wrong--perhaps a missing \\item", "\\item außerhalb einer Liste",
     "\\item darf nur in itemize, enumerate oder description stehen."),
    (r"Runaway argument", "Klammer nicht geschlossen", "Ein Befehl wurde mit { geöffnet, aber nicht geschlossen."),
    (r"Text line contains an invalid character", "Ungültiges Zeichen", "Ein unsichtbares oder kaputtes Zeichen steckt im Text."),
    (r"allowed only in math mode", "Nur in Formeln erlaubt",
     "Dieser Befehl funktioniert nur zwischen $…$ (oder in \\[ … \\]). Setze ihn in eine Formel."),
    (r"Command \\\S+ already defined", "Befehl doppelt definiert",
     "Ein \\newcommand benutzt einen Namen, den es schon gibt – nimm einen anderen oder \\renewcommand."),
    (r"Package (\w+) Error", "Fehler in einem Paket", "Ein geladenes Paket meldet ein Problem. Der Text daneben sagt meist, was fehlt."),
    (r"Not in outer par mode", "Gleitobjekt an falscher Stelle",
     "figure/table darf nicht in einer anderen Box oder Liste stecken."),
    (r"Undefined color", "Unbekannte Farbe", "Diese Farbe kennt xcolor nicht. Probiere red, blue, green, orange, gray."),
    (r"Unicode character (.) \(U\+\w+\)", "Zeichen nicht darstellbar",
     "Dieses Sonderzeichen kann die gewählte Schrift nicht. Mit Tectonic (XeTeX) klappt das meist direkt."),
]
WARNINGS = [
    (r"Reference `([^']+)' on page \d+ undefined", "Verweis fehlt",
     "Ein \\ref zeigt auf ein \\label, das es (noch) nicht gibt. Tippfehler im Namen?"),
    (r"Citation `([^']+)' on page \d+ undefined|Citation `([^']+)' undefined", "Quelle fehlt",
     "\\cite verweist auf einen Schlüssel, der im Literaturverzeichnis fehlt."),
    (r"There were undefined references", "Verweise noch offen", "Nochmal kompilieren kann helfen."),
    (r"Label `([^']+)' multiply defined", "Label doppelt", "Zwei \\label haben denselben Namen."),
    (r"Overfull \\hbox", "Zeile zu lang", "Etwas ragt über den Rand hinaus (oft ein langes Wort, Link oder Bild)."),
]


def explain(msg, warning=False):
    for pat, title, text in (WARNINGS if warning else ERRORS):
        if re.search(pat, msg):
            return title, text
    return None


def body_text(src):
    """Lesbarer Ausschnitt eines LaTeX-Quelltexts (für Listen-Vorschau und Suche)."""
    src = re.sub(r"(?<!\\)%.*", "", src)
    m = re.search(r"\\begin\{document\}(.*)", src, re.S)
    s = m.group(1) if m else src
    s = re.sub(r"\\(begin|end)\{[^}]*\}(\[[^\]]*\]|\{[^}]*\})*", " ", s)
    s = re.sub(r"\\(maketitle|tableofcontents|newpage|clearpage|centering|item|today|hline|noindent)\b", " ", s)
    s = re.sub(r"\\[A-Za-z@]+\*?(\[[^\]]*\])?", " ", s)
    s = re.sub(r"[{}$\\&~^_]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def doc_title(src):
    m = re.search(r"\\title\{([^}]*)\}", src)
    if m:
        t = re.sub(r"\\[A-Za-z]+\*?", "", m.group(1)).replace("{", "").replace("}", "").strip()
        return t
    return ""


# ---------------------------------------------------------------------------------------------------
# Englische Vorlagen (Oberfläche auf English)
# ---------------------------------------------------------------------------------------------------
TEMPLATES_EN = [
    ("lernen", "󰑴", "Learn LaTeX", "A practice document that shows you the basics step by step",
     r"""% ===================================================================
% Welcome! This document explains LaTeX with examples.
% Everything after a % sign is a comment and does NOT appear in the PDF.
% On the right you see the result. Change something and watch.
% ===================================================================

% --- PART 1: The preamble ------------------------------------------
% Before \begin{document} you decide WHAT kind of document it is
% and which extra packages you need.
\documentclass[11pt]{article}   % article = short text, report, essay
\usepackage[english]{babel}      % hyphenation and words like "Contents"
\usepackage{amsmath}             % better math environments
\usepackage{graphicx}            % include images

\title{My first \LaTeX{} document}
\author{Your name}
\date{\today}

% --- PART 2: The content -------------------------------------------
\begin{document}

\maketitle   % prints title, author and date from above

\section{Writing text}
Normal text is just typed. A single line break
in the source changes nothing -- LaTeX breaks lines itself.

An empty line starts a new paragraph.
Use \textbf{bold}, \textit{italic} and \emph{emphasised} to format words.

\section{Lists}
\begin{itemize}
  \item One item
  \item Another item
\end{itemize}

\begin{enumerate}
  \item First
  \item Second
\end{enumerate}

\section{Math}
Formulas inside a sentence go between dollar signs: $a^2 + b^2 = c^2$.
A formula on its own line:
\[
  \int_0^1 x^2 \, dx = \frac{1}{3}
\]

\section{Your turn}
% Try it: write a subsection below with \subsection{...}
% Tip: type \sub -- suggestions appear. Press Tab to accept.


\end{document}
"""),
    ("artikel", "󰈙", "Simple document", "Empty document with sensible defaults",
     "\\documentclass[11pt,a4paper]{article}\n\\usepackage[english]{babel}\n\\usepackage{amsmath}\n\\usepackage{graphicx}\n\n"
     "\\title{" + F + "Title}\n\\author{Your name}\n\\date{\\today}\n\n\\begin{document}\n\n\\maketitle\n\n" + F + "\n\n\\end{document}\n"),
    ("hausarbeit", "󰂺", "Term paper", "Title page, table of contents, chapters, bibliography",
     r"""\documentclass[12pt,a4paper]{article}
\usepackage[english]{babel}
\usepackage[a4paper, margin=2.5cm]{geometry}  % page margins
\usepackage{setspace}                          % line spacing
\onehalfspacing                                % 1.5 line spacing
\usepackage{amsmath}
\usepackage{graphicx}
\usepackage{csquotes}
\usepackage[hidelinks]{hyperref}               % clickable references in the PDF

\begin{document}

% ---------- Title page ----------
\begin{titlepage}
  \centering
  {\Large University / School\par}
  \vspace{2cm}
  {\huge\bfseries \x01Title of the paper\par}
  \vspace{1cm}
  {\large Term paper in …\par}
  \vfill
  Submitted by: Your name\\
  Student ID: 123456\\
  Date: \today
\end{titlepage}

\tableofcontents
\newpage

\section{Introduction}
\x01

\section{Main part}
\subsection{First point}
As \enquote{Miller} writes \cite{miller2020}, …

\section{Conclusion}

% ---------- Bibliography ----------
\begin{thebibliography}{9}
  \bibitem{miller2020} Miller, A. (2020): \textit{A book title}. Publisher, City.
\end{thebibliography}

\end{document}
""".replace("\\x01", F)),
    ("mathe", "󰿈", "Math & exercise sheet", "Exercises with formulas, space for solutions",
     r"""\documentclass[11pt,a4paper]{article}
\usepackage[english]{babel}
\usepackage[a4paper, margin=2cm]{geometry}
\usepackage{amsmath, amssymb}

\title{Exercise sheet \x01 1}
\author{Name}
\date{\today}

\begin{document}
\maketitle

\section*{Exercise 1}
Compute $\displaystyle\lim_{x \to 0} \frac{\sin x}{x}$.

\section*{Exercise 2}
Solve the system of equations:
\begin{align*}
  2x + 3y &= 7 \\
  x - y   &= 1
\end{align*}

\section*{Solution}
\x01

\end{document}
""".replace("\\x01", F)),
    ("praesentation", "󰐩", "Presentation", "Slides with beamer",
     r"""\documentclass{beamer}
\usepackage[english]{babel}
\usetheme{Madrid}      % other themes: Berlin, Copenhagen, metropolis …

\title{\x01Title of the presentation}
\author{Your name}
\date{\today}

\begin{document}

\begin{frame}
  \titlepage
\end{frame}

\begin{frame}{Outline}
  \tableofcontents
\end{frame}

\section{Introduction}
\begin{frame}{First slide}
  \begin{itemize}
    \item \x01
    \item Second point
  \end{itemize}
\end{frame}

\end{document}
""".replace("\\x01", F)),
    ("brief", "󰇮", "Letter", "A formal letter (KOMA-Script)",
     r"""\documentclass[paper=a4, fromalign=right, parskip=half]{scrlttr2}
\usepackage[english]{babel}

\setkomavar{fromname}{Your name}
\setkomavar{fromaddress}{Street 1\\City 12345}
\setkomavar{date}{\today}
\setkomavar{subject}{\x01Subject}

\begin{document}
\begin{letter}{Recipient\\Street 2\\Town 54321}

\opening{Dear Sir or Madam,}

\x01

\closing{Kind regards}

\end{letter}
\end{document}
""".replace("\\x01", F)),
]


def localize(lang):
    """Vorlagen in der Sprache der Oberfläche (Erklärtexte übersetzt die Oberfläche selbst)."""
    global TEMPLATES
    if lang == "en":
        TEMPLATES = TEMPLATES_EN
