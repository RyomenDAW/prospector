import os
import time
from dotenv import load_dotenv
from serpapi import GoogleSearch
from database import insertar_empresa, obtener_empresas, crear_tablas

load_dotenv()

SERPAPI_KEY = os.getenv("SERPAPI_KEY")

SECTORES = [
    "restaurantes",
    "clinicas dentales",
    "inmobiliarias",
    "talleres mecanicos",
    "academias",
    "farmacias",
    "peluquerias",
    "fontaneros",
    "clinicas veterinarias",
    "autoescuelas",
    "gimnasios",
    "centros de estetica",
]

# Zonas con coordenadas GPS (lat, lng, zoom)
# zoom 15 = ~1km radio, zoom 13 = ~5km radio, zoom 10 = ~40km radio
ZONAS = {
    # ── Sevilla amplia ─────────────────────────────────────────────────────────
    "Sevilla Capital (toda la ciudad)": (37.3886, -5.9823, 13),
    "Sevilla Provincia":                (37.3886, -5.9823, 10),

    # ── Municipios ─────────────────────────────────────────────────────────────
    "Dos Hermanas":          (37.2817, -5.9211, 14),
    "Alcala de Guadaira":    (37.3339, -5.8406, 14),
    "Mairena del Aljarafe":  (37.3447, -6.0611, 15),
    "Utrera":                (37.1836, -5.7789, 14),
    "Carmona":               (37.4706, -5.6439, 14),
    "Ecija":                 (37.5411, -5.0828, 14),
    "Coria del Rio":         (37.2922, -6.0539, 15),
    "La Rinconada":          (37.4839, -5.9811, 15),
    "Bormujos":              (37.3683, -6.0733, 15),
    "Tomares":               (37.3711, -6.0403, 15),
    "San Juan de Aznalfarache": (37.3533, -6.0217, 15),
    "Gines":                 (37.3817, -6.0722, 15),
    "Espartinas":            (37.3939, -6.1197, 15),
    "Gelves":                (37.3311, -6.0483, 15),
    "Castilleja de la Cuesta": (37.3794, -6.0533, 15),

    # ── Casco Antiguo ──────────────────────────────────────────────────────────
    "Sevilla Centro":              (37.3886, -5.9823, 15),
    "Sevilla Santa Cruz":          (37.3861, -5.9914, 15),
    "Sevilla El Arenal":           (37.3856, -6.0017, 15),
    "Sevilla Triana":              (37.3856, -6.0100, 15),
    "Sevilla San Vicente":         (37.3908, -5.9972, 15),
    "Sevilla Alameda de Hercules": (37.3944, -5.9928, 15),

    # ── Macarena ───────────────────────────────────────────────────────────────
    "Sevilla La Macarena":   (37.4033, -5.9861, 15),
    "Sevilla Feria":         (37.3989, -5.9906, 15),
    "Sevilla San Luis":      (37.3956, -5.9878, 15),
    "Sevilla Capuchinos":    (37.4011, -5.9828, 15),
    "Sevilla Pino Montano":  (37.4194, -5.9700, 15),

    # ── Norte ──────────────────────────────────────────────────────────────────
    "Sevilla Valdezorras":   (37.4322, -5.9606, 15),
    "Sevilla Parque Miraflores": (37.4150, -5.9811, 15),

    # ── Nervion / San Pablo ────────────────────────────────────────────────────
    "Sevilla Nervion":       (37.3856, -5.9672, 15),
    "Sevilla San Bernardo":  (37.3803, -5.9739, 15),
    "Sevilla Ciudad Jardin": (37.3917, -5.9644, 15),
    "Sevilla La Florida":    (37.3967, -5.9594, 15),
    "Sevilla San Pablo":     (37.4078, -5.9617, 15),

    # ── Este / Alcosa ──────────────────────────────────────────────────────────
    "Sevilla Torreblanca":   (37.3811, -5.9356, 15),
    "Sevilla Alcosa":        (37.3922, -5.9317, 15),
    "Sevilla Este":          (37.3783, -5.9428, 15),

    # ── Cerro Amate ────────────────────────────────────────────────────────────
    "Sevilla Cerro del Aguila": (37.3711, -5.9533, 15),
    "Sevilla Amate":         (37.3756, -5.9483, 15),
    "Sevilla Los Pajaritos": (37.3706, -5.9644, 15),

    # ── Sur ────────────────────────────────────────────────────────────────────
    "Sevilla Heliopolis":    (37.3611, -5.9894, 15),
    "Sevilla Los Bermejales": (37.3658, -6.0017, 15),
    "Sevilla Reina Mercedes": (37.3578, -5.9872, 15),

    # ── Bellavista / Los Remedios ──────────────────────────────────────────────
    "Sevilla Bellavista":    (37.3339, -5.9883, 15),
    "Sevilla La Palmera":    (37.3478, -5.9994, 15),
    "Sevilla Los Remedios":  (37.3711, -6.0106, 15),
}


