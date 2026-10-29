# Minimaler HTTP-Client fuer den Tagged!-Server: nur GET, Klartext-HTTP/1.0, JSON-Antwort, ohne Bundle-Bibliotheken
import json
import os
import time
import socketpool
import wifi

TIMEOUT = 3.0  # Sekunden pro Anfrage (Server steht im Internet)
WIFI_TIMEOUT = 10  # Sekunden pro Verbindungsversuch mit einem WLAN
WIFI_RETRY = 15.0  # so lange warten, bevor ein fehlgeschlagenes WLAN neu versucht wird


def networks():
    """Bekannte WLANs aus settings.toml: erst CIRCUITPY_WIFI_SSID, dann TAGGED_WIFI_SSID_2, _3, ... (ohne Luecke)."""
    known = []
    if os.getenv("CIRCUITPY_WIFI_SSID"):
        known.append((os.getenv("CIRCUITPY_WIFI_SSID"), os.getenv("CIRCUITPY_WIFI_PASSWORD", "")))
    n = 2
    while os.getenv("TAGGED_WIFI_SSID_%d" % n):
        known.append((os.getenv("TAGGED_WIFI_SSID_%d" % n), os.getenv("TAGGED_WIFI_PASSWORD_%d" % n, "")))
        n += 1
    return known


class Net:
    def __init__(self, server, token):
        host, _, port = server.partition(":")
        self.host, self.port, self.token = host, int(port or 80), token
        self.pool = socketpool.SocketPool(wifi.radio)
        self.addr = None
        self.buf = bytearray(512)
        self.next_wifi = 0

    def connect_wifi(self):
        """Mit dem ersten bekannten WLAN in Reichweite verbinden. Gibt True zurueck, wenn verbunden."""
        if wifi.radio.connected:
            return True
        known = networks()
        if not known:
            print("!!! WLAN: CIRCUITPY_WIFI_SSID fehlt in settings.toml")
            return False
        try:  # nur Netze versuchen, die gerade zu sehen sind
            seen = set(n.ssid for n in wifi.radio.start_scanning_networks())
            wifi.radio.stop_scanning_networks()
        except Exception as e:
            print("WLAN: Suche fehlgeschlagen:", type(e).__name__, e)
            seen = None
        for ssid, password in known:
            if seen is not None and ssid not in seen:
                continue
            print("WLAN: verbinde mit", ssid)
            try:
                wifi.radio.connect(ssid, password, timeout=WIFI_TIMEOUT)
            except Exception as e:
                print("WLAN:", ssid, "geht nicht:", type(e).__name__, e)
                continue
            print("WLAN: verbunden, IP", wifi.radio.ipv4_address)
            self.addr = None
            return True
        print("!!! WLAN: keins der bekannten Netze erreichbar:", ", ".join(ssid for ssid, _ in known))
        return False

    def ensure_wifi(self):
        """Verbindet bei Bedarf neu, aber hoechstens alle WIFI_RETRY Sekunden, damit der Leser nicht haengt."""
        if wifi.radio.connected:
            return
        now = time.monotonic()
        if now >= self.next_wifi:
            self.next_wifi = now + WIFI_RETRY
            if self.connect_wifi():
                return
        raise RuntimeError("kein WLAN")

    def get(self, path, **params):
        """GET path?params&token=... und gibt die JSON-Antwort zurueck. Wirft bei Fehlern eine Exception."""
        self.ensure_wifi()
        if self.addr is None:
            self.addr = self.pool.getaddrinfo(self.host, self.port, self.pool.AF_INET, self.pool.SOCK_STREAM)[0][4]
        params["token"] = self.token
        query = "&".join("%s=%s" % kv for kv in params.items())
        req = "GET %s?%s HTTP/1.0\r\nHost: %s\r\nConnection: close\r\n\r\n" % (path, query, self.host)
        s = self.pool.socket(self.pool.AF_INET, self.pool.SOCK_STREAM)
        s.settimeout(TIMEOUT)
        data = b""
        try:
            s.connect(self.addr)
            out = req.encode()
            while out:
                out = out[s.send(out):]
            while True:
                n = s.recv_into(self.buf)
                if not n:
                    break
                data += self.buf[:n]
        except Exception:
            self.addr = None  # beim naechsten Mal neu aufloesen
            raise
        finally:
            s.close()
        head, _, body = data.partition(b"\r\n\r\n")
        status = head.split(b" ", 2)[1] if head else b"?"
        if status != b"200":
            raise RuntimeError("HTTP %s" % status.decode())
        return json.loads(body)
