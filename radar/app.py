import csv, json, os, queue, signal, struct, subprocess, sys, threading, time
from collections import deque
from flask import Flask, Response, abort, render_template, send_file
from ld6002 import LD6002

RING_ADDR = "79:21:9E:24:EC:BA"
RING_INTERVALO = 60      # segundos de espera tras una lectura buena del anillo
RING_REINTENTO = 5       # segundos entre intentos fallidos
VENTANA_RADAR = 25       # promedio del radar en los ultimos N segundos

app = Flask(__name__)
BASE = os.path.dirname(os.path.abspath(__file__))

lock = threading.Lock()                 # protege state, stats, sysinfo, ref y hist
cola = queue.Queue(maxsize=2000)        # lector -> procesador

state = {"breath": None, "heart": None, "distance": None, "detected": 0,
         "ph_total": 0.0, "ph_breath": 0.0, "ph_heart": 0.0,
         "x": None, "y": None, "ts": 0}
stats = {"frames": 0, "descartados": 0, "start": time.time()}
sysinfo = {"cpu": 0.0, "temp": None, "nice": 0, "mem": 0.0}
ref = {"hr": None, "radar": None, "err": None, "ts": 0, "estado": "iniciando",
       "n": 0, "mae": None, "bat": None, "spo2": None}
errores = []
hist = deque(maxlen=300)                # (timestamp, pulso del radar)
proc_anillo = None

CAB = ["fecha_hora", "respiracion_rpm", "corazon_bpm",
       "distancia_cm", "detectado", "x", "y"]
CAB_CMP = ["fecha_hora", "anillo_bpm", "radar_bpm_prom", "error_bpm",
           "muestras_radar", "bateria_anillo", "spo2"]

def ruta(prefijo, dia=None):
    return os.path.join(BASE, f"{prefijo}_{dia or time.strftime('%Y-%m-%d')}.csv")

# ---------- Hilo 1: lector UART (solo lee y encola) ----------
def lector():
    while True:
        try:
            radar = LD6002()
            for ftype, data in radar.frames():
                try:
                    cola.put_nowait((ftype, data))
                except queue.Full:
                    with lock:
                        stats["descartados"] += 1
        except Exception as e:
            print("lector: error:", e, flush=True)
            time.sleep(2)

# ---------- Hilo 2: procesador (interpreta frames) ----------
def procesador():
    while True:
        ftype, data = cola.get()
        upd = {}
        if ftype == 0x0A13 and len(data) >= 12:
            t, b, h = struct.unpack("<3f", data[:12])
            upd = {"ph_total": round(t, 4), "ph_breath": round(b, 4), "ph_heart": round(h, 4)}
        elif ftype == 0x0A14 and len(data) >= 4:
            upd = {"breath": round(struct.unpack("<f", data[:4])[0], 1)}
        elif ftype == 0x0A15 and len(data) >= 4:
            upd = {"heart": round(struct.unpack("<f", data[:4])[0], 1)}
        elif ftype == 0x0A16 and len(data) >= 8:
            flag, dist = struct.unpack("<If", data[:8])
            upd = {"detected": flag, "distance": round(dist, 1)}
        elif ftype == 0x0A17 and len(data) >= 8:
            x, y = struct.unpack("<2f", data[:8])
            upd = {"x": round(x, 3), "y": round(y, 3)}
        with lock:
            stats["frames"] += 1
            if upd:
                state.update(upd)
                state["ts"] = time.time()

# ---------- Hilo 3: registrador (un CSV por dia + historial para el anillo) ----------
def registrador():
    f = w = None
    actual = None
    while True:
        time.sleep(1)
        with lock:
            s = dict(state)
            if (time.time() - s["ts"] < 2 and s["detected"]
                    and s["heart"] and s["heart"] > 0):
                hist.append((time.time(), s["heart"]))
        if time.time() - s["ts"] >= 2:
            continue
        dia = time.strftime("%Y-%m-%d")
        if dia != actual:
            if f:
                f.close()
            p = ruta("datos", dia)
            nuevo = not os.path.exists(p)
            f = open(p, "a", newline="")
            w = csv.writer(f)
            actual = dia
            if nuevo:
                w.writerow(CAB)
        w.writerow([time.strftime("%Y-%m-%d %H:%M:%S"), s["breath"], s["heart"],
                    s["distance"], s["detected"], s["x"], s["y"]])
        f.flush()

# ---------- Hilo 4: monitor del sistema ----------
def leer_cpu():
    with open("/proc/stat") as f:
        v = list(map(int, f.readline().split()[1:]))
    return v[3] + v[4], sum(v)

def sistema():
    i0, t0 = leer_cpu()
    while True:
        time.sleep(1)
        i1, t1 = leer_cpu()
        cpu = 100 * (1 - (i1 - i0) / max(1, t1 - t0))
        i0, t0 = i1, t1
        try:
            with open("/sys/class/thermal/thermal_zone0/temp") as f:
                temp = round(int(f.read()) / 1000, 1)
        except Exception:
            temp = None
        try:
            m = {}
            with open("/proc/meminfo") as f:
                for linea in f:
                    k, v = linea.split(":")
                    m[k] = int(v.split()[0])
            mem = round(100 * (1 - m["MemAvailable"] / m["MemTotal"]), 1)
        except Exception:
            mem = 0.0
        with lock:
            sysinfo.update(cpu=round(cpu, 1), temp=temp,
                           nice=os.getpriority(os.PRIO_PROCESS, 0), mem=mem)

