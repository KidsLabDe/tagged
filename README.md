# Tagged!

RFID-Station für Spiele im KidsLab: Karte an die Disc halten, die Station erkennt sie und leuchtet.

## Hardware

- ESP32-Board mit CircuitPython (Gehäuse: ESP32-C6 Super Mini mit Laderegler, Akku-Pads auf der Unterseite; getestet außerdem: Waveshare ESP32-C6-Zero, Lolin S2 Mini)
- RC522 RFID-Leser (13,56 MHz, ISO14443A)
- 18650-Akku mit direkt angelöteten Kabeln, in zwei Klammern im Unterteil
- WS2812B-LED-Streifen (10 mm)
- KCD1-Wippschalter (Einbauöffnung 19,2 × 13 mm) in der Rückwand
- 4× M3-Gewindeeinsatz + M3×8 Senkkopfschraube

### Verkabelung

```
18650 (+) ── Schalter ──┬── BAT+ (Pad unten am C6 Super Mini)
                        └── LED-Streifen +
18650 (–) ──────────────┬── BAT– (Pad unten am C6 Super Mini)
                        └── LED-Streifen GND
```

- RC522 an 3V3 des ESP-Boards
- Der Schalter trennt den Akku ganz ab: Geladen wird über USB-C am Board nur, wenn er an ist

### Einbau

- **Akku:** Die Kabel direkt an die Zelle löten (Pole kurz anrauen, heißer Kolben, schnell arbeiten) und die Zelle von oben in die zwei Klammern drücken. Sie liegt quer auf dem Boden, Platz ist für Zellen bis etwa 75 mm.
- **C6 Super Mini:** Es gibt keinen Halter mehr, das Board wird mit Heißkleber fixiert, USB-C mittig in die Öffnung der unteren Wand. Die Öffnung ist 11 mm breit und reicht vom Boden bis unter die LED-Nut, damit das Board auch mit den Akku-Kabeln an den Pads unten noch passt. BAT+/BAT– vor dem Einkleben anlöten.
- **Schalter:** Er sitzt von hinten versenkt in einer 3 mm tiefen Mulde, damit er beim Aufhängen möglichst wenig aufliegt, und wird von hinten eingeklipst.
- **Aufhängen:** Oben sind zwei flache Haken in der Rückenebene, z. B. für zwei Nägel oder Schrauben (Schaft bis 5 mm). Alternativ geht eine Kordel durch das Loch oben.

RC522 und LEDs (`code.py`, Board über `TAGGED_BOARD` in `settings.toml` wählen):

| Bauteil | Lolin S2 Mini | ESP32-C6 Super Mini |
|---------|---------------|---------------------|
| RC522 SDA | IO12 | GPIO0 |
| RC522 SCK | IO7 | GPIO1 |
| RC522 MOSI | IO11 | GPIO2 |
| RC522 MISO | IO9 | GPIO3 |
| RC522 RST | IO5 | GPIO4 |
| RC522 3.3V | 3V3 | 3V3 |
| LED-Streifen DIN (25 LEDs im Kreis) | IO40 | GPIO20 |

Am C6 Super Mini liegen die RC522-Pins nebeneinander auf der Leiste mit TX/RX; auf der anderen Leiste liegen GND, 3V3 und GPIO20 (LEDs) direkt nebeneinander. GPIO8 (eingebaute RGB-LED), GPIO9 (BOOT) und GPIO15 (Status-LED) frei lassen. Die eingebaute RGB-LED schaltet `code.py` aus. In die DIN-Leitung am besten 330 Ω, am Streifenanfang einen Elko (100–470 µF) zwischen + und GND.

`kartentest.py` ist für den ESP32-C6-Zero (SDA IO0, SCK IO1, MOSI IO2, MISO IO3, RST IO4).

## Ordner

- `circuitpython/`: Firmware und Hilfsskripte
  - `code.py`: Spielstation: Regenbogen beim Start, dann zeigt der LED-Ring den Zustand vom Server, Karten-Scans gehen an den Server
  - `net.py`: minimaler HTTP-Client (Klartext-HTTP, JSON) für den Server
  - `settings.toml.example`: Vorlage für `settings.toml` auf dem Board (WLAN, Board-Typ, Box-Nummer, Server, Token)
  - `rc522.py`: minimaler RC522-Treiber
  - `kartentest.py`: zeigt UID und Kartentyp jeder erkannten Karte
  - `upload.py`: Dateien über die serielle REPL aufs Board laden (für Boards ohne USB-Laufwerk)
  - `log_serial.py`: serielle Ausgabe mitschreiben
