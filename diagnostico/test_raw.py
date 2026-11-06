import serial
s = serial.Serial("/dev/serial0", 1382400, timeout=1)
for _ in range(5):
    d = s.read(64)
    print(len(d), d.hex(" "))
