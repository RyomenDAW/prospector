import os
import time
from dotenv import load_dotenv
from serpapi import GoogleSearch
from database import insertar_empresa, obtener_empresas, crear_tablas

load_dotenv()

SERPAPI_KEY = os.getenv("SERPAPI_KEY")

# ─────────────────────────────────────────────────────────────────────────────
# SECTORES + QUERIES ALTERNATIVAS
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

# ─────────────────────────────────────────────────────────────────────────────
# ZONAS — agrupadas por territorio
#
# TERRITORIO_SEVILLA  → solo Sevilla capital y provincia
# TERRITORIO_ANDALUCIA → toda Andalucía (incluye Sevilla)
# TERRITORIO_ESPANA   → toda España (incluye Andalucía)
#
# El scheduler usa la variable TERRITORIO_SCHEDULER (configurable desde app.py)
# zoom 15 = ~1km, zoom 14 = ~3km, zoom 13 = ~5km, zoom 10 = ~40km
# ─────────────────────────────────────────────────────────────────────────────

ZONAS_SEVILLA = {
    # ── Sevilla amplia ─────────────────────────────────────────────────────────
    "Sevilla Capital (toda la ciudad)": (37.3886, -5.9823, 13),
    "Sevilla Provincia":                (37.3886, -5.9823, 10),

    # ── Municipios ─────────────────────────────────────────────────────────────
    "Dos Hermanas":             (37.2817, -5.9211, 14),
    "Alcala de Guadaira":       (37.3339, -5.8406, 14),
    "Mairena del Aljarafe":     (37.3447, -6.0611, 15),
    "Utrera":                   (37.1836, -5.7789, 14),
    "Carmona":                  (37.4706, -5.6439, 14),
    "Ecija":                    (37.5411, -5.0828, 14),
    "Coria del Rio":            (37.2922, -6.0539, 15),
    "La Rinconada":             (37.4839, -5.9811, 15),
    "Bormujos":                 (37.3683, -6.0733, 15),
    "Tomares":                  (37.3711, -6.0403, 15),
    "San Juan de Aznalfarache": (37.3533, -6.0217, 15),
    "Gines":                    (37.3817, -6.0722, 15),
    "Espartinas":               (37.3939, -6.1197, 15),
    "Gelves":                   (37.3311, -6.0483, 15),
    "Castilleja de la Cuesta":  (37.3794, -6.0533, 15),

    # ── Barrios de Sevilla ─────────────────────────────────────────────────────
    "Sevilla Centro":               (37.3886, -5.9823, 15),
    "Sevilla Santa Cruz":           (37.3861, -5.9914, 15),
    "Sevilla El Arenal":            (37.3856, -6.0017, 15),
    "Sevilla Triana":               (37.3856, -6.0100, 15),
    "Sevilla San Vicente":          (37.3908, -5.9972, 15),
    "Sevilla Alameda de Hercules":  (37.3944, -5.9928, 15),
    "Sevilla La Macarena":          (37.4033, -5.9861, 15),
    "Sevilla Feria":                (37.3989, -5.9906, 15),
    "Sevilla San Luis":             (37.3956, -5.9878, 15),
    "Sevilla Capuchinos":           (37.4011, -5.9828, 15),
    "Sevilla Pino Montano":         (37.4194, -5.9700, 15),
    "Sevilla Valdezorras":          (37.4322, -5.9606, 15),
    "Sevilla Parque Miraflores":    (37.4150, -5.9811, 15),
    "Sevilla Nervion":              (37.3856, -5.9672, 15),
    "Sevilla San Bernardo":         (37.3803, -5.9739, 15),
    "Sevilla Ciudad Jardin":        (37.3917, -5.9644, 15),
    "Sevilla La Florida":           (37.3967, -5.9594, 15),
    "Sevilla San Pablo":            (37.4078, -5.9617, 15),
    "Sevilla Torreblanca":          (37.3811, -5.9356, 15),
    "Sevilla Alcosa":               (37.3922, -5.9317, 15),
    "Sevilla Este":                 (37.3783, -5.9428, 15),
    "Sevilla Cerro del Aguila":     (37.3711, -5.9533, 15),
    "Sevilla Amate":                (37.3756, -5.9483, 15),
    "Sevilla Los Pajaritos":        (37.3706, -5.9644, 15),
    "Sevilla Heliopolis":           (37.3611, -5.9894, 15),
    "Sevilla Los Bermejales":       (37.3658, -6.0017, 15),
    "Sevilla Reina Mercedes":       (37.3578, -5.9872, 15),
    "Sevilla Bellavista":           (37.3339, -5.9883, 15),
    "Sevilla La Palmera":           (37.3478, -5.9994, 15),
    "Sevilla Los Remedios":         (37.3711, -6.0106, 15),
}