# ---------- Hilo 5: anillo de referencia (proceso aparte + reintentos) ----------
def set_ref(**kw):
    with lock:
        ref.update(kw)

def guardar_comparacion(fila):
    p = ruta("comparacion")
    if os.path.exists(p):
        with open(p) as _f:
            if "spo2" not in _f.readline():
                os.rename(p, p + ".sin_spo2")
    nuevo = not os.path.exists(p)
    with open(p, "a", newline="") as f:
        w = csv.writer(f)
        if nuevo:
            w.writerow(CAB_CMP)
        w.writerow(fila)

def anillo():
    global proc_anillo
    script = os.path.join(BASE, "leer_anillo.py")
    intentos = 0
    while True:
        intentos += 1
        set_ref(estado=f"midiendo (intento {intentos})")
        res = {"ok": False, "error": "sin respuesta"}
        try:
            proc_anillo = subprocess.Popen([sys.executable, script],
                                           stdout=subprocess.PIPE,
                                           stderr=subprocess.DEVNULL, text=True)
            try:
                out, _ = proc_anillo.communicate(timeout=180)
                for linea in reversed(out.strip().splitlines()):
                    if linea.startswith("{"):
                        res = json.loads(linea)
                        break
            except subprocess.TimeoutExpired:
                proc_anillo.kill()
                proc_anillo.communicate()
                res = {"ok": False, "error": "tiempo agotado"}
        except Exception as e:
            res = {"ok": False, "error": repr(e)}
        finally:
            proc_anillo = None

        validos = [v for v in (res.get("hr") or []) if v > 0] if res.get("ok") else []
        if validos:
            anillo_v = sum(validos) / len(validos)
            t_fin = res.get("t_hr") or time.time()
            corte = t_fin - VENTANA_RADAR
            with lock:
                vals = [h for t, h in hist if corte <= t <= t_fin]
            sp_vals = [v for v in (res.get("spo2") or []) if 70 <= v <= 100]
            sp = round(sum(sp_vals) / len(sp_vals), 1) if sp_vals else None
            radar = sum(vals) / len(vals) if vals else None
            err = (radar - anillo_v) if radar is not None else None
            if err is not None:
                errores.append(abs(err))
            mae = sum(errores) / len(errores) if errores else None
            set_ref(hr=round(anillo_v, 1), ts=time.time(), estado="ok", bat=res.get("bat"), spo2=sp,
                    radar=round(radar, 1) if radar is not None else None,
                    err=round(err, 1) if err is not None else None,
                    n=len(errores), mae=round(mae, 1) if mae is not None else None)
            guardar_comparacion([time.strftime("%Y-%m-%d %H:%M:%S"), round(anillo_v, 1),
                                 round(radar, 1) if radar is not None else "",
                                 round(err, 1) if err is not None else "",
                                 len(vals), res.get("bat"), sp])
            intentos = 0
            time.sleep(RING_INTERVALO)
        else:
            print("anillo:", res.get("error", "sin pulso"), flush=True)
            set_ref(estado=f"reintentando (intento {intentos})")
            time.sleep(RING_REINTENTO)

# ---------- Cierre limpio (systemd envia SIGTERM) ----------
def cerrar(signum, frame):
    p = proc_anillo
    if p is not None and p.poll() is None:
        p.terminate()
    try:
        subprocess.run(["bluetoothctl", "disconnect", RING_ADDR],
                       capture_output=True, timeout=5)
    except Exception:
        pass
    sys.exit(0)

signal.signal(signal.SIGTERM, cerrar)
signal.signal(signal.SIGINT, cerrar)

for fn in (lector, procesador, registrador, sistema, anillo):
    threading.Thread(target=fn, name=fn.__name__, daemon=True).start()

# ---------- Web ----------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/datos.csv")
def descargar():
    p = ruta("datos")
    if not os.path.exists(p):
        abort(404)
    return send_file(p, as_attachment=True, download_name=os.path.basename(p))

@app.route("/comparacion.csv")
def descargar_cmp():
    p = ruta("comparacion")
    if not os.path.exists(p):
        abort(404)
    return send_file(p, as_attachment=True, download_name=os.path.basename(p))

@app.route("/stream")
def stream():
    def gen():
        with lock:
            last_f = stats["frames"]
        last_t, fps = time.time(), 0.0
        while True:
            time.sleep(0.05)
            now = time.time()
            with lock:
                out = dict(state)
                out.update(sysinfo)
                out["frames"] = stats["frames"]
                out["descartados"] = stats["descartados"]
                for k, v in ref.items():
                    out["ref_" + k] = v
            if now - last_t >= 1:
                fps = (out["frames"] - last_f) / (now - last_t)
                last_f, last_t = out["frames"], now
            out["age"] = round(now - out["ts"], 2) if out["ts"] else 999
            out["ref_age"] = round(now - out["ref_ts"]) if out["ref_ts"] else None
            out["fps"] = round(fps, 1)
            out["uptime"] = int(now - stats["start"])
            out["hilos"] = threading.active_count()
            yield f"data: {json.dumps(out)}\n\n"
    return Response(gen(), mimetype="text/event-stream")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, threaded=True)
