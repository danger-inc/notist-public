# Automatisches Formatieren beim Tippen (Notizen und Words) – alles einzeln abschaltbar (Mehr-Menü, Einstellungen):
#   typo     „Anführungszeichen“, -- → –, ... → …, -> → →, <- → ←, => → ⇒
#   autocap  erster Buchstabe eines Satzes groß
#   smart    Wort nach Leerzeichen/Satzzeichen korrigieren: SChreibstift → Schreibstift, hALLO → Hallo,
#            Tippfehler-Liste (teh → the, nciht → nicht, eigene in prefs["autocorrect"]), mit Wörterbuch:
#            vertauschte Buchstaben (Tset → Test), Nomen groß (schreibstift → Schreibstift).
#            Rücktaste direkt danach macht die Korrektur rückgängig (und das Wort bleibt dann in Ruhe).
# Dazu tidy(): Notiz einmal aufräumen (Leerzeichen am Zeilenende, doppelte Leerzeichen, zu viele Leerzeilen).
# Ersetzt wird im Leerlauf nach dem Einfügen (während des insert-text-Signals darf der Puffer nicht verändert werden).
import re


DEFAULTS = {"typo": True, "autocap": False, "smart": True}
PAIRS = (("...", "…"), ("--", "–"), ("->", "→"), ("<-", "←"), ("=>", "⇒"))
ABBR = re.compile(r"(?:^|\s)(?:z|d|u|bzw|ca|vgl|usw|etc|e|i|s|o|nr|dr|prof|bspw|ggf|evtl|inkl|max|min|"
                  r"z\. ?b|d\. ?h|u\. ?a|e\.g|i\.e)\.\s+$", re.I)
LIST_HEAD = re.compile(r"^\s*(?:[☐☑•▪◦-]\s+|\d+[.)]\s+|#+\s+|>\s+)?")


# Häufige Tippfehler (nur ganze Wörter, Groß-/Kleinschreibung am Anfang wird übernommen)
TYPOS = {
    # Deutsch
    "ncith": "nicht", "nciht": "nicht", "nicth": "nicht", "nihct": "nicht", "udn": "und",
    "dsa": "das", "dsas": "dass", "ihc": "ich", "icn": "ich", "acuh": "auch", "auhc": "auch", "shcon": "schon",
    "scohn": "schon", "nru": "nur", "imemr": "immer", "imer": "immer", "eigentlcih": "eigentlich",
    "eigendlich": "eigentlich", "vieleicht": "vielleicht", "vileicht": "vielleicht", "warscheinlich": "wahrscheinlich",
    "nähmlich": "nämlich", "wiederrum": "wiederum", "Addresse": "Adresse", "addresse": "Adresse",
    "Vorraussetzung": "Voraussetzung", "vorraus": "voraus", "agressiv": "aggressiv", "Rythmus": "Rhythmus",
    "Maschiene": "Maschine", "Gallerie": "Galerie", "Reperatur": "Reparatur",
    "seperat": "separat", "Interresse": "Interesse", "interresant": "interessant", "interessent": "interessant",
    "tortzdem": "trotzdem", "trozdem": "trotzdem", "zuende": "zu Ende",
    "garnicht": "gar nicht", "garkein": "gar kein",
    "Entgültig": "Endgültig", "entgültig": "endgültig",
    "wieviel": "wie viel", "Poltik": "Politik", "eien": "eine", "enie": "eine", "enen": "einen",
    "mti": "mit", "fpr": "für", "abre": "aber",
    # Englisch
    "teh": "the", "hte": "the", "adn": "and", "nad": "and", "taht": "that", "thta": "that", "waht": "what",
    "wich": "which", "whcih": "which", "recieve": "receive", "beleive": "believe", "seperate": "separate",
    "definately": "definitely", "definatly": "definitely", "occured": "occurred", "untill": "until",
    "becuase": "because", "becasue": "because", "wiht": "with", "thier": "their",
    "freind": "friend", "goverment": "government", "tommorow": "tomorrow", "tomorow": "tomorrow",
    "accomodate": "accommodate", "acheive": "achieve", "wierd": "weird", "alot": "a lot", "dont": "don’t",
    "doesnt": "doesn’t", "didnt": "didn’t", "isnt": "isn’t", "wasnt": "wasn’t",
    "youre": "you’re", "theyre": "they’re",
}
BOUNDARY = set(" \n\t.,;:!?)]}…\"“”»«")
WORD_END = re.compile(r"(?:^|[\s(\[{„“\"‚»«–—])([^\W\d_]{2,})$")
TWO_CAPS = re.compile(r"^[^\W\d_a-zäöüß]{2}[^\W\d_A-ZÄÖÜ]{2,}$")      # SChreibstift
CAPS_LOCK = re.compile(r"^[^\W\d_A-ZÄÖÜ][^\W\d_a-zäöüß]{2,}$")         # hALLO
_reverted = set()                 # nach Rücktaste: diese Wörter nicht wieder anfassen


def opt(prefs, key):
    return prefs.get("autofmt", {}).get(key, DEFAULTS[key])


def set_opt(prefs, key, on):
    prefs.setdefault("autofmt", {})[key] = bool(on)


def _swapped(a, b):
    """b entsteht aus a durch Vertauschen zweier benachbarter Buchstaben."""
    if len(a) != len(b) or a == b:
        return False
    diff = [i for i in range(len(a)) if a[i] != b[i]]
    return len(diff) == 2 and diff[1] == diff[0] + 1 and a[diff[0]] == b[diff[1]] and a[diff[1]] == b[diff[0]]


def _case_like(word, fix):
    return fix[:1].upper() + fix[1:] if word[:1].isupper() and not fix[:1].isupper() else fix


def correction(word, prefs, sp=None):
    """Smarte Korrektur für ein fertig getipptes Wort oder None. sp = spell.Speller (für die Wörterbuch-Regeln)."""
    if word in _reverted or len(word) < 2:
        return None
    own = prefs.get("autocorrect") or {}
    for table in (own, TYPOS):
        if word in table:
            return table[word] if table is own else _fix_quote(table[word], prefs)
        low = word[:1].lower() + word[1:]
        if low != word and low in table:
            return _case_like(word, table[low] if table is own else _fix_quote(table[low], prefs))
    known = sp.known if sp is not None and sp.available else None
    if TWO_CAPS.match(word) and not (known and known(word)):
        return word[0] + word[1:].lower()
    if CAPS_LOCK.match(word) and not (known and known(word)):
        return word[0].upper() + word[1:].lower()
    if not known or len(word) < 3 or word.isupper() or known(word):
        return None
    if word.islower() and "de" in getattr(sp, "codes", ()) and known(word.capitalize()):
        return word.capitalize()                     # schreibstift → Schreibstift
    if len(word) >= 4:
        for s in sp.suggest(word, 12):
            if _swapped(word, s):
                return s                             # Tset → Test
    return None


def _fix_quote(fix, prefs):
    return fix if opt(prefs, "typo") else fix.replace("’", "'")
