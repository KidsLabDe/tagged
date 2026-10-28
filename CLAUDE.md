# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Firmware (`circuitpython/`)

- Läuft auf CircuitPython, nicht CPython: nur eingebaute Module (`board`, `busio`, `digitalio`, `neopixel_write`, ...), keine Bibliotheken aus dem Bundle. LEDs werden direkt über `neopixel_write` angesteuert, der RFID-Treiber ist der eigene `rc522.py`.
- `code.py` ist für den Lolin S2 Mini, `kartentest.py` für den ESP32-C6-Zero. Die Pins unterscheiden sich; die Tabelle steht im README.
- Hosttools (`upload.py`, `log_serial.py`) laufen mit `uv run --no-project --with pyserial python ...`.
- Aufgespielt wird seriell mit `upload.py` (siehe `/flash`). Tests gibt es nicht, geprüft wird auf dem Board über die serielle Ausgabe.

## Gehäuse (`freecad/`)

- `disc_case.py` läuft nur innerhalb von FreeCAD (über die FreeCAD MCP Bridge, siehe `/build-case`), nicht mit normalem `python3`.
- `OUT_DIR` ist ein absoluter Linux-Pfad des Rechners, auf dem FreeCAD läuft. Nicht auf Mac-Pfade umbiegen. `FONT` liegt im Repo (`PixelifySans-Bold.ttf`) und wird relativ zu `OUT_DIR` gefunden.
- STL, 3MF, `DiscCase.FCStd` und die Vorschau-PNGs sind generiert, aber eingecheckt: nach Änderungen an `disc_case.py` neu erzeugen und mit committen.
- `group_3mf.py` wird von `disc_case.py` aufgerufen und erwartet die Objektreihenfolge Unterteil, Deckel, Deckel_Logo.

## Konventionen

- Code-Kommentare und Ausgaben auf Deutsch mit ASCII-Umschrift (`ae`, `oe`, `ue`, `ss`); im README echte Umlaute.
- Hardware-Änderungen (Pins, Verkabelung, Bauteile) auch im README nachziehen.
- Commits direkt auf `main`, Commit-Messages auf Deutsch.
