import asyncio, subprocess, time
from bleak import BleakScanner
from colmi_r02_client.client import Client

ADDR = "79:21:9E:24:EC:BA"
t0 = time.time()
def t(): return f"[{time.strftime('%H:%M:%S')} +{int(time.time()-t0)}s]"

async def intento(n):
    dev = await BleakScanner.find_device_by_address(ADDR, timeout=15)
    if dev is None:
        print(t(), n, "no visto", flush=True); return False
    c = Client(ADDR)
    try:
        await asyncio.wait_for(c.connect(), 20)
        r = await asyncio.wait_for(c.get_realtime_heart_rate(), 60)
        print(t(), n, "EXITO, pulso:", r, flush=True)
        return True
    except Exception as e:
        print(t(), n, "fallo:", repr(e), flush=True)
        return False
    finally:
        try:
            await asyncio.wait_for(c.disconnect(), 10)
        except BaseException:
            pass
        subprocess.run(["bluetoothctl", "disconnect", ADDR], capture_output=True)

async def main():
    for n in range(1, 21):
        if await intento(n):
            break
        await asyncio.sleep(30)
    print(t(), "fin", flush=True)

asyncio.run(main())
