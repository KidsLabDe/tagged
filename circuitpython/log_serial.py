# Schreibt die serielle Ausgabe des Boards zeilenweise nach stdout (fuer Logging/Monitor)
import sys
import serial

s = serial.Serial(sys.argv[1], 115200, timeout=1)
while True:
    line = s.readline()
    if line:
        print(line.decode(errors="replace").rstrip(), flush=True)
