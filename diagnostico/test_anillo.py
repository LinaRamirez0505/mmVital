import asyncio, time
from colmi_r02_client.client import Client

ADDR = "79:21:9E:24:EC:BA"

async def main():
    async with Client(ADDR) as c:
        print("Batería:", await c.get_battery())
        for i in range(3):
            r = await c.get_realtime_heart_rate()
            if r:
                validos = [v for v in r if v > 0]
                prom = sum(validos) / len(validos) if validos else None
                print(f"Lectura {i+1}: {r}  ->  promedio {prom}")
            else:
                print(f"Lectura {i+1}: sin pulso detectado")
            time.sleep(5)

asyncio.run(main())
