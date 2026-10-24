# Platz für den späteren Abgleich mit Google Keep. Noch nicht aktiv: get_backend() gibt None zurück.
#
# So würde es gehen:
# - Google bietet die offizielle Keep-API nur für Workspace-Firmenkonten an. Für ein privates
#   Google-Konto ist der übliche Weg die inoffizielle Bibliothek "gkeepapi" (Anmeldung über einen
#   sogenannten Master-Token, der sicher im Schlüsselbund liegen sollte, nicht in einer Datei).
# - Die Notiz-Felder in store.py heißen schon wie bei Keep: title, text, pinned, archived, trashed,
#   color, labels. Pro Notiz merkt sich sync.keep_id die Keep-ID und sync.dirty, ob es lokal
#   Änderungen gibt, die noch hochgeladen werden müssen.
# - Ablauf eines Abgleichs:
#     1. pull(): Keep-Notizen holen. Neue anlegen, geänderte übernehmen, wenn lokal nicht dirty.
#        Ist beides geändert, gewinnt die neuere ("updated" gegen keep_updated).
#     2. push(): alle dirty Notizen hochladen (auch trashed, damit Löschen ankommt),
#        danach keep_id/keep_updated setzen und dirty = False.


class SyncBackend:
    name = "Kein Abgleich"

    def pull(self, store):
        raise NotImplementedError

    def push(self, store):
        raise NotImplementedError


class KeepSync(SyncBackend):
    name = "Google Keep"

    def __init__(self, email, master_token):
        self.email, self.token = email, master_token

    def pull(self, store):
        raise NotImplementedError("Google-Keep-Abgleich ist noch nicht eingebaut")

    def push(self, store):
        raise NotImplementedError("Google-Keep-Abgleich ist noch nicht eingebaut")


def get_backend():
    return None
