# Laedt Dateien per serieller REPL auf ein CircuitPython-Board ohne USB-Laufwerk (z.B. ESP32-C6)
# Aufruf: uv run --no-project --with pyserial python upload.py /dev/ttyACM0 code.py rc522.py
import os
import sys
import time
import serial


def run(s, cmd, wait=0.3):
    s.write(cmd.encode() + b"\r\n")
    time.sleep(wait)
    return s.read(s.in_waiting or 1).decode(errors="replace")


def board_size(s, name):
    """Dateigroesse auf dem Board, -1 wenn die Datei fehlt."""
    out = run(s, "import os; print('GROESSE', os.stat('/%s')[6])" % name, 0.5)
    for line in out.splitlines():
        if line.startswith("GROESSE "):
            return int(line.split()[1])
    return -1


def write_file(s, name, data):
    run(s, "f = open('/%s', 'wb')" % name)
    for i in range(0, len(data), 256):
        out = run(s, "f.write(%r)" % data[i:i + 256], 0.05)
        if "Traceback" in out:
            print(out)
            sys.exit(1)
    run(s, "f.close()")


port, files = sys.argv[1], sys.argv[2:]
s = serial.Serial(port, 115200, timeout=0.5)
# laufende code.py abbrechen, bis die REPL antwortet
for _ in range(5):
    s.write(b"\x03")
    time.sleep(0.3)
    s.write(b"\r\n")
    time.sleep(0.7)
    if ">>>" in s.read(s.in_waiting or 1).decode(errors="replace"):
        break
else:
    print("Keine REPL erreicht")
    sys.exit(1)

out = run(s, "import storage; storage.remount('/', readonly=False)", 0.5)
if "Traceback" in out:
    print(out)
    sys.exit(1)

for path in files:
    name, data = os.path.basename(path), open(path, "rb").read()
    # Groesse auf dem Board pruefen, bei Abweichung einmal neu schreiben
    for _ in range(2):
        write_file(s, name, data)
        size = board_size(s, name)
        if size == len(data):
            break
    print("%s: %d Byte geschrieben, auf dem Board %d Byte" % (name, len(data), size))
    if size != len(data):
        print("!!! %s auf dem Board unvollstaendig" % name)
        sys.exit(1)

print(run(s, "import os; print(os.listdir('/'))", 0.5))
s.write(b"\x04")  # Soft-Reboot -> code.py startet
time.sleep(4)
print(s.read(s.in_waiting or 1).decode(errors="replace"))
