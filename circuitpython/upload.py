# Laedt Dateien per serieller REPL auf ein CircuitPython-Board ohne USB-Laufwerk (z.B. ESP32-C6)
# Aufruf: uv run --no-project --with pyserial python upload.py /dev/ttyACM0 code.py rc522.py
import sys
import time
import serial


def run(s, cmd, wait=0.3):
    s.write(cmd.encode() + b"\r\n")
    time.sleep(wait)
    return s.read(s.in_waiting or 1).decode(errors="replace")


port, files = sys.argv[1], sys.argv[2:]
s = serial.Serial(port, 115200, timeout=0.5)
s.write(b"\x03\x03")
time.sleep(0.5)
s.write(b"\r\n")
time.sleep(1)
s.read(s.in_waiting or 1)

out = run(s, "import storage; storage.remount('/', readonly=False)", 0.5)
if "Traceback" in out:
    print(out)
    sys.exit(1)

for name in files:
    data = open(name, "rb").read()
    run(s, "f = open('/%s', 'wb')" % name)
    for i in range(0, len(data), 256):
        out = run(s, "f.write(%r)" % data[i:i + 256], 0.05)
        if "Traceback" in out:
            print(out)
            sys.exit(1)
    run(s, "f.close()")
    print("%s: %d Byte geschrieben" % (name, len(data)))

print(run(s, "import os; print(os.listdir('/'))", 0.5))
s.write(b"\x04")  # Soft-Reboot -> code.py startet
time.sleep(4)
print(s.read(s.in_waiting or 1).decode(errors="replace"))
