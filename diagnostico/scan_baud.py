import serial, time

def cksum(b):
    c = 0
    for x in b:
        c ^= x
    return (~c) & 0xFF

def contar_frames(buf):
    n = 0
    for i in range(len(buf) - 8):
        if buf[i] == 0x01 and cksum(buf[i:i+7]) == buf[i+7]:
            n += 1
    return n

for baud in [115200, 230400, 256000, 460800, 921600, 1000000, 1382400, 2000000]:
    try:
        s = serial.Serial("/dev/serial0", baud, timeout=0.5)
        s.reset_input_buffer()
        time.sleep(0.3)
        data = s.read(4096)
        s.close()
        print(f"{baud:>8}  bytes={len(data):>5}  frames_validos={contar_frames(data)}")
    except Exception as e:
        print(f"{baud:>8}  error: {e}")