ZONAS_ANDALUCIA_EXTRA = {
    # ── Cádiz ──────────────────────────────────────────────────────────────────
    "Cadiz Capital":                (36.5271, -6.2886, 13),
    "Jerez de la Frontera":         (36.6864, -6.1372, 13),
    "El Puerto de Santa Maria":     (36.5994, -6.2328, 14),
    "San Fernando":                 (36.4770, -6.1984, 14),
    "Algeciras":                    (36.1408, -5.4547, 14),
    "La Linea de la Concepcion":    (36.1667, -5.3500, 14),
    "Sanlucar de Barrameda":        (36.7781, -6.3553, 14),
    "Chiclana de la Frontera":      (36.4167, -6.1500, 14),
    "Puerto Real":                  (36.5283, -6.1919, 14),
    "Rota":                         (36.6261, -6.3628, 14),

    # ── Huelva ─────────────────────────────────────────────────────────────────
    "Huelva Capital":               (37.2614, -6.9447, 13),
    "Lepe":                         (37.2556, -7.2044, 14),
    "Almonte":                      (37.2617, -6.5275, 14),
    "Moguer":                       (37.2756, -6.8367, 14),
    "Ayamonte":                     (37.2139, -7.4044, 14),
    "Isla Cristina":                (37.2019, -7.3228, 14),

    # ── Málaga ─────────────────────────────────────────────────────────────────
    "Malaga Capital":               (36.7213, -4.4214, 13),
    "Marbella":                     (36.5101, -4.8825, 13),
    "Fuengirola":                   (36.5408, -4.6258, 14),
    "Torremolinos":                 (36.6217, -4.4997, 14),
    "Benalmadena":                  (36.5989, -4.5278, 14),
    "Estepona":                     (36.4283, -5.1467, 14),
    "Velez-Malaga":                 (36.7794, -4.0989, 14),
    "Mijas":                        (36.5961, -4.6381, 14),
    "Ronda":                        (36.7461, -5.1611, 14),
    "Antequera":                    (37.0183, -4.5594, 14),
    "Nerja":                        (36.7439, -3.8722, 14),
    "Coin":                         (36.6608, -4.7578, 14),
    "Alhaurin de la Torre":         (36.6622, -4.5597, 14),

    # ── Granada ────────────────────────────────────────────────────────────────
    "Granada Capital":              (37.1773, -3.5986, 13),
    "Motril":                       (36.7467, -3.5183, 14),
    "Loja":                         (37.1683, -4.1489, 14),
    "Baza":                         (37.4944, -2.7714, 14),
    "Guadix":                       (37.2994, -3.1386, 14),
    "Almunecar":                    (36.7319, -3.6928, 14),

    # ── Almería ────────────────────────────────────────────────────────────────
    "Almeria Capital":              (36.8340, -2.4637, 13),
    "El Ejido":                     (36.7756, -2.8131, 14),
    "Roquetas de Mar":              (36.7644, -2.6150, 14),
    "Nijar":                        (36.9667, -2.2000, 14),
    "Adra":                         (36.7478, -3.0214, 14),

    # ── Jaén ───────────────────────────────────────────────────────────────────
    "Jaen Capital":                 (37.7796, -3.7849, 13),
    "Linares":                      (38.0894, -3.6369, 14),
    "Ubeda":                        (38.0136, -3.3697, 14),
    "Baeza":                        (37.9939, -3.4719, 14),
    "Andujar":                      (38.0378, -4.0514, 14),

    # ── Córdoba ────────────────────────────────────────────────────────────────
    "Cordoba Capital":              (37.8882, -4.7794, 13),
    "Lucena":                       (37.4086, -4.4853, 14),
    "Montilla":                     (37.5844, -4.6378, 14),
    "Puente Genil":                 (37.3906, -4.7647, 14),
    "Cabra":                        (37.5103, -4.4414, 14),
    "Priego de Cordoba":            (37.4378, -4.1953, 14),
}

