"""Prueba de carga: N participantes entran a la vez y recorren la mochila.

Uso:
    python pruebas_carga.py --url http://localhost:5000 --admin admin --clave TU_CLAVE --usuarios 150 --rampa 30

Crea N cuentas de prueba (carga1, carga2, …) si no existen. Bórralas después desde el panel
o usa una base de datos de prueba.
"""
import argparse
import json
import random
import statistics
import threading
import time
import urllib.error
import urllib.request

latencias: dict[str, list[float]] = {}
errores: list[str] = []
candado = threading.Lock()


def pedir(base, ruta, token=None, cuerpo=None, etiqueta=None):
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    req = urllib.request.Request(base + "/api/v1" + ruta, data=datos, method="POST" if datos else "GET")
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    inicio = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            cuerpo_r = r.read()
    except urllib.error.HTTPError as e:
        with candado:
            errores.append(f"{ruta}: HTTP {e.code}")
        return None
    except Exception as e:  # noqa: BLE001
        with candado:
            errores.append(f"{ruta}: {e}")
        return None
    duracion = (time.perf_counter() - inicio) * 1000
    with candado:
        latencias.setdefault(etiqueta or ruta, []).append(duracion)
    try:
        return json.loads(cuerpo_r)
    except ValueError:
        return cuerpo_r


def participante(base, usuario, clave, rondas, barrera, rampa):
    barrera.wait()  # todos arrancan juntos…
    if rampa:
        time.sleep(random.uniform(0, rampa))  # …y entran repartidos en `rampa` segundos
    r = pedir(base, "/auth/login", cuerpo={"usuario": usuario, "contrasena": clave}, etiqueta="login")
    if not r:
        return
    t = r["token"]
    for _ in range(rondas):
        pedir(base, "/auth/yo", t, etiqueta="yo")
        indice = pedir(base, "/mochila", t, etiqueta="mochila")
        pedir(base, "/mochila/proximos", t, etiqueta="proximos")
        for s in (indice or {}).get("secciones", []):
            sec = pedir(base, f"/mochila/secciones/{s['id']}", t, etiqueta="seccion")
            for item in (sec or {}).get("seccion", {}).get("items", []):
                if item["tipo"] == "imagen" and item["archivo"]:
                    pedir(base, f"/archivos/{item['archivo']['id']}?miniatura=1", t, etiqueta="miniatura")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://localhost:5000")
    p.add_argument("--admin", default="admin")
    p.add_argument("--clave", required=True)
    p.add_argument("--usuarios", type=int, default=150)
    p.add_argument("--rondas", type=int, default=2)
    p.add_argument("--rampa", type=float, default=0, help="segundos en los que se reparten los logins (0 = todos a la vez)")
    a = p.parse_args()

    token = pedir(a.url, "/auth/login", cuerpo={"usuario": a.admin, "contrasena": a.clave})["token"]
    existentes = {u["usuario"] for u in pedir(a.url, "/admin/usuarios", token)["usuarios"]}
    nuevos = [{"nombre": f"Carga {i}", "usuario": f"carga{i}", "contrasena": "clave-de-carga",
               "categoria": "universidad", "equipo": f"Equipo {i % 30}"}
              for i in range(1, a.usuarios + 1) if f"carga{i}" not in existentes]
    if nuevos:
        print(f"Creando {len(nuevos)} cuentas de prueba…")
        pedir(a.url, "/admin/usuarios/importar", token, {"usuarios": nuevos})
    latencias.clear()

    barrera = threading.Barrier(a.usuarios)
    hilos = [threading.Thread(target=participante, args=(a.url, f"carga{i}", "clave-de-carga", a.rondas, barrera, a.rampa))
             for i in range(1, a.usuarios + 1)]
    inicio = time.perf_counter()
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    total = time.perf_counter() - inicio

    peticiones = sum(len(v) for v in latencias.values())
    print(f"\n{a.usuarios} participantes simultáneos, {peticiones} peticiones en {total:.1f} s "
          f"({peticiones / total:.0f} peticiones/s), {len(errores)} errores")
    print(f"{'operación':<12}{'n':>6}{'mediana ms':>12}{'p95 ms':>10}{'máx ms':>10}")
    for nombre, valores in latencias.items():
        valores.sort()
        p95 = valores[int(len(valores) * 0.95) - 1]
        print(f"{nombre:<12}{len(valores):>6}{statistics.median(valores):>12.0f}{p95:>10.0f}{valores[-1]:>10.0f}")
    if errores:
        print("Errores:", errores[:10])


if __name__ == "__main__":
    main()
