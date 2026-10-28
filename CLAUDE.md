# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Firmware (`circuitpython/`)

- Läuft auf CircuitPython, nicht CPython: nur eingebaute Module (`board`, `busio`, `digitalio`, `neopixel_write`, ...), keine Bibliotheken aus dem Bundle. LEDs werden direkt über `neopixel_write` angesteuert, der RFID-Treiber ist der eigene `rc522.py`.
- `code.py` läuft auf Lolin S2 Mini und ESP32-C6 Super Mini. Einstellungen (`TAGGED_BOARD`, `TAGGED_BOX_ID`, `TAGGED_SERVER`, `TAGGED_TOKEN`, WLAN) kommen aus `settings.toml` auf dem Board (Vorlage `settings.toml.example`, die echte Datei nie einchecken). Pins stehen in `PINS` als GPIO-Nummern (`microcontroller.pin`, nicht `board`). `kartentest.py` ist für den ESP32-C6-Zero. Pin-Tabelle im README.
- `net.py` ist der eigene HTTP-Client (Klartext-GET, kein `adafruit_requests`).
- Hosttools (`upload.py`, `log_serial.py`) laufen mit `uv run --no-project --with pyserial python ...`.
- Aufgespielt wird seriell mit `upload.py` (siehe `/flash`). Tests gibt es nicht, geprüft wird auf dem Board über die serielle Ausgabe.

## Server (`server/`)

- `tagged_server.py` nutzt nur die Python-Standardbibliothek, der Spielzustand liegt im Speicher. Lokal: `TAGGED_TOKEN=test uv run --no-project python server/tagged_server.py --port 8090` (8080 ist auf dem Laptop belegt).
- Die Webansicht ist eine einzige Datei, `static/index.html`, ohne Build. Texte dort und in den Server-Ereignissen haben echte Umlaute, weil sie vorgelesen werden.
- Deployment über `.github/workflows/deploy.yml` nach `/opt/tagged` auf dem kidslab.de-Server (Traefik, Netzwerk `proxy`, wie `../kidslab.de`). Der HTTP-Router darf nicht auf HTTPS umleiten, weil die Stationen Klartext sprechen.

## Gehäuse (`freecad/`)

- `disc_case.py` läuft nur innerhalb von FreeCAD (über die FreeCAD MCP Bridge, siehe `/build-case`), nicht mit normalem `python3`.
- `OUT_DIR` ist ein absoluter Linux-Pfad des Rechners, auf dem FreeCAD läuft. Nicht auf Mac-Pfade umbiegen. `FONT` liegt im Repo (`PixelifySans-Bold.ttf`) und wird relativ zu `OUT_DIR` gefunden.
- STL, 3MF, `DiscCase.FCStd` und die Vorschau-PNGs sind generiert, aber eingecheckt: nach Änderungen an `disc_case.py` neu erzeugen und mit committen.
- `group_3mf.py` wird von `disc_case.py` aufgerufen und erwartet die Objektreihenfolge Unterteil, Deckel, Deckel_Logo.

## Konventionen

- Code-Kommentare und Ausgaben auf Deutsch mit ASCII-Umschrift (`ae`, `oe`, `ue`, `ss`); im README echte Umlaute.
- Hardware-Änderungen (Pins, Verkabelung, Bauteile) auch im README nachziehen.
- Commits direkt auf `main`, Commit-Messages auf Deutsch.
