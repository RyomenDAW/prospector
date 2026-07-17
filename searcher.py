import os
from dotenv import load_dotenv
from serpapi import GoogleSearch
from database import insertar_empresa, crear_tablas

load_dotenv()

SERPAPI_KEY = os.getenv("SERPAPI_KEY")

# ─────────────────────────────────────────────
# SECTORES
# "general" busca negocios de cualquier tipo — ideal para barrios
# pequeños donde buscar por sector da pocos resultados.
# ─────────────────────────────────────────────
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
    "general",
]

# Queries de búsqueda para el modo "general".
# Se lanzan todas y se deduplican por teléfono.
QUERIES_GENERAL = [
    "negocios locales",
    "empresas",
    "comercios",
    "tiendas",
    "servicios",
]

# ─────────────────────────────────────────────
# ZONAS CON COORDENADAS GPS
# Google Maps responde MUCHO mejor con el parámetro ll (lat,lng,zoom)
# que con texto "en Dos Hermanas". El zoom 14 cubre ~5km de radio,
# suficiente para un municipio. El 13 cubre ~10km para zonas grandes.
# ─────────────────────────────────────────────
ZONAS = {
    # Municipios — zoom 14 (radio ~5km)
    "Dos Hermanas":          "@37.2836,-5.9221,14z",
    "Alcala de Guadaira":    "@37.3392,-5.8379,14z",
    "Mairena del Aljarafe":  "@37.3447,-6.0636,14z",
    "Utrera":                "@37.1861,-5.7816,14z",
    "Carmona":               "@37.4710,-5.6430,14z",
    "Ecija":                 "@37.5413,-5.0827,14z",
    "Coria del Rio":         "@37.2873,-6.0541,14z",
    "La Rinconada":          "@37.4867,-5.9813,14z",
    "Bormujos":              "@37.3720,-6.0711,14z",
    "Tomares":               "@37.3730,-6.0464,14z",
    "San Juan de Aznalfarache": "@37.3663,-6.0286,14z",
    "Gines":                 "@37.3842,-6.0773,14z",
    "Espartinas":            "@37.3881,-6.1232,14z",
    "Gelves":                "@37.3352,-6.0266,14z",
    "Castilleja de la Cuesta": "@37.3831,-6.0535,14z",

    # Sevilla capital — zoom 15 (radio ~2.5km, más preciso por barrio)
    "Sevilla Centro":        "@37.3886,-5.9953,15z",
    "Sevilla Triana":        "@37.3826,-6.0055,15z",
    "Sevilla Nervion":       "@37.3879,-5.9743,15z",
    "Sevilla Macarena":      "@37.4038,-5.9899,15z",
    "Sevilla Este":          "@37.3942,-5.9373,15z",
    "Sevilla Los Remedios":  "@37.3757,-6.0070,15z",
    "Sevilla Bellavista":    "@37.3504,-5.9789,15z",
    "Sevilla Cerro del Aguila": "@37.3741,-5.9621,15z",
    "Sevilla San Pablo":     "@37.4047,-5.9706,15z",
    "Sevilla Pino Montano":  "@37.4200,-5.9900,15z",
    "Sevilla Bermejales":    "@37.3546,-5.9876,15z",
    "Sevilla Santa Justa":   "@37.3925,-5.9760,15z",
    "Sevilla Heliópolis":    "@37.3538,-5.9864,15z",
    "Sevilla Torreblanca":   "@37.3850,-5.9440,15z",
    "Sevilla Alcosa":        "@37.4040,-5.9390,15z",
    "Sevilla San Bernardo":  "@37.3794,-5.9838,15z",
    "Sevilla La Palmera":    "@37.3560,-5.9810,15z",
}

# Lista plana de nombres de zona para el dropdown del panel
ZONAS_NOMBRES = list(ZONAS.keys())


