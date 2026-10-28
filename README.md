# Tagged!

RFID-Station für Spiele im KidsLab: Karte an die Disc halten, die Station erkennt sie und leuchtet.

## Hardware

- ESP32-Board mit CircuitPython (getestet: Waveshare ESP32-C6-Zero; Gehäuse hat Halter für Lolin S2 Mini)
- RC522 RFID-Leser (13,56 MHz, ISO14443A)
- TP4056-Lademodul mit Schutzschaltung (USB-C)
- 18650-Akku mit Halter
- WS2812B-LED-Streifen (10 mm)
- SS12D00-Schiebeschalter
- 4× M3-Gewindeeinsatz + M3×8 Senkkopfschraube

### Verkabelung

```
18650 (+) ── B+                OUT+ ── Schalter ──►|── 5V am ESP-Board   (Schottky 1N5817/SS14)
18650 (–) ── B-   [TP4056]     OUT- ─────────────────── GND am ESP-Board
```

- RC522 an 3V3 des ESP-Boards
- LED-Streifen: + an Akku-Plus hinter dem Schalter, GND an GND
- Die Diode verhindert, dass USB am ESP-Board den Akku direkt mit 5 V speist

RC522 an ESP32-C6-Zero:

| RC522 | ESP32-C6-Zero |
|-------|---------------|
| SDA   | IO0 |
| SCK   | IO1 |
| MOSI  | IO2 |
| MISO  | IO3 |
| RST   | IO4 |

## Ordner

- `circuitpython/`: Firmware (`code.py`, minimaler `rc522.py`-Treiber) und Hilfsskripte
  - `upload.py`: Dateien über die serielle REPL aufs Board laden (für Boards ohne USB-Laufwerk)
  - `log_serial.py`: serielle Ausgabe mitschreiben
- `freecad/`: parametrisches Gehäuse
  - `disc_case.py`: in FreeCAD ausführen, erzeugt `DiscCase.FCStd`, STLs, 3MFs und Vorschaubilder
  - `group_3mf.py`: baut die Bambu-Studio-3MF (Deckel + Logo als ein Objekt, Logo auf Filament 2)
  - `DiscCase_Druck_Bambu.3mf`: druckfertig für Bambu Lab (X1C-Profil, zweifarbiger Deckel)

## Firmware aufspielen

```sh
cd circuitpython
uv run --no-project --with pyserial python upload.py /dev/ttyACM0 code.py rc522.py
```
