#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lector de precios REALES de Carrefour Argentina (carrefour.com.ar, plataforma VTEX).

Estrategia: usa la API pública de catálogo de VTEX
  /api/catalog_system/pub/products/search?ft=<query>&_from=0&_to=9
que responde JSON sin login ni captcha (verificado 2026-10-03).

Para cada producto de nuestra lista (hosting/precios.json) busca
"<nombre> <marca>", elige el mejor match por nombre/marca/tamaño (tamaño
EXACTO con rechazo duro: aliases l/lt, g/gr, ml/cc, kg, m/mt, u/un; y
rechazo de multipacks que no coinciden) y extrae el precio real + la URL
de la imagen (campo "img", VTEX la publica en items[].images[].imageUrl).
Respeta rate limiting: 1 hilo, ~1.5s entre requests (solo cuando hay red).

Salida: herramientas/precios-real-carrefour.json con la misma estructura
del proyecto; los precios de la sucursal "carrefour" son reales cuando hubo
match, el resto conserva los valores actuales. Incluye:
  - "fuentes": estado por cadena (real/demo)
  - por producto "pr_real": ["carrefour"] cuando ese precio es real

Uso:
    python3 leer_carrefour.py
"""
import json
import os
import re
import time
import unicodedata
import urllib.parse
import urllib.request
import urllib.error

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENTRADA = os.path.join(BASE_DIR, "base-demo.json")
SALIDA = os.path.join(BASE_DIR, "precios-real-carrefour.json")
CACHE = os.path.join(BASE_DIR, ".cache_carrefour.json")

API = "https://www.carrefour.com.ar/api/catalog_system/pub/products/search"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
PAUSA = 1.5  # segundos entre búsquedas

BLOQUEO = {"activado": False}


def norm(s):
    s = unicodedata.normalize("NFD", str(s)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", s.lower()).strip()


def cargar_cache():
    try:
        with open(CACHE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def guardar_cache(cache):
    try:
        with open(CACHE, "w", encoding="utf-8") as f:
            json.dump(cache, f)
    except Exception:
        pass


def buscar(query, cache):
    if query in cache:
        return cache[query], False
    url = f"{API}?ft={urllib.parse.quote(query)}&_from=0&_to=19"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        if e.code in (403, 429):
            BLOQUEO["activado"] = True
            raise RuntimeError(f"BLOQUEO del sitio (HTTP {e.code}). Me detengo.")
        # otro error: un reintento tras pausa
        time.sleep(3)
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                data = json.load(r)
        except Exception:
            return [], False
    except Exception:
        return [], False
    cache[query] = data
    guardar_cache(cache)
    return data, True


def precio_de(item):
    """Devuelve (precio_int, disponible) del primer seller del item."""
    try:
        sellers = item.get("sellers") or []
        co = sellers[0].get("commertialOffer") or {}
        if not co.get("IsAvailable"):
            return None, False
        p = co.get("Price")
        return (int(round(float(p))), True) if p else (None, False)
    except Exception:
        return None, False


UNIT_ALIAS = {
    "l": ["l", "lt", "lts", "litro", "litros"],
    "g": ["g", "gr", "grs", "gramo", "gramos"],
    "ml": ["ml", "cc"],
    "kg": ["kg", "kilo", "kilos"],
    "m": ["m", "mt", "mts", "metro", "metros"],
    "u": ["u", "un", "unidades"],
}

CACHE = os.path.join(BASE_DIR, ".cache_carrefour.json")

COUNT_UNITS = {"u", "un", "unidades", "sobre", "sobres", "saq", "cubo", "cubos"}


def componentes(pres):
    """Lista de (num, unit) de la presentación. 'x N' -> (N, '')."""
    comps = []
    for m in re.finditer(r"(\d+(?:[.,]\d+)?)\s*([a-z]*)", norm(pres)):
        if not m.group(1):
            continue
        num = float(m.group(1).replace(",", "."))
        comps.append((num, m.group(2)))
    return comps


def tamano_ok(presentacion, product_name_norm):
    """Chequea que el tamaño aparezca en el nombre y rechaza multipacks ajenos."""
    pn = product_name_norm.replace(",", ".")
    comps = componentes(presentacion)
    if not comps:
        return True
    for num, unit in comps:
        ntxt = str(int(num)) if num.is_integer() else str(num)
        if unit in ("", "x") or unit in COUNT_UNITS:
            # cuenta suelta: vale 'x N' o 'N u/un/unidades/sobres/...'
            if len(comps) == 1 and num == 1:
                continue
            if not (re.search(rf"x\s?{re.escape(ntxt)}\b", pn)
                    or re.search(rf"\b{re.escape(ntxt)}\s?(?:u|un|unidades|sobre|sobres|saq|cubo|cubos)\b", pn)):
                return False
        else:
            aliases = UNIT_ALIAS.get(unit, [unit])
            alt = "|".join(re.escape(a) for a in aliases)
            if not re.search(rf"\b{re.escape(ntxt)}\s?(?:{alt})\b", pn):
                return False
    # guardia multipack: si el nombre trae pack/xN, tiene que coincidir con
    # la cantidad de nuestro producto (o nuestro producto no es unidad simple)
    packs = [int(x) for x in re.findall(r"(?:pack|x)\s?(\d+)", pn)]
    counts = [c[0] for c in comps if c[1] in COUNT_UNITS or (c[1] == "" and len(comps) > 1)]
    if packs:
        if not counts:
            return False  # queremos unidad simple, venden pack
        if not any(p == c for p in packs for c in counts):
            return False  # el tamaño del pack no coincide
    return True


def img_de(item):
    """URL de la imagen del producto (VTEX la publica en el catálogo)."""
    try:
        imgs = item.get("images") or []
        return imgs[0].get("imageUrl", "") if imgs else ""
    except Exception:
        return ""


def mejor_match(producto, resultados):
    """Elige el resultado VTEX más fiel. Devuelve (item, precio, img_url)."""
    nombre_n = norm(producto["n"])
    marca_n = norm(producto["m"])
    tokens = [t for t in nombre_n.split() if len(t) > 2]
    umbral = max(1, len(tokens) // 2)

    mejor, mejor_score = None, 0
    for r in resultados:
        for item in r.get("items", []):
            pn = norm(r.get("productName", ""))
            brand = norm(r.get("brand", ""))
            # la marca tiene que coincidir (en cualquier dirección)
            primera = marca_n.split()[0]
            if not (marca_n in brand or brand in marca_n
                    or (len(primera) > 2 and primera in brand)):
                continue
            hits = sum(1 for t in tokens if t in pn)
            if hits < umbral:
                continue
            # el tamaño tiene que coincidir EXACTO (rechazo duro, no solo puntos)
            if not tamano_ok(producto["p"], pn):
                continue
            score = hits * 2 + 3
            if marca_n == brand:
                score += 2
            precio, disp = precio_de(item)
            if not disp or precio is None:
                continue
            if score > mejor_score:
                mejor = (item, precio, img_de(item), r.get("productName"))
                mejor_score = score
    if mejor is None:
        return None, None, ""
    return mejor[0], mejor[1], mejor[2]


def main():
    with open(ENTRADA, encoding="utf-8") as f:
        datos = json.load(f)

    productos = datos["productos"]
    cache = cargar_cache()
    print(f"Productos a buscar: {len(productos)} (límite ~300)")

    reales = 0
    sin_match = []
    for i, prod in enumerate(productos, 1):
        query = f"{prod['n']} {prod['m']}"
        try:
            resultados, hubo_red = buscar(query, cache)
        except RuntimeError as e:
            print(f"\n{e}")
            break
        item, precio, img = mejor_match(prod, resultados)
        prod["img"] = img if precio is not None else ""
        if precio is not None:
            prod["pr"]["carrefour"] = precio
            prod.setdefault("pr_real", []).append("carrefour")
            reales += 1
        else:
            sin_match.append(f"{prod['n']} | {prod['m']} | {prod['p']}")
        if i % 25 == 0:
            print(f"  ... {i}/{len(productos)} (reales: {reales})")
        if hubo_red:
            time.sleep(PAUSA)

    datos["fecha"] = "2026-10-03"
    datos["actualizado"] = "2026-10-03"
    datos["version"] = 2
    datos["demo"] = True  # mixto: carrefour real donde hubo match, resto demo
    datos["nota"] = ("MIXTO: precios de Carrefour REALES del 2026-10-03 (carrefour.com.ar) "
                     "donde hubo match; resto de cadenas con valores DEMO de ejemplo.")
    datos["fuentes"] = {
        "carrefour": "real 2026-10-03",
        "vea": "demo", "disco": "demo", "cordiez": "demo",
        "marianomax": "demo", "changomas": "demo",
    }

    with open(SALIDA, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, separators=(",", ":"))

    print(f"\nOK: {reales}/{len(productos)} productos con precio REAL de Carrefour")
    print(f"Sin match ({len(sin_match)}):")
    for s in sin_match:
        print("  -", s)
    print(f"JSON -> {SALIDA}")


if __name__ == "__main__":
    main()
