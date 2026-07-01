import os
from dotenv import load_dotenv
from serpapi import GoogleSearch
from database import insertar_empresa, crear_tablas

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
]

ZONAS = [
    "Sevilla",
    "Dos Hermanas",
    "Alcala de Guadaira",
    "Mairena del Aljarafe",
    "Utrera",
    "Carmona",
    "Ecija",
]

def buscar_empresas(sector, zona, max_resultados=20):
    print(f"Buscando: {sector} en {zona}...")

    params = {
        "engine": "google_maps",
        "q": f"{sector} en {zona}",
        "hl": "es",
        "api_key": SERPAPI_KEY,
    }

    search = GoogleSearch(params)
    results = search.get_dict()

    empresas = []
    for lugar in results.get("local_results", [])[:max_resultados]:
        datos = {
            "nombre":     lugar.get("title", ""),
            "sector":     sector,
            "direccion":  lugar.get("address", ""),
            "telefono":   lugar.get("phone", ""),
            "web":        lugar.get("website", ""),
            "valoracion": lugar.get("rating", 0),
            "num_resenas": lugar.get("reviews", 0),
        }

        if datos["nombre"]:
            empresa_id = insertar_empresa(datos)
            datos["id"] = empresa_id
            empresas.append(datos)
            print(f"  ✓ {datos['nombre']} — {datos['telefono']}")

    print(f"  Total: {len(empresas)} empresas encontradas.")
    return empresas

def buscar_todo():
    """Busca en todos los sectores y zonas configurados."""
    crear_tablas()
    total = 0
    for zona in ZONAS:
        for sector in SECTORES:
            empresas = buscar_empresas(sector, zona, max_resultados=10)
            total += len(empresas)
    print(f"\nTotal empresas guardadas: {total}")

if __name__ == "__main__":
    buscar_todo()