ZONAS_ESPANA_EXTRA = {
    # ── Madrid ─────────────────────────────────────────────────────────────────
    "Madrid Centro":                (40.4168, -3.7038, 13),
    "Madrid Norte":                 (40.4800, -3.6900, 13),
    "Madrid Sur":                   (40.3700, -3.7200, 13),
    "Madrid Este":                  (40.4300, -3.6500, 13),
    "Madrid Oeste":                 (40.4200, -3.7800, 13),
    "Alcala de Henares":            (40.4819, -3.3636, 13),
    "Getafe":                       (40.3050, -3.7328, 14),
    "Leganes":                      (40.3289, -3.7642, 14),
    "Alcorcon":                     (40.3456, -3.8233, 14),
    "Mostoles":                     (40.3228, -3.8639, 14),
    "Fuenlabrada":                  (40.2844, -3.7928, 14),
    "Torrejón de Ardoz":            (40.4600, -3.4792, 14),
    "Parla":                        (40.2381, -3.7758, 14),
    "Alcobendas":                   (40.5464, -3.6397, 14),
    "Pozuelo de Alarcon":           (40.4358, -3.8144, 14),

    # ── Barcelona ──────────────────────────────────────────────────────────────
    "Barcelona Centro":             (41.3851, 2.1734, 13),
    "Barcelona Norte":              (41.4200, 2.1700, 13),
    "Barcelona Sur":                (41.3500, 2.1700, 13),
    "Hospitalet de Llobregat":      (41.3597, 2.1000, 14),
    "Badalona":                     (41.4500, 2.2469, 14),
    "Sabadell":                     (41.5433, 2.1083, 13),
    "Terrassa":                     (41.5628, 2.0089, 13),
    "Mataro":                       (41.5381, 2.4472, 14),
    "Cornella de Llobregat":        (41.3544, 2.0703, 14),

    # ── Valencia ───────────────────────────────────────────────────────────────
    "Valencia Capital":             (39.4699, -0.3763, 13),
    "Alicante Capital":             (38.3452, -0.4815, 13),
    "Elche":                        (38.2669, -0.6983, 13),
    "Castellon de la Plana":        (39.9864, -0.0513, 13),
    "Torrevieja":                   (37.9781, -0.6833, 14),
    "Benidorm":                     (38.5419, -0.1233, 14),
    "Gandia":                       (38.9681, -0.1800, 14),

    # ── Murcia ─────────────────────────────────────────────────────────────────
    "Murcia Capital":               (37.9922, -1.1307, 13),
    "Cartagena":                    (37.6006, -0.9819, 13),
    "Lorca":                        (37.6714, -1.7006, 14),
    "Molina de Segura":             (38.0572, -1.2108, 14),
    "Alcantarilla":                 (37.9706, -1.2283, 14),

    # ── País Vasco ─────────────────────────────────────────────────────────────
    "Bilbao":                       (43.2630, -2.9350, 13),
    "San Sebastian":                (43.3183, -1.9812, 13),
    "Vitoria":                      (42.8467, -2.6726, 13),
    "Barakaldo":                    (43.2956, -2.9906, 14),

    # ── Galicia ────────────────────────────────────────────────────────────────
    "Vigo":                         (42.2328, -8.7226, 13),
    "A Coruna":                     (43.3623, -8.4115, 13),
    "Santiago de Compostela":       (42.8782, -8.5448, 13),
    "Ourense":                      (42.3361, -7.8639, 13),
    "Lugo":                         (43.0097, -7.5567, 14),
    "Pontevedra":                   (42.4289, -8.6444, 14),

    # ── Castilla y León ────────────────────────────────────────────────────────
    "Valladolid":                   (41.6523, -4.7245, 13),
    "Burgos":                       (42.3439, -3.6966, 13),
    "Salamanca":                    (40.9701, -5.6635, 13),
    "Leon":                         (42.5987, -5.5671, 13),
    "Palencia":                     (42.0097, -4.5236, 14),
    "Segovia":                      (40.9481, -4.1183, 14),
    "Zamora":                       (41.5028, -5.7446, 14),
    "Avila":                        (40.6564, -4.6814, 14),

    # ── Aragón ─────────────────────────────────────────────────────────────────
    "Zaragoza":                     (41.6561, -0.8773, 13),
    "Huesca":                       (42.1401, -0.4089, 14),
    "Teruel":                       (40.3456, -1.1064, 14),

    # ── Castilla-La Mancha ─────────────────────────────────────────────────────
    "Toledo":                       (39.8628, -4.0273, 13),
    "Albacete":                     (38.9942, -1.8585, 13),
    "Ciudad Real":                  (38.9861, -3.9272, 14),
    "Guadalajara":                  (40.6347, -3.1669, 14),
    "Cuenca":                       (40.0703, -2.1375, 14),

    # ── Extremadura ────────────────────────────────────────────────────────────
    "Badajoz":                      (38.8794, -6.9706, 13),
    "Caceres":                      (39.4753, -6.3723, 13),
    "Merida":                       (38.9167, -6.3400, 14),
    "Plasencia":                    (40.0303, -6.0897, 14),

    # ── Asturias / Cantabria ───────────────────────────────────────────────────
    "Oviedo":                       (43.3619, -5.8494, 13),
    "Gijon":                        (43.5453, -5.6617, 13),
    "Santander":                    (43.4623, -3.8100, 13),
    "Aviles":                       (43.5564, -5.9247, 14),

    # ── Navarra / La Rioja ─────────────────────────────────────────────────────
    "Pamplona":                     (42.8125, -1.6458, 13),
    "Logrono":                      (42.4627, -2.4449, 13),

    # ── Islas Canarias ─────────────────────────────────────────────────────────
    "Las Palmas de Gran Canaria":   (28.1235, -15.4363, 13),
    "Santa Cruz de Tenerife":       (28.4636, -16.2518, 13),
    "La Laguna":                    (28.4869, -16.3159, 14),
    "Arrecife":                     (28.9631, -13.5478, 14),
    "Puerto del Rosario":           (28.4994, -13.8632, 14),

    # ── Islas Baleares ─────────────────────────────────────────────────────────
    "Palma de Mallorca":            (39.5696, 2.6502, 13),
    "Ibiza":                        (38.9067, 1.4206, 14),
    "Mahon":                        (39.8886, 4.2628, 14),
}

