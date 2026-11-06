import struct, serial

def cksum(b):
    c = 0
    for x in b:
        c ^= x
    return (~c) & 0xFF

class LD6002:
    def __init__(self, port="/dev/serial0", baud=115200):
        self.ser = serial.Serial(port, baud, timeout=0.1)
        self.buf = bytearray()

    def frames(self):
        while True:
            self.buf += self.ser.read(256)
            while True:
                i = self.buf.find(b"\x01")
                if i < 0:
                    self.buf.clear(); break
                del self.buf[:i]
                if len(self.buf) < 8: break
                if cksum(self.buf[:7]) != self.buf[7]:
                    del self.buf[0]; continue
                length = struct.unpack(">H", self.buf[3:5])[0]
                ftype = struct.unpack(">H", self.buf[5:7])[0]
                total = 8 + length + 1
                if len(self.buf) < total: break
                data = bytes(self.buf[8:8 + length])
                if cksum(data) != self.buf[8 + length]:
                    del self.buf[0]; continue
                del self.buf[:total]
                yield ftype, data
