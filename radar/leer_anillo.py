import asyncio, json, subprocess, time
from bleak import BleakScanner
from colmi_r02_client.client import Client

ADDR = "79:21:9E:24:EC:BA"

async def main():
    dev = await BleakScanner.find_device_by_address(ADDR, timeout=15)
    if dev is None:
        return {"ok": False, "error": "anillo no visible"}
    c = Client(ADDR)
    try:
        await asyncio.wait_for(c.connect(), 20)
        r = await asyncio.wait_for(c.get_realtime_heart_rate(), 60)
        t_hr = time.time()
        try:
            bat = (await asyncio.wait_for(c.get_battery(), 10)).battery_level
        except Exception:
            bat = None
        sp = None
        try:
            sp = await asyncio.wait_for(c.get_realtime_spo2(), 60)
        except Exception:
            pass          # si el SpO2 falla, el pulso ya esta guardado
        return {"ok": True, "hr": r, "t_hr": t_hr, "spo2": sp, "bat": bat}
    except Exception as e:
        return {"ok": False, "error": repr(e)}
    finally:
        try:
            await asyncio.wait_for(c.disconnect(), 10)
        except BaseException:
            pass
        subprocess.run(["bluetoothctl", "disconnect", ADDR], capture_output=True)

print(json.dumps(asyncio.run(main())))
