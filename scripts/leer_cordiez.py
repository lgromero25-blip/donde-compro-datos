#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lector de precios REALES de Cordiez (Cordoba, Argentina) para la app
"¿Dónde compro?".

Método: API pública de VTEX (la misma plataforma que usan disco.com.ar y
vea.com.ar). No requiere login ni captcha:
    https://www.disco.com.ar/api/catalog_system/pub/products/search?ft=...&_from=0&_to=9

Para cada producto de nuestra lista (ver generar_datos.py: PLANTILLAS) busca en
Disco y en Vea, matchea por marca + presentación + nombre, y extrae el precio
del primer vendedor disponible.

Uso:
    python3 leer_cordiez.py                 # lee todo (590 búsquedas máx, ~13 min)
    python3 leer_cordiez.py --limite 10     # prueba con 10 productos
    python3 leer_cordiez.py --solo disco    # solo una cadena

Respeta rate limiting: 1.2-1.8 s entre requests, un solo hilo.
Si un sitio bloquea (403/429/timeouts repetidos), se detiene en ese sitio.

Genera: precios-real-cordiez.json (misma estructura que hosting/precios.json)
"""
import json
import os
import random
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
from generar_datos import PLANTILLAS  # noqa: E402

SITIOS = {
    "www.cordiez.com.ar": "cordiez",
}
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
CACHE_PATH = os.path.join(BASE, "cache_cordiez.json")
SALIDA = os.path.join(BASE, "precios-real-cordiez.json")
BASE_DEMO = os.path.join(BASE, "base-demo.json")

STOPWORDS = {"de", "del", "la", "el", "las", "los", "en", "con", "y", "o",
             "para", "al", "un", "una", "x", "por"}
# Variantes que NO queremos si nuestro producto no las pide
NEGATIVOS = ["zero", "sin azucar", "light", "diet", "descremad", "deslactosad",
             "reducido en", "bajo en"]
NEG_PACK = ["pack", "combo", "bulto", "caja x", "display"]


def norm(s):
    s = unicodedata.normalize("NFD", str(s)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9 ]", " ", s.lower())


# unidad -> variantes para regex
UNIDADES = {
    "l": r"l|lt|lts|litro|litros",
    "g": r"g|gr|grs|gramo|gramos",
    "kg": r"kg|kilo|kilos",
    "ml": r"ml|cc|mililitro|mililitros",
    "u": r"u|un|und|unid|unidad|unidades",
    "m": r"m|mt|mts|metro|metros",
    "sobre": r"sobre|sobres|saq|saquito|saquitos|sachet",
    "cubo": r"cubo|cubos",
    "lata": r"lata|latas",
}


def pares_presentacion(pres):
    """'4 u. x 30 m' -> [('4','u'),('30','m')]; '90 g x 3' -> [('90','g'),('3','u')]"""
    t = norm(pres)
    partes = re.split(r"\bx\b", t)
    pares = []
    for i, parte in enumerate(partes):
        for num, uni in re.findall(r"(\d+(?:[.,]\d+)?)\s*([a-z]*)", parte):
            uni = uni.strip()
            if not uni:
                uni = "u" if i > 0 else None  # "x 3" suelto -> unidades
            if uni is None:
                continue
            # canonalizar unidad
            canon = None
            for c, _alt in UNIDADES.items():
                if re.fullmatch(rf"(?:{_alt})", uni):
                    canon = c
                    break
            if canon is None:
                canon = uni
            pares.append((num, canon))
    # deduplicar manteniendo orden
    vistos, out = set(), []
    for p in pares:
        if p not in vistos:
            vistos.add(p)
            out.append(p)
    return out


def num_pat(num):
    return re.escape(num).replace(r"\.", "[.,]")


def presentacion_match(pres, nombre_prod):
    """Todos los pares (número, unidad) de la presentación deben aparecer."""
    pares = pares_presentacion(pres)
    if not pares:
        return True
    t = norm(nombre_prod)
    for num, uni in pares:
        alt = UNIDADES.get(uni, re.escape(uni))
        if not re.search(rf"(?<![\d]){num_pat(num)}(?![\d])\s*(?:{alt})\b", t):
            return False
    return True


def buscar(sitio, query):
    url = (f"https://{sitio}/api/catalog_system/pub/products/search"
           f"?ft={urllib.parse.quote(query)}&_from=0&_to=9")
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                               "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)


def precio_e_imagen(producto):
    """Devuelve (precio, img) del primer item con vendedor disponible."""
    for item in producto.get("items", []):
        for seller in item.get("sellers", []):
            off = seller.get("commertialOffer", {})
            if off.get("IsAvailable") and (off.get("Price") or 0) > 0:
                precio = int(round(float(off["Price"])))
                imgs = item.get("images", []) or []
                img = (imgs[0].get("imageUrl", "") or "") if imgs else ""
                return precio, img
    return None, ""


def elegir_candidato(nombre, marca, pres, resultados):
    m_marca = norm(marca)
    toks_nombre = [t for t in norm(nombre).split()
                   if t not in STOPWORDS and len(t) > 1]
    pide_neg = [n for n in NEGATIVOS if n in norm(nombre)]
    es_pack = "x" in norm(pres)
    mejor, mejor_score = None, None
    for p in resultados:
        pn = norm(p.get("productName", ""))
        pb = norm(p.get("brand", ""))
        if m_marca not in pn and m_marca != pb:
            continue
        if not presentacion_match(pres, p.get("productName", "")):
            continue
        overlap = len(set(toks_nombre) & set(pn.split()))
        if overlap < 1:
            continue
        penal = 0
        for n in NEGATIVOS:
            if n not in pide_neg and n in pn:
                penal += 3
        if not es_pack:
            for n in NEG_PACK:
                if n in pn:
                    penal += 3
        score = (overlap * 2) - penal
        key = (score, -len(pn))
        if mejor_score is None or key > mejor_score:
            mejor, mejor_score = p, key
    if mejor is None:
        return None, None, ""
    return mejor.get("productName"), *precio_e_imagen(mejor)


def main():
    args = sys.argv[1:]
    limite = None
    solo = None
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--limite" and i + 1 < len(args):
            limite = int(args[i + 1]); i += 2; continue
        if a.startswith("--limite="):
            limite = int(a.split("=", 1)[1]); i += 1; continue
        if a == "--solo" and i + 1 < len(args):
            solo = args[i + 1]; i += 2; continue
        if a.startswith("--solo="):
            solo = a.split("=", 1)[1]; i += 1; continue
        i += 1
    sitios = [s for s in SITIOS if solo is None or SITIOS[s] == solo]

    # expandir productos: (nombre, marca, pres, categoria)
    productos = []
    for nombre, marcas, press, cat in PLANTILLAS:
        for marca in marcas:
            for pres in press:
                productos.append((nombre, marca, pres, cat))
    if limite:
        productos = productos[:limite]
    print(f"Productos a buscar: {len(productos)} x {len(sitios)} sitios")

    cache = {}
    if os.path.exists(CACHE_PATH):
        cache = json.load(open(CACHE_PATH, encoding="utf-8"))

    resultados = {}  # (n,m,p) -> {cadena: (nombre_match, precio)}
    fallos = {s: 0 for s in sitios}
    bloqueado = set()
    total_req = 0

    for idx, (nombre, marca, pres, cat) in enumerate(productos):
        for sitio in sitios:
            if sitio in bloqueado:
                continue
            cadena = SITIOS[sitio]
            q = f"{marca} {nombre}"
            ckey = f"{sitio}|{q}"
            try:
                if ckey in cache:
                    prods = cache[ckey]
                else:
                    prods = buscar(sitio, q)
                    cache[ckey] = prods
                    total_req += 1
                    time.sleep(random.uniform(1.2, 1.8))
                fallos[sitio] = 0
            except Exception as e:
                fallos[sitio] += 1
                print(f"  !! {cadena}: error en '{q}': {type(e).__name__} ({fallos[sitio]})",
                      flush=True)
                if fallos[sitio] >= 4:
                    print(f"  XX {cadena}: BLOQUEADO o caído, detengo ese sitio.", flush=True)
                    bloqueado.add(sitio)
                time.sleep(3)
                continue
            nm, precio, img = elegir_candidato(nombre, marca, pres, prods)
            resultados.setdefault((nombre, marca, pres), {})[cadena] = (nm, precio, img)
        if (idx + 1) % 25 == 0:
            print(f"  ... {idx + 1}/{len(productos)} productos", flush=True)
            json.dump(cache, open(CACHE_PATH, "w", encoding="utf-8"))

    json.dump(cache, open(CACHE_PATH, "w", encoding="utf-8"))

    # estadísticas
    stats = {c: {"ok": 0, "sin_match": 0, "con_img": 0} for c in SITIOS.values()}
    sin_match = {c: [] for c in SITIOS.values()}
    for (nombre, marca, pres), d in resultados.items():
        for cadena in SITIOS.values():
            nm, precio, img = d.get(cadena, (None, None, ""))
            if precio:
                stats[cadena]["ok"] += 1
                if img:
                    stats[cadena]["con_img"] += 1
            else:
                stats[cadena]["sin_match"] += 1
                sin_match[cadena].append(f"{nombre} | {marca} | {pres}")

    print("\n=== RESULTADOS ===")
    for cadena, st in stats.items():
        print(f"{cadena}: {st['ok']} con precio real ({st['con_img']} con imagen), "
              f"{st['sin_match']} sin match")
    print(f"requests HTTP realizados: {total_req}")

    # generar JSON final
    base = json.load(open(BASE_DEMO, encoding="utf-8"))
    for prod in base["productos"]:
        key = (prod["n"], prod["m"], prod["p"])
        if key in resultados:
            img_final = ""
            for cadena in SITIOS.values():
                _nm, precio, img = resultados[key].get(cadena, (None, None, ""))
                if precio:
                    prod["pr"][cadena] = precio
                if img and not img_final:
                    img_final = img  # imagen de Disco primero, si no la de Vea
            if img_final and not prod.get("img"):
                prod["img"] = img_final
        else:
            prod["img"] = ""
    base["fecha"] = "2026-10-04"
    base["actualizado"] = "2026-10-04"
    base["version"] = base.get("version", 1) + 1
    base["demo"] = True  # sigue habiendo cadenas con valores de ejemplo
    base["nota"] = ("Precios REALES para Cordiez leidos el 2026-10-04 de "
                    "cordiez.com.ar (API publica VTEX). "
                    "Resto de cadenas con valores de ejemplo.")
    base["fuentes"] = {
        "cordiez": "real 2026-10-04 (cordiez.com.ar)",
        "disco": "demo",
        "vea": "demo",
        "carrefour": "demo",
        "marianomax": "demo",
        "changomas": "demo",
    }
    json.dump(base, open(SALIDA, "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print(f"\nOK -> {SALIDA} ({os.path.getsize(SALIDA)//1024} KB)")

    rep = os.path.join(BASE, "reporte_cordiez.txt")
    with open(rep, "w", encoding="utf-8") as f:
        f.write("Precios reales Cordiez 2026-10-04\n")
        for cadena, st in stats.items():
            f.write(f"\n== {cadena}: {st['ok']} ok ({st['con_img']} con imagen) / "
                    f"{st['sin_match']} sin match ==\n")
            for s in sin_match[cadena]:
                f.write(f"  - {s}\n")
    print(f"Reporte -> {rep}")


if __name__ == "__main__":
    main()
