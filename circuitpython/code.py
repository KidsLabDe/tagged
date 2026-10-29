# Tagged!-Spielstation: Regenbogen beim Start, dann zeigt der LED-Ring den Zustand vom Server.
# Karte an den Leser -> Scan an den Server, die Antwort wird als Animation gezeigt.
# Laeuft auf dem Lolin S2 Mini und dem ESP32-C6 Super Mini. Einstellungen in settings.toml (siehe README).
import math
import os
import time
import busio
import digitalio
import microcontroller
import neopixel_write
import supervisor
from net import Net
from rc522 import RC522

# ---- Einstellungen: Standardwerte, settings.toml hat Vorrang --------------------------------------------------
BOARD = os.getenv("TAGGED_BOARD", "s2mini")  # "s2mini" (Lolin S2 Mini) oder "c6" (ESP32-C6 Super Mini)
BOX_ID = int(os.getenv("TAGGED_BOX_ID", 1))  # Nummer der Box (1-5), passend zur Ziffer auf dem Deckel
SERVER = os.getenv("TAGGED_SERVER", "fangulus.kidslab.de")  # Host, optional mit :Port
TOKEN = os.getenv("TAGGED_TOKEN", "")
BRIGHTNESS = int(os.getenv("TAGGED_BRIGHTNESS", 25)) / 100  # Prozent; 25 LEDs voll weiss waeren ~1.5 A
# --------------------------------------------------------------------------------------------------------------

# RC522 (SDA = Chip Select) und LED-Streifen je Board, als GPIO-Nummer
PINS = {
    "s2mini": {"sda": 12, "sck": 7, "mosi": 11, "miso": 9, "rst": 5, "leds": 40},  # Standard-SPI-Pins des S2 Mini
    "c6": {"sda": 0, "sck": 1, "mosi": 2, "miso": 3, "rst": 4, "leds": 20,  # RC522 linke Leiste, LEDs rechts neben 3V3
           "onboard_rgb": 8, "onboard_led": 15},  # eingebaute LEDs, werden ausgeschaltet
}
CHIP = {"s2mini": "ESP32S2", "c6": "ESP32C6"}


def gpio(name):
    return getattr(microcontroller.pin, "GPIO%d" % PINS[BOARD][name])


if BOARD not in PINS:
    raise ValueError("TAGGED_BOARD muss 's2mini' oder 'c6' sein, nicht %r" % BOARD)
if CHIP[BOARD] not in os.uname().machine.replace("-", "").upper():
    print("!!! TAGGED_BOARD = %r passt nicht zum Chip: %s" % (BOARD, os.uname().machine))
print("Tagged! Box %d auf %s, Server %s, Helligkeit %d%%" % (BOX_ID, BOARD, SERVER, BRIGHTNESS * 100))

NUM_LEDS = 25

SPIN_TIME = 1.6  # Sekunden pro Umlauf
TAIL = 10  # Laenge des Schweifs in LEDs
RAINBOW_TIME = 3.0  # Sekunden Regenbogen beim Start
RAINBOW_SPIN = 1.5  # Sekunden pro Umlauf des Regenbogens
CARD_GONE = 1.0  # so lange muss die Karte weg sein, bevor sie wieder ausloest
POLL_EVERY = 0.1  # Sekunden zwischen zwei Abfragen des Lesers
SERVER_EVERY = 2.0  # Sekunden zwischen zwei Abfragen des Servers
OFFLINE_AFTER = 3  # so viele Fehlversuche, bevor die Station "offline" zeigt

WHITE = (200, 200, 200)
ORANGE = (255, 80, 0)

def onboard_leds_off():
    """Eingebaute LEDs des Boards aus (C6 Super Mini: RGB auf GPIO8 zeigt sonst den CircuitPython-Status)."""
    supervisor.runtime.rgb_status_brightness = 0
    keep = []
    try:
        if "onboard_rgb" in PINS[BOARD]:
            p = digitalio.DigitalInOut(gpio("onboard_rgb"))
            p.switch_to_output()
            neopixel_write.neopixel_write(p, bytes(3))
            keep.append(p)
        if "onboard_led" in PINS[BOARD]:
            keep.append(digitalio.DigitalInOut(gpio("onboard_led")))
            keep[-1].switch_to_output(False)
    except Exception as e:
        print("Onboard-LEDs:", type(e).__name__, e)
    return keep  # Pins festhalten, sonst gibt CircuitPython sie wieder frei


onboard = onboard_leds_off()
pin = digitalio.DigitalInOut(gpio("leds"))
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


def scaled(c, k):
    return c[0] * k, c[1] * k, c[2] * k


def hue(h):
    """h in 0..1 -> (r, g, b) mit voller Saettigung"""
    h = (h % 1.0) * 6
    x = int(255 * (1 - abs(h % 2 - 1)))
    return ((255, x, 0), (x, 255, 0), (0, 255, x), (0, x, 255), (x, 0, 255), (255, 0, x))[int(h)]


def breath(t, period):
    """0..1..0 weich, quadratisch wirkt fuers Auge gleichmaessiger"""
    k = (1 - math.cos(2 * math.pi * t / period)) / 2
    return k * k


