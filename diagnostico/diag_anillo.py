import asyncio, time
from bleak import BleakScanner
from colmi_r02_client.client import Client

ADDR = "79:21:9E:24:EC:BA"
def t(): return time.strftime("%H:%M:%S")

async def ciclo(n):
    print(f"[{t()}] --- ciclo {n} ---", flush=True)
    dev = await BleakScanner.find_device_by_address(ADDR, timeout=20)
    print(f"[{t()}] escaneo:", "visto" if dev else "NO visto", flush=True)
    if dev is None:
        return
    c = Client(ADDR)
    try:
        await asyncio.wait_for(c.connect(), 30)
        print(f"[{t()}] conectado", flush=True)
        r = await asyncio.wait_for(c.get_realtime_heart_rate(), 60)
        print(f"[{t()}] pulso: {r}", flush=True)
    except Exception as e:
        print(f"[{t()}] ERROR en conexion/lectura: {e!r}", flush=True)
    finally:
        try:
            await asyncio.wait_for(c.disconnect(), 10)
            print(f"[{t()}] desconectado limpio", flush=True)
        except BaseException as e:
            print(f"[{t()}] la desconexion fallo: {e!r}", flush=True)

async def main():
    for n in (1, 2, 3):
        await ciclo(n)
        await asyncio.sleep(10)

asyncio.run(main())
