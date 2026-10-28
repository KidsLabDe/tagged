# Minimaler HTTP-Client fuer den Tagged!-Server: nur GET, Klartext-HTTP/1.0, JSON-Antwort, ohne Bundle-Bibliotheken
import json
import os
import socketpool
import wifi

TIMEOUT = 3.0  # Sekunden pro Anfrage (Server steht im Internet)


class Net:
    def __init__(self, server, token):
        host, _, port = server.partition(":")
        self.host, self.port, self.token = host, int(port or 80), token
        self.pool = socketpool.SocketPool(wifi.radio)
        self.addr = None
        self.buf = bytearray(512)

    def ensure_wifi(self):
        """Mit dem WLAN aus settings.toml verbinden, falls (noch) nicht verbunden."""
        if wifi.radio.connected:
            return
        ssid = os.getenv("CIRCUITPY_WIFI_SSID")
        if not ssid:
            raise RuntimeError("CIRCUITPY_WIFI_SSID fehlt in settings.toml")
        print("WLAN: verbinde mit", ssid)
        wifi.radio.connect(ssid, os.getenv("CIRCUITPY_WIFI_PASSWORD", ""))
        print("WLAN: verbunden, IP", wifi.radio.ipv4_address)
        self.addr = None

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
