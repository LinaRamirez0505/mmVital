#!/usr/bin/env python3
import csv, datetime, os, sys

BASE = os.path.dirname(os.path.abspath(__file__))
dia = sys.argv[1] if len(sys.argv) > 1 else \
      (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
src = os.path.join(BASE, f"datos_{dia}.csv")
if not os.path.exists(src):
    sys.exit(f"No existe {src}")

horas = {}
with open(src) as f:
    for r in csv.DictReader(f):
        if r["detectado"] != "1":
            continue
        d = horas.setdefault(r["fecha_hora"][11:13], {"n": 0, "b": [], "c": [], "d": []})
        d["n"] += 1
        for k, col in (("b", "respiracion_rpm"), ("c", "corazon_bpm"), ("d", "distancia_cm")):
            try:
                v = float(r[col])
                if v > 0:
                    d[k].append(v)
            except ValueError:
                pass

prom = lambda l: f"{sum(l)/len(l):7.1f}" if l else "     --"
lineas = [f"Resumen del {dia} (solo filas con presencia)",
          "hora  filas  resp_rpm  pulso_bpm  dist_cm"]
for h in sorted(horas):
    d = horas[h]
    lineas.append(f"{h}:00  {d['n']:5d} {prom(d['b'])}  {prom(d['c'])}  {prom(d['d'])}")
if not horas:
    lineas.append("Sin datos con presencia.")

cmp_ = os.path.join(BASE, f"comparacion_{dia}.csv")
if os.path.exists(cmp_):
    errs = []
    with open(cmp_) as f:
        for r in csv.DictReader(f):
            try:
                errs.append(abs(float(r["error_bpm"])))
            except ValueError:
                pass
    if errs:
        lineas.append("")
        lineas.append(f"Comparacion radar vs anillo: {len(errs)} pares, "
                      f"error medio absoluto = {sum(errs)/len(errs):.1f} bpm")

texto = "\n".join(lineas)
with open(os.path.join(BASE, f"resumen_{dia}.txt"), "w") as out:
    out.write(texto + "\n")
print(texto)
