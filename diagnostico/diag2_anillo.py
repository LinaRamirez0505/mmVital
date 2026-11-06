import asyncio, subprocess, time
from bleak import BleakScanner
from colmi_r02_client.client import Client

ADDR = "79:21:9E:24:EC:BA"
def t(): return time.strftime("%H:%M:%S")

async def main():
    dev = await BleakScanner.find_device_by_address(ADDR, timeout=20)
    print(f"[{t()}] escaneo:", "visto" if dev else "NO visto", flush=True)
    if dev is None:
        return
    c = Client(ADDR)
    try:
        await asyncio.wait_for(c.connect(), 30)
        print(f"[{t()}] conectado (una sola conexion)", flush=True)
        for i in range(1, 7):
            try:
                r = await asyncio.wait_for(c.get_realtime_heart_rate(), 60)
                print(f"[{t()}] lectura {i}: {r}", flush=True)
            except Exception as e:
                print(f"[{t()}] lectura {i} ERROR: {e!r}", flush=True)
            await asyncio.sleep(30)
    finally:
        try:
            await asyncio.wait_for(c.disconnect(), 10)
        except BaseException as e:
            print(f"[{t()}] cierre fallo: {e!r}", flush=True)
        subprocess.run(["bluetoothctl", "disconnect", ADDR], capture_output=True)
        print(f"[{t()}] fin", flush=True)

asyncio.run(main())
