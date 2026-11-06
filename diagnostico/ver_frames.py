import time
from collections import Counter
from ld6002 import LD6002

radar = LD6002()
cuenta = Counter()
ejemplo = {}
t0 = time.time()

for ftype, data in radar.frames():
    cuenta[ftype] += 1
    ejemplo[ftype] = data
    if time.time() - t0 > 10:
        break

for t, n in cuenta.most_common():
    print(f"tipo=0x{t:04X}  frames={n}  largo={len(ejemplo[t])}  datos={ejemplo[t].hex(' ')}")
