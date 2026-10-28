# Tagged!-Spielserver: Stationen melden Kartenscans, der Server verteilt Teams, verwaltet Stationen und Punkte.
# Nur Python-Standardbibliothek. Lokal: uv run --no-project python server/tagged_server.py --port 8080
# Umgebung: TAGGED_TOKEN (Stationen, ?token=...), TAGGED_ADMIN (Steuerung, Header X-Admin). Leer = ohne Schutz.
import argparse
import json
import os
import random
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
TOKEN = os.environ.get("TAGGED_TOKEN", "")
ADMIN = os.environ.get("TAGGED_ADMIN", "")

# Name (fuer Anzeige und Sprachausgabe, daher echte Umlaute) und LED-Farbe
TEAMS = [("Rot", (255, 0, 0)), ("Blau", (0, 0, 255)), ("Grün", (0, 255, 0)), ("Gelb", (255, 160, 0))]
STATIONS = 5
OFFLINE_AFTER = 6.0  # Sekunden ohne Abfrage -> Station gilt als offline
MAX_EVENTS = 50
MIME = {".html": "text/html; charset=utf-8", ".ttf": "font/ttf", ".js": "text/javascript", ".css": "text/css"}


class Game:
    def __init__(self):
        self.lock = threading.RLock()
        self.duration = 600  # Sekunden
        self.cooldown = 20  # Sperrzeit nach Eroberung
        self.n_teams = 2
        self.autostart = True  # erster Scan in der Lobby startet das Spiel
        self.last_seen = [0.0] * STATIONS
        self.events = []
        self.event_id = 0
        self.reset()

    # ---- Hilfen ------------------------------------------------------------------------------------------------
    @property
    def max_team(self):
        return max(1, STATIONS - 2)

    def team_info(self, t):
        name, color = TEAMS[t]
        return {"team": name, "color": list(color)}

    def event(self, text, kind="info"):
        self.event_id += 1
        self.events.append({"id": self.event_id, "t": time.time(), "text": text, "kind": kind})
        del self.events[:-MAX_EVENTS]
        print("[%s] %s" % (kind, text), flush=True)

    def remaining(self):
        if self.phase == "running":
            return max(0.0, self.end_at - time.monotonic())
        if self.phase == "lobby":
            return float(self.duration)
        return 0.0

    def dominator(self):
        """Team, das alle Stationen haelt, sonst None."""
        o = self.owner[0]
        return o if o is not None and all(x == o for x in self.owner) else None

    def all_claimed(self):
        return all(x is not None for x in self.owner)

    def winner(self):
        if self.phase != "over" or not any(self.scores):
            return None
        best = max(self.scores)
        top = [t for t, s in enumerate(self.scores) if s == best]
        return top[0] if len(top) == 1 else None  # Gleichstand -> kein Sieger

    # ---- Spielablauf -------------------------------------------------------------------------------------------
    def reset(self):
        with self.lock:
            self.phase = "lobby"
            self.cards = {}  # UID -> Team
            self.owner = [None] * STATIONS
            self.locked_until = [0.0] * STATIONS
            self.scores = [0] * self.n_teams
            self.end_at = None
            self.was_all_claimed = False
            self.was_dominator = None

    def start(self):
        with self.lock:
            self.phase = "running"
            self.owner = [None] * STATIONS
            self.locked_until = [0.0] * STATIONS
            self.scores = [0] * self.n_teams
            self.end_at = time.monotonic() + self.duration
            self.was_all_claimed = False
            self.was_dominator = None
            m = round(self.duration / 60)
            self.event("Das Spiel beginnt! %d %s" % (m, "Minute" if m == 1 else "Minuten"), "start")

    def stop(self):
        with self.lock:
            if self.phase != "running":
                return
            self.phase = "over"
            w = self.winner()
            if w is None:
                self.event("Spielende. Unentschieden!", "over")
            else:
                self.event("Spielende. Team %s gewinnt!" % TEAMS[w][0], "over")

    def tick(self):
        with self.lock:
            if self.phase != "running":
                return
            if time.monotonic() >= self.end_at:
                self.stop()
                return
            if not self.all_claimed():
                return
            dom = self.dominator()
            for t in self.owner:
                self.scores[t] += 2 if t == dom else 1

    def check_board(self):
        """Ereignisse fuer 'alle Stationen erobert' und Dominanz."""
        if self.all_claimed() and not self.was_all_claimed:
            self.event("Alle Stationen sind erobert. Die Punkte zählen!", "claimed")
        self.was_all_claimed = self.was_all_claimed or self.all_claimed()
        dom = self.dominator()
        if dom is not None and dom != self.was_dominator:
            self.event("Team %s hält alle Stationen!" % TEAMS[dom][0], "domination")
        self.was_dominator = dom

    def scan(self, box, uid):
        with self.lock:
            i = box - 1
            self.last_seen[i] = time.monotonic()
            if self.phase == "over":  # nur Rueckmeldung, Spielstand bleibt bis "Neues Spiel"
                t = self.cards.get(uid)
                res = self.team_info(t) if t is not None else {}
                res["result"] = "over"
                return res
            team = self.cards.get(uid)
            assigned = False
            if team is None:
                counts = [0] * self.n_teams
                for t in self.cards.values():
                    counts[t] += 1
                if min(counts) >= self.max_team:
                    return {"result": "full"}
                team = random.choice([t for t, c in enumerate(counts) if c == min(counts)])
                self.cards[uid] = team
                assigned = True
                self.event("Neue Karte ist jetzt Team %s" % TEAMS[team][0], "card")
            res = self.team_info(team)
            res["captured"] = False
            if self.phase == "lobby" and self.autostart:
                self.start()
            if self.phase != "running":
                res["result"] = "assigned" if assigned else "team"
                return res
            now = time.monotonic()
            if self.owner[i] == team:
                res["result"] = "assigned" if assigned else "own"
            elif now < self.locked_until[i]:
                res["result"] = "assigned" if assigned else "locked"
                res["lock_left"] = round(self.locked_until[i] - now, 1)
            else:
                self.owner[i] = team
                self.locked_until[i] = now + self.cooldown
                res["captured"] = True
                res["result"] = "assigned" if assigned else "captured"
                self.event("Station %d ist jetzt %s" % (box, TEAMS[team][0].lower()), "capture")
                self.check_board()
            return res

    def station(self, box):
        with self.lock:
            i = box - 1
            self.last_seen[i] = time.monotonic()
            o = self.owner[i]
            dom = self.dominator()
            w = self.winner()
            return {
                "phase": self.phase,
                "owner": list(TEAMS[o][1]) if o is not None else None,
                "domination": self.phase == "running" and dom is not None,
                "all_claimed": self.all_claimed(),
                "lock_left": round(max(0.0, self.locked_until[i] - time.monotonic()), 1),
                "winner": list(TEAMS[w][1]) if w is not None else None,
                "remaining": round(self.remaining()),
            }

    def state(self):
        with self.lock:
            now = time.monotonic()
            members = [0] * self.n_teams
            for t in self.cards.values():
                members[t] += 1
            dom = self.dominator()
            w = self.winner()
            return {
                "phase": self.phase,
                "remaining": round(self.remaining(), 1),
                "duration": self.duration,
                "cooldown": self.cooldown,
                "autostart": self.autostart,
                "n_teams": self.n_teams,
                "max_team": self.max_team,
                "teams": [dict(self.team_info(t), score=self.scores[t], members=members[t]) for t in range(self.n_teams)],
                "stations": [{
                    "box": i + 1,
                    "owner": self.owner[i],
                    "lock_left": round(max(0.0, self.locked_until[i] - now), 1),
                    "online": self.last_seen[i] > 0 and now - self.last_seen[i] < OFFLINE_AFTER,
                } for i in range(STATIONS)],
                "all_claimed": self.all_claimed(),
                "domination": dom if self.phase == "running" else None,
                "winner": w,
                "cards": len(self.cards),
                "events": self.events,
            }

    def control(self, data):
        with self.lock:
            if "duration" in data:
                self.duration = max(60, min(3600, int(data["duration"])))
            if "autostart" in data:
                self.autostart = bool(data["autostart"])
            if "cooldown" in data:
                self.cooldown = max(0, min(300, int(data["cooldown"])))
            action = data.get("action")
            if action == "reset":
                if "teams" in data:
                    self.n_teams = max(2, min(len(TEAMS), int(data["teams"])))
                self.reset()
                self.event("Neues Spiel vorbereitet, alle Karten sind frei", "reset")
            elif action == "start":
                self.start()
            elif action == "stop":
                self.stop()