def buscar_empresas(sector, zona, max_resultados=20):
    """
    Busca empresas en Google Maps por sector y zona.

    MEJORAS vs versión anterior:
    - Usa coordenadas GPS (ll) en vez de texto "en zona" → más resultados
    - Pagina automáticamente hasta max_resultados → antes solo 1ª página
    - Modo "general" busca con múltiples queries genéricas
    - Deduplica por teléfono dentro de la misma búsqueda
    """
    print(f"Buscando: {sector} en {zona}...")

    if sector == "general":
        return _buscar_general(zona, max_resultados)

    resultados = _buscar_con_paginacion(sector, zona, max_resultados)
    empresas = _procesar_y_guardar(resultados, sector)
    print(f"  Total: {len(empresas)} empresas guardadas.")
    return empresas


def _buscar_general(zona, max_resultados):
    """
    Modo general: lanza varias queries genéricas y deduplica por teléfono.
    Ideal para zonas pequeñas donde buscar por sector da pocos resultados.
    """
    todos = []
    telefonos_vistos = set()

    for query in QUERIES_GENERAL:
        resultados = _buscar_con_paginacion(query, zona, max_resultados=20)
        for r in resultados:
            tel = r.get("phone", "")
            if tel and tel not in telefonos_vistos:
                telefonos_vistos.add(tel)
                todos.append(r)

    # Para "general" inferimos el sector del tipo de Google Maps
    empresas = _procesar_y_guardar(todos[:max_resultados], "general")
    print(f"  Total general: {len(empresas)} empresas guardadas.")
    return empresas


def _buscar_con_paginacion(query_sector, zona, max_resultados=20):
    """
    Busca en Google Maps con paginación automática.

    SerpAPI devuelve ~20 resultados por página. Si pides 40,
    hace 2 llamadas (start=0 y start=20). Cada llamada consume
    1 crédito de SerpAPI.
    """
    coordenadas = ZONAS.get(zona)
    todos = []
    start = 0
    paginas_max = (max_resultados + 19) // 20  # ceil division

    for _ in range(paginas_max):
        if len(todos) >= max_resultados:
            break

        params = {
            "engine": "google_maps",
            "q": query_sector,
            "hl": "es",
            "api_key": SERPAPI_KEY,
            "start": start,
        }

        # Si tenemos coordenadas, usarlas (mucho más preciso).
        # Si no, fallback al texto "en zona" como antes.
        if coordenadas:
            params["ll"] = coordenadas
        else:
            params["q"] = f"{query_sector} en {zona}"

        try:
            search = GoogleSearch(params)
            results = search.get_dict()
        except Exception as e:
            print(f"  ✗ Error SerpAPI página {start}: {e}")
            break

        local = results.get("local_results", [])
        if not local:
            break  # No hay más resultados

        todos.extend(local)
        start += 20

        # Si devolvió menos de 20, no hay siguiente página
        if len(local) < 20:
            break

    return todos[:max_resultados]


def _procesar_y_guardar(resultados, sector):
    """Filtra, normaliza y guarda en BD. Devuelve lista de empresas guardadas."""
    empresas = []
    for lugar in resultados:
        datos = {
            "nombre":      lugar.get("title", ""),
            "sector":      sector,
            "direccion":   lugar.get("address", ""),
            "telefono":    lugar.get("phone", ""),
            "web":         lugar.get("website", ""),
            "valoracion":  lugar.get("rating", 0),
            "num_resenas": lugar.get("reviews", 0),
        }

        # Sin nombre o sin teléfono no tiene sentido prospectar
        if not datos["nombre"] or not datos["telefono"]:
            continue

        empresa_id = insertar_empresa(datos)
        if empresa_id:
            datos["id"] = empresa_id
            empresas.append(datos)
            print(f"  ✓ {datos['nombre']} — {datos['telefono']}")

    return empresas


def buscar_todo():
    """Busca en todos los sectores y zonas configurados."""
    crear_tablas()
    total = 0
    for zona in ZONAS:
        for sector in SECTORES:
            if sector == "general":
                continue  # general se lanza aparte, no en el barrido masivo
            empresas = buscar_empresas(sector, zona, max_resultados=20)
            total += len(empresas)
    print(f"\nTotal empresas guardadas: {total}")


if __name__ == "__main__":
    buscar_todo()