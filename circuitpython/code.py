# Kartentest: zeigt fuer jede erkannte Karte UID, ATQA, SAK und den vermuteten Kartentyp
import time
import board
import busio
import digitalio
import neopixel_write
from rc522 import RC522

# Waveshare ESP32-C6-Zero -> RC522
PIN_SDA = board.IO0   # SDA = Chip Select
PIN_SCK = board.IO1
PIN_MOSI = board.IO2
PIN_MISO = board.IO3
PIN_RST = board.IO4

led = digitalio.DigitalInOut(board.NEOPIXEL)  # WS2812 auf GPIO8
led.switch_to_output()


def color(r, g, b):
    neopixel_write.neopixel_write(led, bytes((g, r, b)))


def hexs(data):
    return "".join("%02X" % b for b in data)


def mifare_type(atqa, sak):
    a = (atqa[1] << 8) | atqa[0]
    if sak == 0x09:
        return "MIFARE Mini"
    if sak == 0x08:
        return "MIFARE Classic 1K (z.B. S50)"
    if sak == 0x18:
        return "MIFARE Classic 4K (z.B. S70)"
    if sak == 0x88:
        return "MIFARE Classic 1K (Infineon)"
    if sak in (0x10, 0x11):
        return "MIFARE Plus (SL2)"
    if sak == 0x00:
        return "Ultralight / NTAG"
    if sak in (0x28, 0x38):
        return "Smartcard mit Classic-Emulation (SmartMX, ISO14443-4)"
    if sak & 0x20:
        if a == 0x0344:
            return "MIFARE DESFire (ISO14443-4)"
        return "ISO14443-4 Smartcard (Bankkarte, Handy, Ausweis, ...)"
    return "unbekannt"


def ntag_detail(rfid):
    v = rfid.command(b"\x60")  # GET_VERSION
    if not v or len(v) < 8:
        return "keine Antwort auf GET_VERSION (Ultralight / Ultralight C?)"
    product, size = v[2], v[6]
    if product == 0x04:
        names = {0x0F: "NTAG213 (144 Byte)", 0x11: "NTAG215 (504 Byte)", 0x13: "NTAG216 (888 Byte)"}
        return names.get(size, "NTAG, Groesse 0x%02X" % size)
    if product == 0x03:
        names = {0x0B: "Ultralight EV1 (48 Byte)", 0x0E: "Ultralight EV1 (128 Byte)"}
        return names.get(size, "Ultralight, Groesse 0x%02X" % size)
    return "GET_VERSION: " + hexs(v)


def iso4_detail(rfid):
    ats = rfid.command(b"\xE0\x50")  # RATS
    if not ats:
        return "keine Antwort auf RATS"
    text = "ATS " + hexs(ats)
    ver = rfid.command(b"\x02\x90\x60\x00\x00\x00")  # DESFire GetVersion als I-Block
    if ver and len(ver) >= 8 and ver[-2:] == b"\x91\xAF":
        hw_type, major, storage = ver[2], ver[4], ver[6]
        kind = {0x01: "DESFire", 0x08: "DESFire Light", 0x02: "MIFARE Plus"}.get(hw_type, "Typ 0x%02X" % hw_type)
        gen = {0x00: "EV0", 0x01: "EV1", 0x12: "EV2", 0x30: "EV3", 0x33: "EV3"}.get(major, "v%d" % major)
        size = {0x16: "2K", 0x18: "4K", 0x1A: "8K"}.get(storage, "")
        text += " | " + " ".join(s for s in (kind, gen, size) if s)
    rfid.command(b"\xC2")  # S(DESELECT)
    return text


spi = busio.SPI(PIN_SCK, MOSI=PIN_MOSI, MISO=PIN_MISO)
rfid = RC522(spi, PIN_SDA, PIN_RST)

v = rfid.version()
chips = {0x88: "FM17522 (Klon)", 0x90: "MFRC522 v0.0", 0x91: "MFRC522 v1.0", 0x92: "MFRC522 v2.0", 0x12: "Faelschung/Klon", 0xB2: "Klon"}
print()
print("RC522 Version: 0x%02X %s" % (v, chips.get(v, "")))
if v in (0x00, 0xFF):
    print("!!! Keine Verbindung zum RC522 - Verkabelung pruefen (MISO/MOSI, 3.3V, GND)")
    while True:
        color(40, 0, 0)
        time.sleep(0.5)
        color(0, 0, 0)
        time.sleep(0.5)

print("Bereit. Karte an den Leser halten...")
color(0, 0, 10)

last_uid = None
last_seen = 0
seen = {}

while True:
    atqa = rfid.wupa()
    if atqa is None:
        if last_uid and time.monotonic() - last_seen > 1.0:
            last_uid = None
            color(0, 0, 10)
        time.sleep(0.05)
        continue
    try:
        uid, sak = rfid.select()
    except Exception as e:
        print("Lesefehler:", type(e).__name__, e)
        rfid.halt()
        time.sleep(0.2)
        continue

    now = time.monotonic()
    if uid != last_uid:
        kind = mifare_type(atqa, sak)
        detail = ""
        if sak == 0x00:
            detail = ntag_detail(rfid)
        elif sak & 0x20:
            detail = iso4_detail(rfid)

        hint = ""
        if len(uid) == 4 and uid[0] == 0x08:
            hint = "  !!! ZUFAELLIGE UID - aendert sich bei jedem Auflegen, nicht als Spielerkarte geeignet"
        count = seen.get(uid, 0) + 1
        seen[uid] = count

        print("-" * 60)
        print("UID  %s (%d Byte)%s" % (hexs(uid), len(uid), "  [schon %dx gesehen]" % (count - 1) if count > 1 else ""))
        print("ATQA %s  SAK %02X  -> %s" % (hexs(bytes((atqa[1], atqa[0]))), sak, kind))
        if detail:
            print("     " + detail)
        if hint:
            print(hint)
        print("Verschiedene Karten bisher: %d" % len(seen))
        color(0, 30, 0) if not hint else color(30, 15, 0)
        last_uid = uid
    last_seen = now
    rfid.halt()
    time.sleep(0.1)
