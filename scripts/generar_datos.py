#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generador del dataset DEMO para la app Comparador de Precios (v1).

IMPORTANTE: estos datos son de DEMOSTRACIÓN, con precios de ejemplo inventados.
NO son precios reales del SEPA/Precios Claros.

El 2026-10-03 se verificó que la API pública de Precios Claros
(datos.produccion.gob.ar y los endpoints CloudFront prod/sucursales y
prod/productos) devolvía errores internos del lado del servidor
(Lambda UnboundLocalError / 500), y el portal CKAN bloquea el acceso
automatizado (403). Cuando la fuente oficial vuelva a estar operativa,
este script se puede reemplazar por una descarga real filtrada a Córdoba.

Uso:
    python3 generar_datos.py   # escribe assets/precios.json
"""
import hashlib
import json
import os
import random

# Semilla fija: los precios demo son siempre los mismos (deterministas)
random.seed(20261003)

SALIDA = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "ComparadorPrecios", "app", "src", "main", "assets", "precios.json",
)

# Sucursales de ejemplo en Córdoba (cadenas reales, direcciones ilustrativas)
SUCURSALES = [
    {"id": "carrefour", "cadena": "Carrefour", "direccion": "Av. Colón 3233", "localidad": "Córdoba"},
    {"id": "vea", "cadena": "Vea", "direccion": "Av. Rafael Núñez 3850", "localidad": "Córdoba"},
    {"id": "disco", "cadena": "Disco", "direccion": "Av. Hipólito Yrigoyen 320", "localidad": "Córdoba"},
    {"id": "cordiez", "cadena": "Cordiez", "direccion": "Av. General Paz 150", "localidad": "Córdoba"},
    {"id": "marianomax", "cadena": "Mariano Max", "direccion": "Av. Recta Martinolli 6100", "localidad": "Córdoba"},
    {"id": "changomas", "cadena": "Chango Más", "direccion": "Av. Fuerza Aérea 2100", "localidad": "Córdoba"},
]

# Factor de precio por cadena (para que el "más barato" varíe): demo
FACTOR_CADENA = {
    "carrefour": 1.00, "vea": 1.02, "disco": 1.04,
    "cordiez": 0.98, "marianomax": 0.99, "changomas": 0.97,
}

# (nombre, marcas, presentaciones{texto: precio_base}, categoria)
PLANTILLAS = [
    # Lácteos
    ("Leche entera clásica", ["La Serenísima", "Sancor", "Manfrey"], {"1 L": 2100}, "Lácteos"),
    ("Leche descremada", ["La Serenísima", "Sancor"], {"1 L": 2150}, "Lácteos"),
    ("Yogur bebible de frutilla", ["La Serenísima", "Sancor", "Tregar"], {"1 L": 2800}, "Lácteos"),
    ("Queso cremoso", ["La Serenísima", "Sancor"], {"500 g": 6500}, "Lácteos"),
    ("Dulce de leche clásico", ["La Serenísima", "Sancor"], {"400 g": 3200}, "Lácteos"),
    ("Manteca", ["La Serenísima", "Sancor"], {"200 g": 2900}, "Lácteos"),
    ("Queso rallado", ["La Serenísima", "Sancor"], {"120 g": 2600}, "Lácteos"),
    ("Crema de leche", ["La Serenísima", "Tregar"], {"200 ml": 2400}, "Lácteos"),
    # Almacén
    ("Yerba mate elaborada", ["Taragüí", "Playadito", "Rosamonte"], {"500 g": 3500, "1 kg": 6500}, "Almacén"),
    ("Fideos tallarines", ["Matarazzo", "Lucchetti", "Don Felipe"], {"500 g": 1400}, "Almacén"),
    ("Fideos mostacholes", ["Matarazzo", "Lucchetti"], {"500 g": 1400}, "Almacén"),
    ("Arroz largo fino", ["Gallo", "Molinos Ala", "Lucchetti"], {"1 kg": 2200}, "Almacén"),
    ("Harina de trigo 000", ["Blancaflor", "Pureza"], {"1 kg": 1300}, "Almacén"),
    ("Aceite de girasol", ["Natura", "Cocinero", "Legítimo"], {"900 ml": 2800, "1.5 L": 4200}, "Almacén"),
    ("Aceite de oliva", ["Natura", "Cocinero"], {"500 ml": 7500}, "Almacén"),
    ("Azúcar común", ["Ledesma", "Chango"], {"1 kg": 1500}, "Almacén"),
    ("Sal fina", ["Celusal", "Dos Anclas"], {"500 g": 900}, "Almacén"),
    ("Café instantáneo", ["Nescafé", "La Virginia", "Arlistán"], {"170 g": 8500}, "Almacén"),
    ("Té en saquitos", ["La Virginia", "Taragüí"], {"25 saq.": 1800, "50 saq.": 3200}, "Almacén"),
    ("Mate cocido en saquitos", ["Taragüí", "La Virginia"], {"25 saq.": 1600}, "Almacén"),
    ("Galletitas dulces surtidas", ["Terrabusi", "Bagley"], {"400 g": 2100}, "Almacén"),
    ("Galletitas de agua", ["Terrabusi", "Criollitas"], {"300 g": 1600}, "Almacén"),
    ("Pan lactal blanco", ["Bimbo", "Fargo"], {"560 g": 3200}, "Almacén"),
    ("Mermelada de durazno", ["La Campagnola", "Arcor"], {"454 g": 2900}, "Almacén"),
    ("Duraznos en almíbar", ["La Campagnola", "Arcor"], {"820 g": 3400}, "Almacén"),
    ("Tomate triturado", ["La Campagnola", "Arcor"], {"520 g": 1300}, "Almacén"),
    ("Puré de tomate", ["La Campagnola", "Arcor"], {"520 g": 1200}, "Almacén"),
    ("Arvejas en lata", ["La Campagnola", "Arcor"], {"350 g": 1500}, "Almacén"),
    ("Choclo en lata", ["La Campagnola", "Arcor"], {"300 g": 1700}, "Almacén"),
    ("Atún al natural", ["La Campagnola", "Gomes da Costa"], {"170 g": 3900}, "Almacén"),
    ("Mayonesa clásica", ["Hellmann's", "Natura"], {"500 g": 3200, "950 g": 5400}, "Almacén"),
    ("Mostaza", ["Hellmann's", "Natura"], {"220 g": 1900}, "Almacén"),
    ("Ketchup", ["Hellmann's"], {"250 g": 2100}, "Almacén"),
    ("Vinagre de alcohol", ["Menoyo", "Casalta"], {"500 ml": 1400}, "Almacén"),
    ("Caldo de verdura en cubos", ["Knorr", "Maggi"], {"6 cubos": 1500, "12 cubos": 2600}, "Almacén"),
    ("Sopa crema de choclo", ["Knorr", "Maggi"], {"70 g": 1800}, "Almacén"),
    ("Polenta instantánea", ["Matarazzo", "Presto Pronta"], {"500 g": 1500}, "Almacén"),
    ("Cacao en polvo", ["Nesquik", "Toddy"], {"400 g": 4500, "800 g": 8200}, "Almacén"),
    ("Chocolatada", ["Nesquik", "Cindor"], {"1 L": 2900}, "Almacén"),
    ("Avena instantánea", ["Quaker", "Granix"], {"400 g": 2600}, "Almacén"),
    ("Copos de maíz azucarados", ["Kellogg's", "Granix"], {"500 g": 4200}, "Almacén"),
    ("Miel pura", ["Alelí", "San Apicultor"], {"500 g": 5200}, "Almacén"),
    ("Tapas de empanada", ["La Salteña"], {"12 u.": 2400}, "Almacén"),
    ("Tapas de tarta", ["La Salteña"], {"400 g": 2600}, "Almacén"),
    # Bebidas
    ("Agua mineral sin gas", ["Villavicencio", "Eco de los Andes"], {"1.5 L": 1300, "2.25 L": 1700}, "Bebidas"),
    ("Gaseosa cola", ["Coca-Cola", "Pepsi"], {"1.5 L": 3200, "2.25 L": 4200}, "Bebidas"),
    ("Gaseosa lima limón", ["Sprite", "7Up"], {"1.5 L": 3100}, "Bebidas"),
    ("Gaseosa naranja", ["Fanta", "Mirinda"], {"1.5 L": 3100}, "Bebidas"),
    ("Jugo en polvo de naranja", ["Tang", "Clight"], {"sobre 20 g": 600}, "Bebidas"),
    ("Cerveza lager en lata", ["Quilmes", "Brahma"], {"473 ml": 1900}, "Bebidas"),
    ("Vino tinto malbec", ["Trapiche", "Santa Julia"], {"750 ml": 6500}, "Bebidas"),
    ("Fernet", ["Branca"], {"750 ml": 14500}, "Bebidas"),
    ("Agua tónica", ["Schweppes", "Paso de los Toros"], {"1.5 L": 2900}, "Bebidas"),
    # Limpieza
    ("Lavandina común", ["Ayudín"], {"1 L": 1600, "2 L": 2800}, "Limpieza"),
    ("Detergente lavavajilla", ["Ala", "Magistral"], {"500 ml": 1900, "750 ml": 2600}, "Limpieza"),
    ("Jabón en polvo baja espuma", ["Ala", "Skip"], {"800 g": 4200, "3 kg": 13500}, "Limpieza"),
    ("Jabón líquido para ropa", ["Ala", "Skip"], {"800 ml": 5200}, "Limpieza"),
    ("Suavizante para ropa", ["Vívere", "Comfort"], {"900 ml": 3900}, "Limpieza"),
    ("Limpiador cremoso", ["Cif"], {"500 g": 2900}, "Limpieza"),
    ("Limpiador líquido multiuso", ["Procenex", "Poett"], {"900 ml": 2400}, "Limpieza"),
    ("Desinfectante de piso lavanda", ["Poett", "Procenex"], {"900 ml": 2300}, "Limpieza"),
    ("Esponja de cocina", ["Scotch-Brite"], {"3 u.": 2200}, "Limpieza"),
    ("Bolsas de residuos", ["Hefty"], {"30 u.": 2600}, "Limpieza"),
    ("Papel higiénico hoja simple", ["Higienol", "Campanita"], {"4 u. x 30 m": 2900}, "Limpieza"),
    ("Papel higiénico hoja doble", ["Higienol", "Élite"], {"4 u.": 4200}, "Limpieza"),
    ("Rollo de cocina", ["Elite", "Sussex"], {"3 u.": 3600}, "Limpieza"),
    # Higiene personal
    ("Jabón de tocador", ["Dove", "Rexona"], {"90 g x 3": 3900}, "Higiene"),
    ("Shampoo anticaspa", ["Head & Shoulders", "Clear"], {"400 ml": 7200}, "Higiene"),
    ("Shampoo uso diario", ["Sedal", "Pantene"], {"340 ml": 5900}, "Higiene"),
    ("Acondicionador", ["Sedal", "Dove"], {"340 ml": 5900}, "Higiene"),
    ("Desodorante antitranspirante en aerosol", ["Rexona", "Dove"], {"150 ml": 5200}, "Higiene"),
    ("Pasta dental anticaries", ["Colgate", "Oral-B"], {"90 g": 3400}, "Higiene"),
    ("Cepillo dental medio", ["Colgate", "Oral-B"], {"1 u.": 2900}, "Higiene"),
    ("Toallitas húmedas para bebé", ["Huggies", "Pampers"], {"48 u.": 4200}, "Higiene"),
    ("Pañales descartables M", ["Huggies", "Pampers"], {"34 u.": 12500}, "Higiene"),
    ("Máquina de afeitar descartable", ["Gillette"], {"5 u.": 6800}, "Higiene"),
    ("Alcohol en gel", ["La Farma"], {"250 ml": 2400}, "Higiene"),
    ("Protector solar FPS 50", ["Dermaglós", "Nivea"], {"200 ml": 14500}, "Higiene"),
    # Más almacén
    ("Fideos tirabuzón", ["Matarazzo", "Lucchetti"], {"500 g": 1400}, "Almacén"),
    ("Ñoquis de papa", ["Lucchetti"], {"500 g": 1900}, "Almacén"),
    ("Lentejas secas", ["La Campagnola", "Arcor"], {"400 g": 1800}, "Almacén"),
    ("Garbanzos en lata", ["La Campagnola"], {"350 g": 1900}, "Almacén"),
    ("Porotos en lata", ["La Campagnola", "Arcor"], {"350 g": 1600}, "Almacén"),
    ("Salsa de tomate para pizza", ["La Campagnola"], {"340 g": 1500}, "Almacén"),
    ("Aceitunas verdes rellenas", ["La Campagnola", "Nucete"], {"200 g": 3200}, "Almacén"),
    ("Pickles en vinagre", ["La Campagnola"], {"330 g": 2900}, "Almacén"),
    ("Mermelada de frutilla", ["La Campagnola", "Arcor"], {"454 g": 2900}, "Almacén"),
    ("Mermelada de naranja", ["Arcor"], {"454 g": 2800}, "Almacén"),
    ("Jalea de membrillo", ["Arcor", "La Campagnola"], {"500 g": 2600}, "Almacén"),
    ("Batata en almíbar", ["La Campagnola"], {"820 g": 3200}, "Almacén"),
    ("Ensalada de frutas en almíbar", ["La Campagnola", "Arcor"], {"820 g": 3600}, "Almacén"),
    ("Ananá en almíbar", ["La Campagnola"], {"580 g": 3900}, "Almacén"),
    ("Caballa en aceite", ["La Campagnola", "Gomes da Costa"], {"170 g": 3400}, "Almacén"),
    ("Paté de foie", ["La Campagnola"], {"90 g": 1900}, "Almacén"),
    ("Salchichas de Viena", ["Paladini", "Swift"], {"6 u.": 2900}, "Almacén"),
    ("Hamburguesas de carne", ["Paty", "Swift"], {"4 u.": 5200}, "Almacén"),
    ("Supremas de pollo rebozadas", ["Granja del Sol"], {"500 g": 4900}, "Almacén"),
    ("Bastones de merluza", ["Granja del Sol"], {"400 g": 4500}, "Almacén"),
    ("Papas fritas congeladas", ["McCain", "Granja del Sol"], {"1 kg": 5900}, "Almacén"),
    ("Espinaca congelada", ["Granja del Sol"], {"500 g": 2900}, "Almacén"),
    ("Choclo en granos congelado", ["Granja del Sol"], {"500 g": 3100}, "Almacén"),
    ("Arvejas congeladas", ["Granja del Sol"], {"500 g": 2900}, "Almacén"),
    ("Helado de crema americana", ["Grido", "Freddo"], {"1 kg": 8900}, "Almacén"),
    ("Helado de dulce de leche", ["Grido"], {"1 kg": 8900}, "Almacén"),
    ("Postre de chocolate", ["La Serenísima", "Sancor"], {"120 g": 1400}, "Almacén"),
    ("Flan casero", ["La Serenísima"], {"120 g": 1300}, "Almacén"),
    ("Gelatina de frutilla", ["Royal"], {"40 g": 900}, "Almacén"),
    ("Polvo para hornear", ["Royal"], {"100 g": 1600}, "Almacén"),
    ("Esencia de vainilla", ["Alicante"], {"30 ml": 1900}, "Almacén"),
    ("Canela molida", ["Alicante"], {"25 g": 1700}, "Almacén"),
    ("Pimentón dulce", ["Alicante", "La Parmesana"], {"50 g": 1500}, "Almacén"),
    ("Orégano", ["Alicante"], {"25 g": 1200}, "Almacén"),
    ("Provenzal", ["Alicante"], {"25 g": 1300}, "Almacén"),
    ("Comino molido", ["Alicante"], {"25 g": 1400}, "Almacén"),
    ("Ají molido", ["Alicante"], {"25 g": 1400}, "Almacén"),
    ("Laurel en hojas", ["Alicante"], {"10 g": 1100}, "Almacén"),
    ("Edulcorante en polvo", ["Hileret", "Si Diet"], {"100 sobres": 3900}, "Almacén"),
    ("Edulcorante líquido", ["Hileret"], {"200 ml": 3600}, "Almacén"),
    ("Sal gruesa parrillera", ["Celusal", "Dos Anclas"], {"500 g": 1100}, "Almacén"),
    ("Harina leudante", ["Blancaflor", "Pureza"], {"1 kg": 1600}, "Almacén"),
    ("Harina integral", ["Pureza"], {"1 kg": 1900}, "Almacén"),
    ("Fécula de maíz", ["Maizena"], {"400 g": 2400}, "Almacén"),
    ("Premezcla para bizcochuelo de vainilla", ["Exquisita"], {"540 g": 2900}, "Almacén"),
    ("Premezcla para bizcochuelo de chocolate", ["Exquisita"], {"540 g": 2900}, "Almacén"),
    ("Alfajores de chocolate", ["Jorgito", "Terrabusi"], {"6 u.": 3600}, "Almacén"),
    ("Turrón de maní", ["Arcor"], {"25 g": 800}, "Almacén"),
    ("Caramelos de leche", ["Arcor"], {"150 g": 1600}, "Almacén"),
    ("Chicles de menta", ["Beldent"], {"16 u.": 2200}, "Almacén"),
    ("Barras de cereal", ["Granix", "Quaker"], {"6 u.": 3200}, "Almacén"),
    ("Granola con miel", ["Granix"], {"400 g": 3900}, "Almacén"),
    ("Leche en polvo entera", ["La Serenísima", "Sancor"], {"800 g": 12500}, "Almacén"),
    # Más bebidas
    ("Agua mineral con gas", ["Villavicencio"], {"1.5 L": 1400}, "Bebidas"),
    ("Agua saborizada de manzana", ["Villavicencio", "Levité"], {"1.5 L": 1900}, "Bebidas"),
    ("Jugo de naranja en caja", ["Cepita"], {"1 L": 2400}, "Bebidas"),
    ("Jugo de durazno en caja", ["Cepita", "Baggio"], {"1 L": 2300}, "Bebidas"),
    ("Bebida energizante", ["Monster", "Red Bull"], {"473 ml": 3900}, "Bebidas"),
    ("Cerveza negra en lata", ["Quilmes"], {"473 ml": 2100}, "Bebidas"),
    ("Cerveza en porrón", ["Quilmes", "Brahma"], {"340 ml": 1500}, "Bebidas"),
    ("Vino blanco chardonnay", ["Trapiche"], {"750 ml": 6800}, "Bebidas"),
    ("Espumante brut nature", ["Chandon", "Navarro Correas"], {"750 ml": 12500}, "Bebidas"),
    ("Aperitivo bitter", ["Campari"], {"750 ml": 11800}, "Bebidas"),
    # Más limpieza
    ("Lavandina en gel", ["Ayudín"], {"1 L": 2400}, "Limpieza"),
    ("Quitamanchas en polvo", ["Vanish"], {"400 g": 5200}, "Limpieza"),
    ("Lustramuebles en aerosol", ["Blem"], {"360 ml": 4200}, "Limpieza"),
    ("Cera para pisos", ["Blem", "Echo"], {"900 ml": 4900}, "Limpieza"),
    ("Insecticida en aerosol", ["Raid"], {"360 ml": 5900}, "Limpieza"),
    ("Pastillas para inodoro", ["Harpic"], {"3 u.": 3900}, "Limpieza"),
    ("Limpiador de vidrios con gatillo", ["Mr. Músculo"], {"500 ml": 3400}, "Limpieza"),
    ("Destapacañerías", ["Mr. Músculo"], {"500 ml": 4900}, "Limpieza"),
    ("Guantes de látex", ["Champión"], {"10 u.": 2900}, "Limpieza"),
    # Más higiene
    ("Shampoo para cabello graso", ["Sedal", "Plusbelle"], {"340 ml": 4900}, "Higiene"),
    ("Crema para peinar", ["Sedal"], {"300 ml": 5200}, "Higiene"),
    ("Enjuague bucal menta", ["Listerine", "Colgate"], {"250 ml": 4900}, "Higiene"),
    ("Hilo dental", ["Oral-B"], {"50 m": 3900}, "Higiene"),
    ("Toallas femeninas normales", ["Always"], {"16 u.": 4900}, "Higiene"),
    ("Protectores diarios", ["Carefree"], {"40 u.": 3900}, "Higiene"),
    ("Discos de algodón", ["La Farma"], {"80 u.": 2400}, "Higiene"),
    ("Hisopos de algodón", ["La Farma"], {"100 u.": 1900}, "Higiene"),
    ("Crema hidratante corporal", ["Nivea", "Dove"], {"400 ml": 8900}, "Higiene"),
    ("Repelente de insectos en crema", ["Off"], {"200 ml": 6900}, "Higiene"),
    ("Curitas surtidas", ["Curitas"], {"30 u.": 2900}, "Higiene"),
    # Mascotas
    ("Alimento para perros adultos", ["Pedigree", "Dog Chow"], {"1.5 kg": 8900, "8 kg": 39000}, "Mascotas"),
    ("Alimento para gatos", ["Whiskas", "Cat Chow"], {"1.5 kg": 9900}, "Mascotas"),
    ("Piedras sanitarias para gatos", ["Absorsol"], {"4 kg": 6900}, "Mascotas"),
    # --- Ampliación 2026-10-03: más lácteos ---
    ("Leche chocolatada", ["La Serenísima", "Sancor"], {"1 L": 3400}, "Lácteos"),
    ("Yogur firme de vainilla", ["La Serenísima", "Sancor"], {"190 g": 1900}, "Lácteos"),
    ("Yogur con cereales", ["La Serenísima", "Sancor"], {"174 g": 2100}, "Lácteos"),
    ("Queso untable", ["La Serenísima", "Sancor"], {"300 g": 3900}, "Lácteos"),
    ("Queso port salut", ["La Serenísima", "Sancor"], {"500 g": 7200}, "Lácteos"),
    ("Queso reggianito", ["La Serenísima"], {"200 g": 5900}, "Lácteos"),
    ("Muzzarella", ["La Serenísima", "Sancor"], {"500 g": 6900}, "Lácteos"),
    ("Ricota", ["La Serenísima", "Sancor"], {"500 g": 4200}, "Lácteos"),
    ("Postre de chocolate", ["La Serenísima", "Sancor"], {"95 g": 1600}, "Lácteos"),
    ("Flan de vainilla", ["La Serenísima"], {"120 g": 1400}, "Lácteos"),
    ("Leche en polvo", ["La Serenísima", "Sancor"], {"400 g": 8900}, "Lácteos"),
    ("Gelatina de frutilla", ["Exquisita"], {"40 g": 1200}, "Lácteos"),
    ("Crema chantilly", ["La Serenísima"], {"250 g": 3900}, "Lácteos"),
    ("Queso azul", ["La Serenísima"], {"200 g": 6400}, "Lácteos"),
    ("Huevos blancos", ["San Juan"], {"12 u.": 4900, "30 u.": 11000}, "Lácteos"),
    ("Yogur griego natural", ["La Serenísima", "Sancor"], {"150 g": 2400}, "Lácteos"),
    ("Leche deslactosada", ["La Serenísima"], {"1 L": 2900}, "Lácteos"),
    ("Queso crema light", ["La Serenísima"], {"300 g": 4200}, "Lácteos"),
    # --- Ampliación 2026-10-03: más bebidas ---
    ("Gaseosa cola", ["Coca-Cola", "Pepsi"], {"500 ml": 1900}, "Bebidas"),
    ("Gaseosa lima limón", ["Sprite", "7Up"], {"2.25 L": 3900}, "Bebidas"),
    ("Gaseosa naranja", ["Fanta", "Mirinda"], {"2.25 L": 3900}, "Bebidas"),
    ("Agua mineral sin gas", ["Villavicencio", "Villa del Sur"], {"2 L": 1900, "500 ml": 900}, "Bebidas"),
    ("Agua saborizada de manzana", ["Aquarius", "Villa del Sur"], {"1.5 L": 2400}, "Bebidas"),
    ("Jugo de naranja", ["Cepita", "Citric"], {"1 L": 2900}, "Bebidas"),
    ("Jugo en polvo de naranja", ["Tang", "Clight"], {"18 g": 600}, "Bebidas"),
    ("Cerveza rubia", ["Quilmes", "Brahma"], {"1 L": 2900, "473 ml": 1900}, "Bebidas"),
    ("Vino tinto malbec", ["Norton"], {"750 ml": 6900}, "Bebidas"),
    ("Vino blanco chardonnay", ["Norton"], {"750 ml": 6900}, "Bebidas"),
    ("Aperitivo americano", ["Gancia"], {"950 ml": 7900}, "Bebidas"),
    ("Soda en sifón", ["Villavicencio"], {"1.5 L": 1900}, "Bebidas"),
    ("Limonada", ["Cepita"], {"1 L": 2400}, "Bebidas"),
    # --- Ampliación 2026-10-03: más higiene ---
    ("Jabón de tocador", ["Lux", "Rexona", "Dove"], {"90 g": 1400}, "Higiene"),
    ("Acondicionador", ["Pantene", "Elvive"], {"400 ml": 7900}, "Higiene"),
    ("Crema dental", ["Colgate", "Oral-B", "Sensodyne"], {"90 g": 3900}, "Higiene"),
    ("Cepillo dental", ["Colgate", "Oral-B"], {"1 u.": 2900}, "Higiene"),
    ("Desodorante en aerosol", ["Rexona", "Dove", "Axe"], {"150 ml": 5900}, "Higiene"),
    ("Papel higiénico", ["Higienol", "Campanita", "Elite"], {"4 u.": 3900, "12 u.": 9900}, "Higiene"),
    ("Toallas femeninas", ["Always", "Carefree"], {"16 u.": 4900}, "Higiene"),
    ("Pañales descartables", ["Pampers", "Huggies"], {"36 u.": 14900}, "Higiene"),
    ("Algodón", ["Estrella"], {"100 g": 2400}, "Higiene"),
    ("Alcohol en gel", ["Bialcohol"], {"250 ml": 2900}, "Higiene"),
    ("Afeitadora descartable", ["Gillette", "Bic"], {"2 u.": 3400}, "Higiene"),
    # --- Ampliación 2026-10-03: más limpieza ---
    ("Detergente", ["Ala", "Magistral", "Cif"], {"500 ml": 2400}, "Limpieza"),
    ("Lavandina", ["Ayudín", "Querubín"], {"1 L": 1900, "2 L": 3400}, "Limpieza"),
    ("Suavizante para ropa", ["Comfort", "Ala"], {"500 ml": 3900, "1 L": 6900}, "Limpieza"),
    ("Jabón en polvo", ["Ala", "Skip", "Drive"], {"800 g": 5900}, "Limpieza"),
    ("Desinfectante", ["Lysoform", "Ayudín"], {"500 ml": 3900}, "Limpieza"),
    ("Esponja de cocina", ["Mortimer"], {"3 u.": 1900}, "Limpieza"),
    ("Bolsas de basura", ["Hefty"], {"10 u.": 2900}, "Limpieza"),
    ("Trapo de piso", ["Mortimer"], {"1 u.": 2400}, "Limpieza"),
    ("Cera para pisos", ["Ceramicol"], {"900 ml": 4900}, "Limpieza"),
    ("Lustramuebles", ["Blem"], {"360 ml": 3900}, "Limpieza"),
    ("Limpia hornos", ["Mr. Músculo"], {"500 ml": 4400}, "Limpieza"),
    # --- Ampliación 2026-10-03: más almacén ---
    ("Choclo en lata", ["La Campagnola"], {"350 g": 2400}, "Almacén"),
    ("Tomate perita en lata", ["La Campagnola", "Arcor"], {"400 g": 1900}, "Almacén"),
    ("Mayonesa", ["Hellmann's", "Natura"], {"500 g": 4900}, "Almacén"),
    ("Mostaza", ["Hellmann's", "Savora"], {"250 g": 2400}, "Almacén"),
    ("Ketchup", ["Hellmann's"], {"500 g": 4400}, "Almacén"),
    ("Papas fritas", ["Lays"], {"150 g": 3900}, "Almacén"),
    ("Maní tostado", ["Arcor"], {"100 g": 1900}, "Almacén"),
    ("Galletitas rellenas", ["Oreo", "Toddy"], {"118 g": 1900}, "Almacén"),
    ("Alfajores", ["Jorgito", "Guaymallén"], {"6 u.": 3900}, "Almacén"),
    ("Chocolate en barra", ["Cadbury", "Águila"], {"150 g": 4900}, "Almacén"),
    ("Miel", ["Aleluya"], {"500 g": 6900}, "Almacén"),
    ("Polenta", ["Presto Pronta"], {"500 g": 1900}, "Almacén"),
    ("Caldo en cubos", ["Knorr", "Maggi"], {"12 u.": 2400}, "Almacén"),
    ("Sopa instantánea", ["Knorr"], {"70 g": 1400}, "Almacén"),
    # --- Ampliación 2026-10-03: más mascotas ---
    ("Alimento para cachorros", ["Pedigree", "Dog Chow"], {"3 kg": 14900}, "Mascotas"),
    ("Alimento para gatos castrados", ["Whiskas", "Cat Chow"], {"3 kg": 19900}, "Mascotas"),
    ("Snacks para perros", ["Pedigree"], {"100 g": 2900}, "Mascotas"),
    ("Huesos de carnaza", ["Pedigree"], {"4 u.": 3900}, "Mascotas"),
    ("Alimento húmedo para gatos", ["Whiskas"], {"85 g": 1400}, "Mascotas"),
    ("Alimento húmedo para perros", ["Pedigree"], {"100 g": 1400}, "Mascotas"),
    ("Shampoo para perros", ["Mimaskot"], {"500 ml": 4900}, "Mascotas"),
    ("Cepillo para mascotas", ["Mimaskot"], {"1 u.": 3400}, "Mascotas"),
    # --- Ampliación 2026-10-03 (tanda 2): almacén ---
    ("Aceite de maíz", ["Natura", "Cocinero"], {"900 ml": 3200}, "Almacén"),
    ("Vinagre de alcohol", ["Dos Anclas"], {"500 ml": 1400}, "Almacén"),
    ("Vinagre de manzana", ["Dos Anclas"], {"500 ml": 1900}, "Almacén"),
    ("Salsa golf", ["Hellmann's"], {"250 g": 2900}, "Almacén"),
    ("Aceitunas verdes", ["La Campagnola"], {"200 g": 3400}, "Almacén"),
    ("Palmitos en lata", ["La Campagnola"], {"400 g": 5900}, "Almacén"),
    ("Ananá en almíbar", ["La Campagnola"], {"820 g": 4900}, "Almacén"),
    ("Jardinera en lata", ["La Campagnola"], {"350 g": 2400}, "Almacén"),
    ("Lentejas", ["Lucchetti"], {"500 g": 2400}, "Almacén"),
    ("Garbanzos", ["Lucchetti"], {"500 g": 2900}, "Almacén"),
    ("Avena", ["Quaker"], {"500 g": 2900}, "Almacén"),
    ("Mantecol", ["Mantecol"], {"250 g": 4900}, "Almacén"),
    ("Turrón", ["Arcor"], {"25 g": 900}, "Almacén"),
    ("Chupetines", ["Arcor"], {"10 u.": 1900}, "Almacén"),
    ("Gomitas", ["Arcor"], {"100 g": 1900}, "Almacén"),
    # --- Ampliación 2026-10-03 (tanda 2): bebidas ---
    ("Gaseosa pomelo", ["Paso de los Toros"], {"1.5 L": 2900}, "Bebidas"),
    ("Agua con gas", ["Villavicencio"], {"2 L": 1900}, "Bebidas"),
    ("Jugo de manzana", ["Cepita"], {"1 L": 2900}, "Bebidas"),
    ("Té frío de limón", ["Cepita", "Aquarius"], {"1.5 L": 2900}, "Bebidas"),
    ("Cerveza negra", ["Quilmes"], {"1 L": 3400}, "Bebidas"),
    ("Sidra", ["Real"], {"750 ml": 4900}, "Bebidas"),
    ("Espumante", ["Norton"], {"750 ml": 9900}, "Bebidas"),
    # --- Ampliación 2026-10-03 (tanda 2): lácteos/higiene/limpieza ---
    ("Yogur bebible de vainilla", ["La Serenísima", "Sancor"], {"1 L": 2900}, "Lácteos"),
    ("Leche parcialmente descremada", ["La Serenísima"], {"1 L": 2200}, "Lácteos"),
    ("Queso cremoso light", ["La Serenísima"], {"500 g": 6900}, "Lácteos"),
    ("Dulce de leche repostero", ["La Serenísima"], {"400 g": 3400}, "Lácteos"),
    ("Enjuague bucal", ["Listerine", "Colgate"], {"500 ml": 6900}, "Higiene"),
    ("Crema para peinar", ["Pantene", "Elvive"], {"300 ml": 5900}, "Higiene"),
    ("Quitaesmalte", ["Cutex"], {"100 ml": 2400}, "Higiene"),
    ("Jabón blanco en pan", ["Seiseme"], {"200 g": 1900}, "Limpieza"),
    ("Limpiador de piso", ["Procenex", "Poett"], {"900 ml": 3400}, "Limpieza"),
    ("Antigrasa", ["Mr. Músculo"], {"500 ml": 3900}, "Limpieza"),
]


def jitter(clave: str) -> float:
    """Variación determinista entre 0.94 y 1.06 según la clave."""
    h = hashlib.md5(clave.encode("utf-8")).hexdigest()
    return 0.94 + (int(h[:8], 16) % 130) / 1000.0


def redondear(p: float) -> int:
    p = max(99, round(p / 10) * 10 - 1)
    return int(p)


def main():
    productos = []
    for nombre, marcas, presentaciones, categoria in PLANTILLAS:
        for marca in marcas:
            for pres, base in presentaciones.items():
                precios = {}
                for suc in SUCURSALES:
                    sid = suc["id"]
                    p = base * FACTOR_CADENA[sid] * jitter(f"{nombre}|{marca}|{pres}|{sid}")
                    precios[sid] = redondear(p)
                productos.append({
                    "n": nombre,
                    "m": marca,
                    "p": pres,
                    "c": categoria,
                    "pr": precios,
                })

    datos = {
        "actualizado": "2026-10-03",
        "demo": True,
        "nota": "DEMO: precios de ejemplo inventados. No son datos reales del SEPA/Precios Claros.",
        "sucursales": SUCURSALES,
        "productos": productos,
    }

    os.makedirs(os.path.dirname(SALIDA), exist_ok=True)
    with open(SALIDA, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, separators=(",", ":"))

    tam = os.path.getsize(SALIDA) / 1024
    print(f"OK: {len(productos)} productos, {len(SUCURSALES)} sucursales -> {SALIDA} ({tam:.0f} KB)")


if __name__ == "__main__":
    main()
