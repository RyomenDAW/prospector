"""
export.py — Exportación y backup del Prospector

Dos funciones críticas:
  1. Backup de la BD — 548 empresas son trabajo y dinero (SerpAPI cuesta).
     Si prospector.db se corrompe sin backup, se pierde TODO.
  2. Export a CSV/Excel — Miguel Ángel quiere ver los datos en una hoja.

Justificación:
  Un sistema sin backup es una bomba de relojería. Cuando (no si) la BD
  falle, tendrás un respaldo. Y exportar a Excel permite a los comerciales
  trabajar con los datos sin tocar el sistema.
"""

import os
import csv
import shutil
import sqlite3
from datetime import datetime

import config
from database import get_connection, obtener_empresas
from logger import get_logger

log = get_logger(__name__)

# Carpeta donde se guardan backups y exports
CARPETA_BACKUPS = "backups"
CARPETA_EXPORTS = "exports"


def _asegurar_carpeta(carpeta):
    """Crea la carpeta si no existe."""
    if not os.path.exists(carpeta):
        os.makedirs(carpeta)


def hacer_backup():
    """
    Copia prospector.db a backups/ con timestamp.
    Mantiene solo los últimos 10 backups.
    """
    _asegurar_carpeta(CARPETA_BACKUPS)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = os.path.join(CARPETA_BACKUPS, f"prospector_{timestamp}.db")

    try:
        shutil.copy2(config.DB_PATH, destino)
        log.info("Backup creado: %s", destino)
    except Exception as e:
        log.error("Error creando backup: %s", e)
        return None

    # Limpiar backups antiguos (mantener solo 10)
    _limpiar_backups_antiguos(max_backups=10)

    return destino


def _limpiar_backups_antiguos(max_backups=10):
    """Elimina los backups más antiguos si hay más de max_backups."""
    backups = sorted([
        os.path.join(CARPETA_BACKUPS, f)
        for f in os.listdir(CARPETA_BACKUPS)
        if f.startswith("prospector_") and f.endswith(".db")
    ])

    while len(backups) > max_backups:
        antiguo = backups.pop(0)
        try:
            os.remove(antiguo)
            log.info("Backup antiguo eliminado: %s", antiguo)
        except Exception as e:
            log.error("Error eliminando backup: %s", e)


def exportar_csv(solo_estado=None):
    """
    Exporta las empresas a un CSV.

    Args:
        solo_estado: si se indica, solo exporta empresas de ese estado
                     (ej: "respondida", "enviada")
    """
    _asegurar_carpeta(CARPETA_EXPORTS)

    empresas = obtener_empresas(estado=solo_estado)

    if not empresas:
        log.warning("No hay empresas para exportar.")
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    sufijo = f"_{solo_estado}" if solo_estado else ""
    destino = os.path.join(CARPETA_EXPORTS, f"empresas{sufijo}_{timestamp}.csv")

    # Columnas a exportar (las más útiles para un comercial)
    columnas = [
        "id", "nombre", "sector", "zona", "telefono_normalizado",
        "email", "web", "score", "estado", "intentos_contacto",
        "fecha_envio", "fecha_respuesta", "opt_out",
    ]

    try:
        with open(destino, "w", newline="", encoding="utf-8-sig") as f:
            # utf-8-sig para que Excel abra bien las tildes
            writer = csv.DictWriter(f, fieldnames=columnas, extrasaction="ignore")
            writer.writeheader()
            for empresa in empresas:
                writer.writerow(empresa)

        log.info("Exportadas %d empresas a %s", len(empresas), destino)
        return destino

    except Exception as e:
        log.error("Error exportando CSV: %s", e)
        return None


def estadisticas_rapidas():
    """Imprime un resumen rápido del estado de la BD."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT estado, COUNT(*) as n FROM empresas GROUP BY estado")
    por_estado = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) FROM empresas")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM empresas WHERE opt_out = 1")
    opt_outs = cursor.fetchone()[0]

    conn.close()

    print(f"\n{'='*50}")
    print(f"  ESTADÍSTICAS DEL PROSPECTOR")
    print(f"{'='*50}")
    print(f"  Total empresas: {total}")
    print(f"  Opt-outs: {opt_outs}")
    print(f"\n  Por estado:")
    for row in por_estado:
        print(f"    {row['estado']:15} {row['n']:>5}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    import sys

    if "--backup" in sys.argv:
        hacer_backup()
    elif "--csv" in sys.argv:
        exportar_csv()
    elif "--stats" in sys.argv:
        estadisticas_rapidas()
    else:
        # Por defecto: backup + stats
        hacer_backup()
        estadisticas_rapidas()
        print("Opciones: --backup, --csv, --stats")