def _cargar_telefonos_existentes():
    """Carga todos los teléfonos ya en BD para filtrar duplicados."""
    todas = obtener_empresas()
    return {e["telefono"] for e in todas if e.get("telefono")}


def buscar_empresas(sector, zona, max_resultados=20):
    """
    Busca empresas en Google Maps via SerpAPI con coordenadas GPS.
    Pagina hasta completar max_resultados válidos nuevos.
    Filtra duplicados por teléfono contra la BD.
    """
    coords = ZONAS.get(zona)
    if coords:
        lat, lng, zoom = coords
        ll_param = f"@{lat},{lng},{zoom}z"
        query = sector
    else:
        # Fallback para zonas sin coordenadas
        ll_param = None
        query = f"{sector} en {zona}"

    print(f"Buscando: {sector} en {zona}...")

    telefonos_existentes = _cargar_telefonos_existentes()
    empresas_guardadas = []
    pagina = 0
    max_paginas = 10  # safety net: máximo 200 resultados brutos

    while len(empresas_guardadas) < max_resultados and pagina < max_paginas:
        params = {
            "engine": "google_maps",
            "q": query,
            "hl": "es",
            "api_key": SERPAPI_KEY,
            "start": pagina * 20,
        }
        if ll_param:
            params["ll"] = ll_param

        search = GoogleSearch(params)
        results = search.get_dict()

        locales = results.get("local_results", [])
        if not locales:
            break  # No hay más resultados

        for lugar in locales:
            if len(empresas_guardadas) >= max_resultados:
                break

            telefono = lugar.get("phone", "")
            if not telefono:
                continue  # Sin teléfono no tiene sentido prospectar

            if telefono in telefonos_existentes:
                continue  # Ya existe en BD

            datos = {
                "nombre":      lugar.get("title", ""),
                "sector":      sector,
                "direccion":   lugar.get("address", ""),
                "telefono":    telefono,
                "web":         lugar.get("website", ""),
                "valoracion":  lugar.get("rating", 0),
                "num_resenas": lugar.get("reviews", 0),
                "zona":        zona,
            }

            if datos["nombre"]:
                empresa_id = insertar_empresa(datos)
                if empresa_id:
                    datos["id"] = empresa_id
                    empresas_guardadas.append(datos)
                    telefonos_existentes.add(telefono)
                    print(f"  ✓ {datos['nombre']} — {telefono}")

        pagina += 1
        if pagina < max_paginas and len(empresas_guardadas) < max_resultados:
            time.sleep(0.5)  # Respeto a la API

    print(f"  Total nuevas: {len(empresas_guardadas)} empresas.")
    return empresas_guardadas


def buscar_todo(max_por_busqueda=10):
    """Busca en todos los sectores y zonas configurados."""
    crear_tablas()
    total = 0
    for zona in ZONAS:
        for sector in SECTORES:
            empresas = buscar_empresas(sector, zona, max_resultados=max_por_busqueda)
            total += len(empresas)
    print(f"\nTotal empresas nuevas guardadas: {total}")


if __name__ == "__main__":
    buscar_todo()