game = Game()


def ticker():
    while True:
        time.sleep(1.0)
        game.tick()


class Handler(BaseHTTPRequestHandler):
    server_version = "Tagged/1"

    def log_message(self, fmt, *args):
        pass  # Stationen fragen jede Sekunde, das waere zu viel Ausgabe

    def send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def box_arg(self, q):
        try:
            box = int(q.get("box", ["0"])[0])
        except ValueError:
            return None
        return box if 1 <= box <= STATIONS else None

    def do_GET(self):
        url = urlparse(self.path)
        q = parse_qs(url.query)
        if url.path in ("/api/scan", "/api/station"):
            if TOKEN and q.get("token", [""])[0] != TOKEN:
                return self.send(403, {"error": "token"})
            box = self.box_arg(q)
            if box is None:
                return self.send(400, {"error": "box"})
            if url.path == "/api/station":
                return self.send(200, game.station(box))
            uid = q.get("uid", [""])[0].upper()
            if not uid or not all(c in "0123456789ABCDEF" for c in uid):
                return self.send(400, {"error": "uid"})
            return self.send(200, game.scan(box, uid))
        if url.path == "/api/state":
            return self.send(200, game.state())
        name = "index.html" if url.path == "/" else url.path.lstrip("/")
        if name in os.listdir(STATIC):  # nur Dateien direkt in static/, kein Pfad
            with open(os.path.join(STATIC, name), "rb") as f:
                return self.send(200, f.read(), MIME.get(os.path.splitext(name)[1], "application/octet-stream"))
        self.send(404, {"error": "not found"})

    def do_POST(self):
        if urlparse(self.path).path != "/api/control":
            return self.send(404, {"error": "not found"})
        if ADMIN and self.headers.get("X-Admin", "") != ADMIN:
            return self.send(403, {"error": "admin"})
        try:
            n = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(n) or b"{}")
            game.control(data)
        except (ValueError, TypeError) as e:
            return self.send(400, {"error": str(e)})
        self.send(200, game.state())


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=8080)
    p.add_argument("--host", default="0.0.0.0")
    a = p.parse_args()
    threading.Thread(target=ticker, daemon=True).start()
    print("Tagged!-Server auf %s:%d (Token %s, Admin %s)" % (
        a.host, a.port, "an" if TOKEN else "aus", "an" if ADMIN else "aus"), flush=True)
    ThreadingHTTPServer((a.host, a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
