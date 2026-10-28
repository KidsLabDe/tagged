# Tagged! auf dem Lolin S2 Mini: rundlaufende Animation auf dem LED-Ring, Karte erkannt -> 5x rot atmen
import math
import time
import board
import busio
import digitalio
import neopixel_write
from rc522 import RC522

# Lolin S2 Mini -> RC522 (Standard-SPI-Pins des Boards)
PIN_SDA = board.IO12  # SDA = Chip Select
PIN_SCK = board.IO7
PIN_MOSI = board.IO11
PIN_MISO = board.IO9
PIN_RST = board.IO5

PIN_LEDS = board.IO40
NUM_LEDS = 25
BRIGHTNESS = 0.25  # 25 LEDs voll weiss waeren ~1.5 A, das schont Akku und Augen

SPIN_TIME = 1.6  # Sekunden pro Umlauf
TAIL = 10  # Laenge des Schweifs in LEDs
HUE_TIME = 20.0  # Sekunden fuer einmal durch den Farbkreis
BREATHS = 5
BREATH_TIME = 0.6  # Sekunden pro Atemzug
CARD_GONE = 1.0  # so lange muss die Karte weg sein, bevor sie wieder ausloest
POLL_EVERY = 0.1  # Sekunden zwischen zwei Abfragen des Lesers

pin = digitalio.DigitalInOut(PIN_LEDS)
pin.switch_to_output()
buf = bytearray(NUM_LEDS * 3)


def show():
    neopixel_write.neopixel_write(pin, buf)


def set_led(i, r, g, b):
    buf[i * 3] = int(g * BRIGHTNESS)  # WS2812B erwartet GRB
    buf[i * 3 + 1] = int(r * BRIGHTNESS)
    buf[i * 3 + 2] = int(b * BRIGHTNESS)


def fill(r, g, b):
    for i in range(NUM_LEDS):
        set_led(i, r, g, b)
    show()


def hue(h):
    """h in 0..1 -> (r, g, b) mit voller Saettigung"""
    h = (h % 1.0) * 6
    x = int(255 * (1 - abs(h % 2 - 1)))
    return ((255, x, 0), (x, 255, 0), (0, 255, x), (0, x, 255), (x, 0, 255), (255, 0, x))[int(h)]


def spin_frame(t):
    head = (t / SPIN_TIME % 1.0) * NUM_LEDS
    r, g, b = hue(t / HUE_TIME)
    for i in range(NUM_LEDS):
        d = (head - i) % NUM_LEDS  # Abstand hinter dem Kopf
        if d < TAIL:
            k = (1 - d / TAIL) ** 2
            set_led(i, r * k, g * k, b * k)
        else:
            set_led(i, 0, 0, 0)
    show()


def breathe_red():
    start = time.monotonic()
    while True:
        t = time.monotonic() - start
        if t >= BREATHS * BREATH_TIME:
            break
        k = (1 - math.cos(2 * math.pi * t / BREATH_TIME)) / 2
        fill(255 * k * k, 0, 0)  # quadratisch wirkt fuers Auge gleichmaessiger
    fill(0, 0, 0)


def hexs(data):
    return "".join("%02X" % b for b in data)


spi = busio.SPI(PIN_SCK, MOSI=PIN_MOSI, MISO=PIN_MISO)
rfid = RC522(spi, PIN_SDA, PIN_RST)
v = rfid.version()
print("RC522 Version: 0x%02X" % v)
if v in (0x00, 0xFF):
    print("!!! Keine Verbindung zum RC522 - Verkabelung pruefen (MISO/MOSI, 3.3V, GND)")
    while True:  # Fehler: erste LED blinkt rot
        set_led(0, 255, 0, 0)
        show()
        time.sleep(0.5)
        fill(0, 0, 0)
        time.sleep(0.5)

print("Bereit. Karte an den Leser halten...")
last_uid = None
last_seen = 0
next_poll = 0

while True:
    now = time.monotonic()
    spin_frame(now)
    if now < next_poll:
        continue
    next_poll = now + POLL_EVERY

    if rfid.wupa() is None:
        if last_uid and now - last_seen > CARD_GONE:
            last_uid = None
        continue
    try:
        uid, _ = rfid.select()
    except Exception as e:
        print("Lesefehler:", type(e).__name__, e)
        rfid.halt()
        continue
    rfid.halt()
    if uid != last_uid:
        print("Karte:", hexs(uid))
        breathe_red()
        last_uid = uid
    last_seen = time.monotonic()
