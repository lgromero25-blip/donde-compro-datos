#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
merge_real.py — JSON solo con precios REALES.

Regla de Luis (2026-10-04): "solo quiero precios reales o mejor no agreguemos
si no tenemos precios". Este merge incluye UNICAMENTE:
  - productos con al menos un precio real (Carrefour / Disco / Vea, canal online)
  - sucursales de esas 3 cadenas
Nada de valores demo. demo=false.

Entradas (en este mismo directorio):
  precios-real-carrefour.json, precios-real-cencosud.json,
  precios-real-masonline.json, precios-real-cordiez.json (lectores VTEX),
  ../hosting/precios.json (base demo para detectar diff real),
  precios-v4.json (padrón de sucursales)
Salida: precios-real.json (version 7)
"""
import json
import os
from datetime import date

BASE = os.path.dirname(os.path.abspath(__file__))
HOY = date.today().isoformat()
CADENAS = ["carrefour", "vea", "disco", "changomas", "cordiez"]
# cadenas con detección de "real" por diferencia vs base demo
CADENAS_DIFF = ["disco", "vea", "changomas", "cordiez"]
# versión: se toma de la variable de entorno VERSION_BASE (+1) para que el
# workflow diario la incremente; por defecto 7.
VERSION = int(os.environ.get("VERSION_BASE", "6")) + 1


def cargar(nombre):
    with open(os.path.join(BASE, nombre), encoding="utf-8") as f:
        return json.load(f)


def cargar_opcional(nombre):
    """Devuelve None si el archivo no existe (lector falló ese día)."""
    ruta = os.path.join(BASE, nombre)
    if not os.path.exists(ruta):
        print(f"  !! sin {nombre}: esa cadena queda fuera hoy")
        return None
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def main():
    demo = cargar(os.path.join("..", "hosting", "precios.json"))
    v4 = cargar("precios-v4.json")
    rcar = cargar("precios-real-carrefour.json")
    rcen = cargar("precios-real-cencosud.json")

    base_idx = {(p["n"], p["m"], p["p"]): p for p in demo["productos"]}
    reales_src = {
        "carrefour": cargar_opcional("precios-real-carrefour.json"),
        "disco": cargar_opcional("precios-real-cencosud.json"),
        "vea": cargar_opcional("precios-real-cencosud.json"),
        "changomas": cargar_opcional("precios-real-masonline.json"),
        "cordiez": cargar_opcional("precios-real-cordiez.json"),
    }
    # cadenas sin datos hoy: quedan fuera del JSON
    cadenas_hoy = [c for c in CADENAS if reales_src[c] is not None]
    idx = {c: {(p["n"], p["m"], p["p"]): p for p in reales_src[c]["productos"]}
           for c in cadenas_hoy}

    sucursales = [s for s in v4["sucursales"] if s["cadena"] in cadenas_hoy]
    print(f"sucursales reales: {len(sucursales)} (cadenas: {', '.join(cadenas_hoy)})")

    productos = []
    reales = {c: 0 for c in cadenas_hoy}
    for clave in base_idx:
        pr_real = {}
        # Carrefour: marcado explícito en pr_real
        if "carrefour" in idx:
            pc = idx["carrefour"].get(clave)
            if pc and "carrefour" in pc.get("pr_real", []):
                pr_real["carrefour"] = pc["pr"]["carrefour"]
        # Resto: difieren de la base demo determinista
        b = base_idx[clave]
        for cad in CADENAS_DIFF:
            if cad not in idx:
                continue
            pe = idx[cad].get(clave)
            if pe and pe["pr"][cad] != b["pr"][cad]:
                pr_real[cad] = pe["pr"][cad]
        if not pr_real:
            continue  # sin precio real: no se agrega
        p = base_idx[clave]
        pr = {}
        for s in sucursales:
            if s["cadena"] in pr_real:
                pr[s["id"]] = pr_real[s["cadena"]]
        r = sorted(pr_real)
        for cad in r:
            reales[cad] += 1
        img = ""
        for cad in cadenas_hoy:
            pe = idx[cad].get(clave)
            if pe and pe.get("img"):
                img = pe["img"]
                break
        if img:
            r = r + ["img"]
        productos.append({
            "n": p["n"], "m": p["m"], "p": p["p"], "c": p["c"],
            "pr": pr, "r": r, "img": img,
        })

    if not productos:
        raise SystemExit("ERROR: ningún producto con precio real; no se genera salida.")
    detalle = ", ".join(f"{c.title()} {reales[c]}" for c in cadenas_hoy)
    sitios_web = {"carrefour": "carrefour.com.ar", "disco": "disco.com.ar",
                  "vea": "vea.com.ar", "changomas": "masonline.com.ar",
                  "cordiez": "cordiez.com.ar"}
    datos = {
        "version": VERSION,
        "fecha": HOY,
        "actualizado": HOY,
        "demo": False,
        "nota": (
            f"Precios REALES {HOY} (tiendas online): {detalle} productos. "
            "Solo cadenas con precios reales verificados; sin valores de ejemplo. "
            "Precios de referencia: pueden variar en sucursal."
        ),
        "fuentes": {c: f"real {HOY} ({sitios_web[c]})" for c in cadenas_hoy},
        "sucursales": sucursales,
        "productos": productos,
    }
    salida = os.path.join(BASE, "precios-real.json")
    with open(salida, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, separators=(",", ":"))
    print(f"OK real-only v7: {len(productos)} productos, {len(sucursales)} sucursales -> {salida} ({os.path.getsize(salida)//1024} KB)")
    print("Reales:", " ".join(f"{c}={reales[c]}" for c in cadenas_hoy))
    print(f"Fotos reales: {sum(1 for p in productos if p['img'])}")


if __name__ == "__main__":
    main()