# ---- Daueranzeigen (ein Bild pro Aufruf) ----------------------------------------------------------------------
def spin_frame(t, color, spin=SPIN_TIME, gain=1.0):
    head = (t / spin % 1.0) * NUM_LEDS
    for i in range(NUM_LEDS):
        d = (head - i) % NUM_LEDS  # Abstand hinter dem Kopf
        if d < TAIL:
            set_led(i, *scaled(color, gain * (1 - d / TAIL) ** 2))
        else:
            set_led(i, 0, 0, 0)
    show()


def offline_frame(t):
    """Kein Server: erste LED blinkt orange."""
    for i in range(NUM_LEDS):
        set_led(i, 0, 0, 0)
    if t % 1.0 < 0.5:
        set_led(0, *ORANGE)
    show()


def frame(t, st):
    """Zeigt den Zustand vom Server: st ist die Antwort von /api/station oder None."""
    if st is None:
        spin_frame(t, WHITE, gain=0.3)  # verbinde noch
    elif st["phase"] == "lobby":
        fill(*scaled(WHITE, 0.1 + 0.4 * breath(t, 3.0)))
    elif st["phase"] == "over":
        if st["winner"]:
            fill(*st["winner"])
        else:  # Unentschieden: letzte eigene Farbe atmet langsam, neutral bleibt weiss
            fill(*scaled(st["owner"] or WHITE, 0.15 + 0.6 * breath(t, 3.0)))
    elif st["domination"]:
        fill(*scaled(st["owner"], 0.2 + 0.8 * breath(t, 0.5)))
    elif st["owner"] is None:
        spin_frame(t, WHITE)
    elif st["lock_left"] > 0:
        spin_frame(t, st["owner"], spin=SPIN_TIME * 2, gain=0.5)
    else:
        spin_frame(t, st["owner"])


# ---- Kurze Animationen als Antwort auf einen Scan --------------------------------------------------------------
def blink(color, n, period=0.6):
    start = time.monotonic()
    while True:
        t = time.monotonic() - start
        if t >= n * period:
            break
        fill(*scaled(color, breath(t, period)))
    fill(0, 0, 0)


def wave(color, duration=0.7):
    """Farbe laeuft einmal rundherum, dann einmal hell aufblitzen."""
    for i in range(NUM_LEDS):
        set_led(i, *color)
        show()
        time.sleep(duration / NUM_LEDS)
    blink(color, 1, 0.5)


def flicker(color, n=6):
    for _ in range(n):
        fill(*scaled(color, 0.6))
        time.sleep(0.05)
        fill(0, 0, 0)
        time.sleep(0.07)


def rainbow():
    """Regenbogen ueber den ganzen Ring, dreht sich RAINBOW_TIME lang und blendet am Ende aus."""
    start = time.monotonic()
    while True:
        t = time.monotonic() - start
        if t >= RAINBOW_TIME:
            break
        k = min(1.0, (RAINBOW_TIME - t) / 0.5)  # letzte halbe Sekunde ausblenden
        for i in range(NUM_LEDS):
            set_led(i, *scaled(hue(i / NUM_LEDS + t / RAINBOW_SPIN), k))
        show()
    fill(0, 0, 0)


def react(res):
    """Animation zur Antwort von /api/scan."""
    r = res["result"]
    color = res.get("color") or WHITE
    if r == "assigned":  # neue Karte: "du bist rot"
        blink(color, 3)
        if res.get("captured"):
            wave(color)
    elif r == "captured":
        wave(color)
    elif r in ("own", "team", "over"):
        blink(color, 1)
    elif r == "locked":
        flicker(color)
    elif r == "full":
        blink(WHITE, 2)


def hexs(data):
    return "".join("%02X" % b for b in data)


rainbow()

spi = busio.SPI(gpio("sck"), MOSI=gpio("mosi"), MISO=gpio("miso"))
rfid = RC522(spi, gpio("sda"), gpio("rst"))
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

net = Net(SERVER, TOKEN)
state = None
fails = 0
next_server = 0
print("Bereit. Karte an den Leser halten...")
last_uid = None
last_seen = 0
next_poll = 0

while True:
    now = time.monotonic()
    if fails >= OFFLINE_AFTER:
        offline_frame(now)
    else:
        frame(now, state)

    if now >= next_server:
        next_server = now + SERVER_EVERY
        try:
            state = net.get("/api/station", box=BOX_ID)
            if fails >= OFFLINE_AFTER:
                print("Server wieder erreichbar")
            fails = 0
        except Exception as e:
            fails += 1
            if fails == OFFLINE_AFTER:
                print("!!! Server nicht erreichbar:", type(e).__name__, e)

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
        try:
            res = net.get("/api/scan", box=BOX_ID, uid=hexs(uid))
            print("Server:", res)
            react(res)
        except Exception as e:
            print("!!! Scan nicht gesendet:", type(e).__name__, e)
            blink(ORANGE, 2)
        next_server = 0  # Zustand gleich neu holen
        last_uid = uid
    last_seen = time.monotonic()
