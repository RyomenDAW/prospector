"""
dedup.py — Detección de empresas duplicadas

Problema que resuelve:
  "INSERT OR IGNORE" de SQLite solo evita duplicados de nombre EXACTO.
  Pero estas son la MISMA empresa:
    - "Bar Pepe"
    - "Bar Pepe S.L."
    - "BAR PEPE"
    - "Bar  Pepe" (doble espacio)
  Y contactarlas 3 veces = spam = baneo de WhatsApp.

Estrategia de detección:
  1. Normalizar nombres (minúsculas, sin tildes, sin sufijos legales)
  2. Comparar similitud con SequenceMatcher (biblioteca estándar, sin deps)
  3. Comparar teléfonos normalizados (si dos tienen el mismo tel, son la misma)

No usa librerías externas (fuzzywuzzy/rapidfuzz) para mantener el proyecto
ligero. difflib.SequenceMatcher viene en la stdlib de Python.
"""

import re
import unicodedata
from difflib import SequenceMatcher

from database import get_connection, actualizar_empresa
from logger import get_logger

log = get_logger(__name__)

# Umbral de similitud (0-1). Por encima de esto se consideran duplicados.
UMBRAL_SIMILITUD = 0.87

# Sufijos legales y palabras a ignorar al comparar nombres
SUFIJOS_LEGALES = [
    "sl", "s.l.", "sociedad limitada",
    "sa", "s.a.", "sociedad anonima",
    "slu", "s.l.u.",
    "scp", "s.c.p.",
    "cb", "c.b.",
    "sll", "s.l.l.",
]


def normalizar_nombre(nombre):
    """
    Normaliza un nombre de empresa para comparación.

    "Bar Pepe S.L." → "bar pepe"
    "RESTAURANTE José García" → "restaurante jose garcia"
    """
    if not nombre:
        return ""

    # A minúsculas
    n = nombre.lower().strip()

    # Quitar tildes (José → jose)
    n = unicodedata.normalize("NFKD", n)
    n = "".join(c for c in n if not unicodedata.combining(c))

    # Quitar sufijos legales
    for sufijo in SUFIJOS_LEGALES:
        n = n.replace(sufijo, "")

    # Quitar puntuación y espacios múltiples
    n = re.sub(r'[^\w\s]', '', n)
    n = re.sub(r'\s+', ' ', n).strip()

    return n


def similitud(nombre_a, nombre_b):
    """
    Devuelve la similitud entre dos nombres (0-1).
    1.0 = idénticos, 0.0 = completamente distintos.
    """
    a = normalizar_nombre(nombre_a)
    b = normalizar_nombre(nombre_b)

    if not a or not b:
        return 0.0

    return SequenceMatcher(None, a, b).ratio()


def encontrar_duplicados():
    """
    Recorre todas las empresas y detecta duplicados por:
      1. Teléfono normalizado igual
      2. Nombre muy similar (>= UMBRAL_SIMILITUD)

    Devuelve una lista de grupos de duplicados.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, nombre, telefono, telefono_normalizado, direccion
        FROM empresas
        ORDER BY id
    """)
    empresas = [dict(e) for e in cursor.fetchall()]
    conn.close()

    duplicados = []
    procesados = set()

    for i, emp_a in enumerate(empresas):
        if emp_a["id"] in procesados:
            continue

        grupo = [emp_a]

        for emp_b in empresas[i + 1:]:
            if emp_b["id"] in procesados:
                continue

            es_duplicado = False

            # Criterio 1 — mismo teléfono normalizado
            tel_a = emp_a.get("telefono_normalizado")
            tel_b = emp_b.get("telefono_normalizado")
            if tel_a and tel_b and tel_a == tel_b:
                es_duplicado = True

            # Criterio 2 — nombre muy similar
            elif similitud(emp_a["nombre"], emp_b["nombre"]) >= UMBRAL_SIMILITUD:
                es_duplicado = True

            if es_duplicado:
                grupo.append(emp_b)
                procesados.add(emp_b["id"])

        if len(grupo) > 1:
            duplicados.append(grupo)
            procesados.add(emp_a["id"])

    return duplicados


def marcar_duplicados(dry_run=True):
    """
    Detecta duplicados y marca todos menos el primero (el más antiguo)
    como estado 'duplicada' para que no se contacten.

    Args:
        dry_run: si True, solo muestra qué haría sin tocar la BD
    """
    grupos = encontrar_duplicados()

    if not grupos:
        log.info("No se encontraron duplicados.")
        return

    log.info("Encontrados %d grupos de duplicados:", len(grupos))

    total_marcados = 0
    for grupo in grupos:
        # El primero (más antiguo) se queda, el resto se marcan
        principal = grupo[0]
        duplicados = grupo[1:]

        log.info(
            "  Grupo: '%s' (#%d) tiene %d duplicado(s)",
            principal["nombre"][:40], principal["id"], len(duplicados)
        )

        for dup in duplicados:
            log.info("    → '%s' (#%d)", dup["nombre"][:40], dup["id"])
            if not dry_run:
                actualizar_empresa(dup["id"], {"estado": "duplicada"})
            total_marcados += 1

    if dry_run:
        log.info("[DRY RUN] Se marcarían %d empresas como duplicadas.", total_marcados)
        log.info("Ejecuta con dry_run=False para aplicar los cambios.")
    else:
        log.info("✓ %d empresas marcadas como duplicadas.", total_marcados)


def existe_similar(nombre, telefono=None):
    """
    Comprueba si ya existe una empresa similar ANTES de insertarla.
    Útil para llamar desde searcher.py antes de cada INSERT.

    Returns:
        El id de la empresa similar si existe, None si no.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nombre, telefono_normalizado FROM empresas")
    empresas = [dict(e) for e in cursor.fetchall()]
    conn.close()

    for emp in empresas:
        # Mismo teléfono
        if telefono and emp.get("telefono_normalizado") == telefono:
            return emp["id"]
        # Nombre similar
        if similitud(nombre, emp["nombre"]) >= UMBRAL_SIMILITUD:
            return emp["id"]

    return None


if __name__ == "__main__":
    import sys
    aplicar = "--aplicar" in sys.argv
    marcar_duplicados(dry_run=not aplicar)