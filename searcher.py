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
    # Municipios del Aljarafe y provincia
    "Dos Hermanas",
    "Alcala de Guadaira",
    "Mairena del Aljarafe",
    "Utrera",
    "Carmona",
    "Ecija",

    # Casco Antiguo
    "Sevilla Centro",
    "Sevilla Santa Cruz",
    "Sevilla El Arenal",
    "Sevilla Triana",
    "Sevilla San Vicente",
    "Sevilla Alameda de Hercules",
    "Sevilla La Macarena",
    "Sevilla Feria",

    # Macarena
    "Sevilla San Luis",
    "Sevilla Parlamento",
    "Sevilla Capuchinos",
    "Sevilla La Calzada",
    "Sevilla San Julian",
    "Sevilla Pino Montano",
    "Sevilla Rochelambert",
    "Sevilla Valdezorras",
    "Sevilla Palmete",

    # Norte
    "Sevilla La Bachillera",
    "Sevilla Martires",
    "Sevilla Parque Miraflores",
    "Sevilla Pajares Vistahermosa",

    # Nervion / San Pablo
    "Sevilla Nervion",
    "Sevilla San Bernardo",
    "Sevilla Ciudad Jardin",
    "Sevilla La Florida",
    "Sevilla La Buhaira",
    "Sevilla San Roque",
    "Sevilla Santa Justa",
    "Sevilla San Pablo",

    # Este - Alcosa - Torreblanca
    "Sevilla Torreblanca",
    "Sevilla Alcosa",
    "Sevilla Este",
    "Sevilla Parque Alcosa",

    # Cerro Amate
    "Sevilla Cerro del Aguila",
    "Sevilla Amate",
    "Sevilla Los Pajaritos",
    "Sevilla Su Eminencia",
    "Sevilla Zurbarán",

    # Sur
    "Sevilla Heliópolis",
    "Sevilla Los Bermejales",
    "Sevilla Reina Mercedes",
    "Sevilla Prado San Sebastian",

    # Bellavista - La Palmera
    "Sevilla Bellavista",
    "Sevilla La Palmera",
    "Sevilla Elcano",
    "Sevilla Pineda",

    # Los Remedios
    "Sevilla Los Remedios",
    "Sevilla Tablada",

    # Triana (barrios internos)
    "Sevilla Triana Casco",
    "Sevilla Leon XIII",
    "Sevilla Las Palmeritas",
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

        # POR ESTO:
        if datos["nombre"] and datos["telefono"]:  # ← sin teléfono ya que no tiene sentido prospectar algo que no se puede.
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