import os
import time
from dotenv import load_dotenv
from serpapi import GoogleSearch
from database import insertar_empresa, obtener_empresas, crear_tablas

load_dotenv()

SERPAPI_KEY = os.getenv("SERPAPI_KEY")

# ─────────────────────────────────────────────────────────────────────────────
# SECTORES + QUERIES ALTERNATIVAS
#
# La clave para maximizar SerpAPI: cada sector se busca con VARIAS queries
# distintas. Google Maps devuelve lugares diferentes según el término exacto
# ("restaurante" ≠ "bar de tapas" ≠ "comida para llevar"), así que rotando
# queries sacamos negocios que una sola búsqueda nunca encontraría.
#
# Cada query añade ~un techo de 120 resultados nuevos potenciales por zona.
# ─────────────────────────────────────────────────────────────────────────────
SECTORES = {
    "restaurantes": [
        "restaurantes", "bar de tapas", "comida para llevar",
        "cafeteria", "cerveceria", "asador", "marisqueria",
    ],
    "clinicas dentales": [
        "clinica dental", "dentista", "ortodoncista",
        "clinica de implantes dentales",
    ],
    "inmobiliarias": [
        "inmobiliaria", "agencia inmobiliaria", "administrador de fincas",
    ],
    "talleres mecanicos": [
        "taller mecanico", "taller de coches", "taller de chapa y pintura",
        "neumaticos", "electricidad del automovil",
    ],
    "academias": [
        "academia", "academia de ingles", "autoescuela",
        "centro de formacion", "clases particulares", "guarderia",
    ],
    "farmacias": [
        "farmacia", "parafarmacia", "ortopedia",
    ],
    "peluquerias": [
        "peluqueria", "barberia", "salon de belleza", "centro de estetica",
    ],
    "fontaneros": [
        "fontanero", "electricista", "cerrajero",
        "reformas", "aire acondicionado instalacion",
    ],
    "clinicas veterinarias": [
        "clinica veterinaria", "veterinario", "peluqueria canina",
    ],
    "gimnasios": [
        "gimnasio", "centro deportivo", "crossfit", "estudio de pilates",
        "estudio de yoga",
    ],
    "centros de estetica": [
        "centro de estetica", "spa", "centro de depilacion laser",
        "clinica estetica", "centro de unas",
    ],
    "general": [
        "empresa", "negocio local", "comercio", "tienda",
        "servicios profesionales", "asesoria", "gestoria",
    ],
}

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


def _queries_para_sector(sector):
    """
    Devuelve la lista de queries alternativas de un sector.
    Si el sector no está en el dict (compatibilidad), usa el propio nombre.
    """
    return SECTORES.get(sector, [sector])


def _buscar_una_query(query, sector, zona, ll_param, max_resultados,
                      telefonos_existentes, empresas_guardadas):
    """
    Ejecuta UNA query concreta paginando hasta agotar resultados o llegar al máximo.
    Muta telefonos_existentes y empresas_guardadas in-place.
    Devuelve cuántas nuevas añadió esta query.
    """
    añadidas = 0
    pagina = 0
    max_paginas = 7  # Google Maps rara vez da más de 6-7 páginas útiles

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

        try:
            search = GoogleSearch(params)
            results = search.get_dict()
        except Exception as exc:
            print(f"    ✗ Error SerpAPI en '{query}' pág {pagina}: {exc}")
            break

        locales = results.get("local_results", [])
        if not locales:
            break

        nuevas_en_pagina = 0
        for lugar in locales:
            if len(empresas_guardadas) >= max_resultados:
                break

            telefono = lugar.get("phone", "")
            if not telefono:
                continue
            if telefono in telefonos_existentes:
                continue

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
                    añadidas += 1
                    nuevas_en_pagina += 1
                    print(f"  ✓ [{query}] {datos['nombre']} — {telefono}")

        # Si una página entera no aportó nada nuevo, las siguientes tampoco
        # (son los mismos resultados que ya tenemos). Cortamos esta query.
        if nuevas_en_pagina == 0 and pagina > 0:
            break

        pagina += 1
        if pagina < max_paginas and len(empresas_guardadas) < max_resultados:
            time.sleep(0.4)

    return añadidas


def buscar_empresas(sector, zona, max_resultados=20):
    """
    Busca empresas en Google Maps via SerpAPI con coordenadas GPS.

    ESTRATEGIA DE MAXIMIZACIÓN:
    Rota entre varias queries alternativas del sector (restaurante, tapas,
    cafetería...) para exprimir lugares distintos que una sola búsqueda no da.
    Deduplica por teléfono globalmente. Corta una query cuando deja de aportar.
    """
    coords = ZONAS.get(zona)
    if coords:
        lat, lng, zoom = coords
        ll_param = f"@{lat},{lng},{zoom}z"
    else:
        ll_param = None

    print(f"Buscando: {sector} en {zona} (objetivo: {max_resultados})...")

    telefonos_existentes = _cargar_telefonos_existentes()
    empresas_guardadas = []

    queries = _queries_para_sector(sector)

    for query in queries:
        if len(empresas_guardadas) >= max_resultados:
            break

        # Si no hay coordenadas, añadimos la zona al texto de la query
        query_final = query if ll_param else f"{query} en {zona}"

        añadidas = _buscar_una_query(
            query=query_final,
            sector=sector,
            zona=zona,
            ll_param=ll_param,
            max_resultados=max_resultados,
            telefonos_existentes=telefonos_existentes,
            empresas_guardadas=empresas_guardadas,
        )
        print(f"    → '{query_final}': +{añadidas} nuevas "
              f"({len(empresas_guardadas)}/{max_resultados})")

    print(f"  Total nuevas: {len(empresas_guardadas)} empresas.")
    return empresas_guardadas


def buscar_todo(max_por_busqueda=30):
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