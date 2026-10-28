# Minimaler MFRC522-Treiber fuer CircuitPython (nur ISO14443A: UID, ATQA, SAK, ATS, GET_VERSION)
import time
import digitalio


class SPIDev:
    def __init__(self, spi, cs_pin, baudrate=4_000_000):
        self.spi = spi
        self.baudrate = baudrate
        self.cs = digitalio.DigitalInOut(cs_pin)
        self.cs.switch_to_output(True)

    def transfer(self, out):
        buf = bytearray(len(out))
        while not self.spi.try_lock():
            pass
        try:
            self.spi.configure(baudrate=self.baudrate, polarity=0, phase=0)
            self.cs.value = False
            self.spi.write_readinto(out, buf)
            self.cs.value = True
        finally:
            self.spi.unlock()
        return buf

    def write(self, out):
        self.transfer(out)

CommandReg = 0x01
ComIrqReg = 0x04
DivIrqReg = 0x05
ErrorReg = 0x06
FIFODataReg = 0x09
FIFOLevelReg = 0x0A
ControlReg = 0x0C
BitFramingReg = 0x0D
CollReg = 0x0E
ModeReg = 0x11
TxModeReg = 0x12
RxModeReg = 0x13
TxControlReg = 0x14
TxASKReg = 0x15
ModWidthReg = 0x24
RFCfgReg = 0x26
TModeReg = 0x2A
TPrescalerReg = 0x2B
TReloadRegH = 0x2C
TReloadRegL = 0x2D
VersionReg = 0x37

CMD_IDLE = 0x00
CMD_TRANSCEIVE = 0x0C
CMD_SOFTRESET = 0x0F


class RC522Error(Exception):
    pass


class Timeout(RC522Error):
    pass


class Collision(RC522Error):
    pass


def crc_a(data):
    crc = 0x6363
    for b in data:
        b ^= crc & 0xFF
        b = (b ^ (b << 4)) & 0xFF
        crc = ((crc >> 8) ^ (b << 8) ^ (b << 3) ^ (b >> 4)) & 0xFFFF
    return bytes((crc & 0xFF, crc >> 8))


def with_crc(data):
    data = bytes(data)
    return data + crc_a(data)


class RC522:
    def __init__(self, spi, cs_pin, rst_pin=None):
        self.dev = SPIDev(spi, cs_pin)
        if rst_pin is not None:
            self.rst = digitalio.DigitalInOut(rst_pin)
            self.rst.switch_to_output(False)
            time.sleep(0.01)
            self.rst.value = True
            time.sleep(0.05)
        self.init()

    def w(self, reg, val):
        self.dev.write(bytes(((reg << 1) & 0x7E, val)))

    def r(self, reg):
        return self.dev.transfer(bytes((((reg << 1) & 0x7E) | 0x80, 0)))[1]

    def set_bits(self, reg, mask):
        self.w(reg, self.r(reg) | mask)

    def clear_bits(self, reg, mask):
        self.w(reg, self.r(reg) & ~mask)

    def version(self):
        return self.r(VersionReg)

    def init(self):
        self.w(CommandReg, CMD_SOFTRESET)
        time.sleep(0.05)
        self.w(TxModeReg, 0x00)
        self.w(RxModeReg, 0x00)
        self.w(ModWidthReg, 0x26)
        self.w(TModeReg, 0x80)  # Timer startet automatisch nach dem Senden
        self.w(TPrescalerReg, 0xA9)
        self.w(TReloadRegH, 0x03)  # ca. 25 ms Timeout
        self.w(TReloadRegL, 0xE8)
        self.w(TxASKReg, 0x40)
        self.w(ModeReg, 0x3D)
        self.w(RFCfgReg, 0x70)  # maximale Empfangsverstaerkung (48 dB)
        self.antenna(True)

    def antenna(self, on):
        if on:
            self.set_bits(TxControlReg, 0x03)
        else:
            self.clear_bits(TxControlReg, 0x03)

    def transceive(self, data, tx_last_bits=0):
        self.w(CommandReg, CMD_IDLE)
        self.w(ComIrqReg, 0x7F)
        self.w(FIFOLevelReg, 0x80)
        for b in data:
            self.w(FIFODataReg, b)
        self.w(BitFramingReg, tx_last_bits)
        self.w(CommandReg, CMD_TRANSCEIVE)
        self.set_bits(BitFramingReg, 0x80)
        deadline = time.monotonic() + 0.1
        while True:
            irq = self.r(ComIrqReg)
            if irq & 0x30:
                break
            if irq & 0x01 or time.monotonic() > deadline:
                self.clear_bits(BitFramingReg, 0x80)
                raise Timeout()
        self.clear_bits(BitFramingReg, 0x80)
        err = self.r(ErrorReg)
        if err & 0x08:
            raise Collision()
        if err & 0x13:
            raise RC522Error("Fehler 0x%02X" % err)
        n = self.r(FIFOLevelReg)
        out = bytes(self.r(FIFODataReg) for _ in range(n))
        last_bits = self.r(ControlReg) & 0x07
        return out, last_bits

    def wupa(self):
        """Weckt auch Karten im HALT-Zustand. Gibt ATQA (2 Bytes) zurueck oder None."""
        try:
            atqa, _ = self.transceive(b"\x52", tx_last_bits=7)
        except RC522Error:
            return None
        return atqa if len(atqa) == 2 else None

    def select(self):
        """Antikollision + Select ueber alle Kaskadenstufen. Gibt (uid, sak) zurueck."""
        uid = b""
        for sel in (0x93, 0x95, 0x97):
            self.clear_bits(CollReg, 0x80)
            resp, _ = self.transceive(bytes((sel, 0x20)))
            if len(resp) != 5:
                raise RC522Error("Antikollision: %d Bytes" % len(resp))
            if resp[0] ^ resp[1] ^ resp[2] ^ resp[3] != resp[4]:
                raise RC522Error("BCC falsch")
            resp2, _ = self.transceive(with_crc(bytes((sel, 0x70)) + resp))
            if len(resp2) < 1:
                raise RC522Error("Kein SAK")
            sak = resp2[0]
            if resp[0] == 0x88 and not sak & 0x04:
                raise RC522Error("UID unvollstaendig gelesen")
            if sak & 0x04:  # UID noch nicht vollstaendig, resp[0] ist der Cascade Tag 0x88
                uid += resp[1:4]
                continue
            return uid + resp[0:4], sak
        raise RC522Error("UID zu lang")

    def halt(self):
        try:
            self.transceive(with_crc(b"\x50\x00"))
        except RC522Error:
            pass  # keine Antwort ist hier der Normalfall

    def command(self, data):
        """Sendet data + CRC, gibt die Antwort ohne CRC zurueck (oder None)."""
        try:
            resp, last_bits = self.transceive(with_crc(data))
        except RC522Error:
            return None
        if last_bits or len(resp) < 3:  # z.B. 4-Bit-NAK
            return None
        return resp[:-2]