- `server/`: Spielserver (Python, nur Standardbibliothek) mit Webansicht `static/index.html`, läuft als Docker-Container auf fangulus.kidslab.de
- `docker-compose.yml`, `.github/workflows/deploy.yml`: Deployment wie bei kidslab.de (Image auf GHCR, Traefik)
- `freecad/`: parametrisches Gehäuse
  - `disc_case.py`: in FreeCAD ausführen, erzeugt `DiscCase.FCStd`, STLs, 3MFs und Vorschaubilder
  - `group_3mf.py`: baut die Bambu-Studio-3MF (Deckel + Logo als ein Objekt, Logo auf Filament 2)
  - `DiscCase_Druck_Bambu.3mf`: druckfertig für Bambu Lab (X1C-Profil, Unterteil + zweifarbiger Deckel von Station 1)
  - `DiscCase_Unterteil.stl`: nur das Unterteil
  - `DiscCase_Front_1_Bambu.3mf` … `DiscCase_Front_5_Bambu.3mf`: nur der Deckel je Station („FANGULUS“ + Nummer 1–5), Logo auf Filament 2
  - `PixelifySans-Bold.ttf`: Schrift für alle Texte (Pixelify Sans, statische Bold-Instanz, SIL Open Font License)

## Spiel

Karten sind Spieler, Teams sind Farben, die 5 Stationen sind die „Türme“.

- **Teams:** Eine neue Karte kommt beim ersten Scan an irgendeiner Station ins Team mit den wenigsten Leuten (bei Gleichstand zufällig). Die Station blinkt 3× in der Teamfarbe. Pro Team dürfen höchstens Stationen − 2 Leute sein, also 3 bei 5 Stationen. Weitere Karten blinken 2× weiß.
- **Start:** Die erste Karte an einer Station startet das Spiel und erobert gleich diese Station (Autostart, in der Spielleitung abschaltbar, dann startet das Spiel per Knopf).
- **Erobern:** Im laufenden Spiel wechselt eine Station mit einer Karte des anderen Teams die Farbe, die Farbe läuft einmal um den Ring. Danach ist sie für die Sperrzeit (Standard 20 s) geschützt, ein Versuch flackert nur.
- **Punkte:** Erst wenn keine Station mehr neutral ist, bekommt jedes Team pro Sekunde 1 Punkt pro Station. Hält ein Team alle Stationen, zählt es doppelt, und alle Stationen pulsieren.
- **Ende:** Nach der Laufzeit (Standard 10 min) leuchten alle Stationen in der Siegerfarbe.

Anzeige am Ring: Lobby = weiß atmend, neutral = weißer Lauf, erobert = Lauf in Teamfarbe (langsam und gedimmt während der Sperre), kein Server = erste LED blinkt orange.

### Server

Die Webansicht unter https://fangulus.kidslab.de zeigt die Stationen, die Restzeit und die Punkte. Sie sagt Ereignisse an („Station 1 ist jetzt rot“), dafür einmal „Ton an“ drücken. Unter „Spielleitung“ werden Laufzeit, Sperrzeit, Teamzahl und Autostart eingestellt, außerdem gibt es Start, Stop und Neues Spiel. Dafür ist das Passwort `TAGGED_ADMIN` nötig.

Die Stationen sprechen Klartext-HTTP (Port 80) mit `?token=TAGGED_TOKEN`, die Webansicht läuft über HTTPS. Ein Push auf `main`, der `server/` ändert, baut das Image und deployt es nach `/opt/tagged`. Einmalig auf dem Server: `/opt/tagged/.env` mit `TAGGED_TOKEN=...` und `TAGGED_ADMIN=...` anlegen, im Repo die Secrets `SERVER_HOST`, `SERVER_USER` und `SERVER_SSH_KEY` setzen.

Lokal testen:

```sh
TAGGED_TOKEN=test uv run --no-project python server/tagged_server.py --port 8090
```

Dann auf den Boards `TAGGED_SERVER = "<IP des Laptops>:8090"` setzen.

## Firmware aufspielen

Der S2 Mini taucht mit CircuitPython als Laufwerk `CIRCUITPY` auf: `code.py`, `net.py` und `rc522.py` einfach draufkopieren, dazu eine `settings.toml` nach der Vorlage `settings.toml.example`. Alle Boxen haben dieselbe `code.py`, nur `TAGGED_BOX_ID` (und ggf. `TAGGED_BOARD`) unterscheidet sich. Die Helligkeit des LED-Rings stellt `TAGGED_BRIGHTNESS` in Prozent ein (Standard 25).
Für Boards ohne USB-Laufwerk (z. B. ESP32-C6):

```sh
cd circuitpython
uv run --no-project --with pyserial python upload.py /dev/ttyACM0 code.py net.py rc522.py settings.toml
```