# ─────────────────────────────────────────────────────────────────────────────
# TERRITORIOS — combinaciones de zonas para el scheduler y el panel
# ─────────────────────────────────────────────────────────────────────────────
TERRITORIO_SEVILLA   = {**ZONAS_SEVILLA}
TERRITORIO_ANDALUCIA = {**ZONAS_SEVILLA, **ZONAS_ANDALUCIA_EXTRA}
TERRITORIO_ESPANA    = {**ZONAS_SEVILLA, **ZONAS_ANDALUCIA_EXTRA, **ZONAS_ESPANA_EXTRA}

# ZONAS es el dict global que usa buscar_empresas() — incluye todo
ZONAS = TERRITORIO_ESPANA


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
    max_paginas = 7

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

        if nuevas_en_pagina == 0 and pagina > 0:
            break

        pagina += 1
        if pagina < max_paginas and len(empresas_guardadas) < max_resultados:
            time.sleep(0.4)

    return añadidas


def buscar_empresas(sector, zona, max_resultados=20):
    """
    Busca empresas en Google Maps via SerpAPI con coordenadas GPS.
    Rota queries alternativas por sector para maximizar resultados únicos.
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


def buscar_en_territorio(territorio, sector="general", max_por_zona=30):
    """
    Busca un sector concreto en todas las zonas de un territorio.
    territorio: TERRITORIO_SEVILLA | TERRITORIO_ANDALUCIA | TERRITORIO_ESPANA
    Útil para el scheduler automático cuando rota por zonas.
    """
    crear_tablas()
    total = 0
    for zona in territorio:
        empresas = buscar_empresas(sector, zona, max_resultados=max_por_zona)
        total += len(empresas)
    print(f"\nTotal nuevas en territorio: {total}")
    return total


def buscar_todo(max_por_busqueda=30):
    """Busca todos los sectores en todas las zonas configuradas (ZONAS = España entera)."""
    crear_tablas()
    total = 0
    for zona in ZONAS:
        for sector in SECTORES:
            empresas = buscar_empresas(sector, zona, max_resultados=max_por_busqueda)
            total += len(empresas)
    print(f"\nTotal empresas nuevas guardadas: {total}")


if __name__ == "__main__":
    buscar_todo()