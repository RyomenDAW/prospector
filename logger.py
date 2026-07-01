"""
logger.py — Sistema de logging del Prospector

Reemplaza los print() por un logging profesional que:
  - Escribe a archivo (prospector.log) con rotación automática
  - También muestra en consola
  - Incluye timestamp, nivel y origen del mensaje
  - Sobrevive a reinicios (los print se pierden, los logs no)

Justificación:
  Si un envío falla a las 3AM en un cron, necesitas saberlo. Los print()
  desaparecen. Un log en archivo te dice qué pasó, cuándo y por qué.

Uso en cualquier archivo:
    from logger import get_logger
    log = get_logger(__name__)
    log.info("Mensaje enviado a %s", telefono)
    log.error("Falló el envío: %s", error)
"""

import logging
from logging.handlers import RotatingFileHandler

import config


def get_logger(nombre):
    """
    Devuelve un logger configurado.

    Args:
        nombre: normalmente __name__ del módulo que lo usa

    Returns:
        logging.Logger configurado
    """
    logger = logging.getLogger(nombre)

    # Evitar añadir handlers duplicados si se llama varias veces
    if logger.handlers:
        return logger

    nivel = getattr(logging, config.LOG_LEVEL, logging.INFO)
    logger.setLevel(nivel)

    # Formato: 2026-06-12 15:30:45 [INFO] sender_evolution: Mensaje enviado
    formato = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Handler 1 — Archivo con rotación
    # Cuando prospector.log llega a 5MB, se renombra y empieza uno nuevo.
    # Se conservan los últimos 3 archivos.
    file_handler = RotatingFileHandler(
        config.LOG_FILE,
        maxBytes=config.LOG_MAX_BYTES,
        backupCount=config.LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(formato)
    logger.addHandler(file_handler)

    # Handler 2 — Consola (para ver en tiempo real)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formato)
    logger.addHandler(console_handler)

    return logger


if __name__ == "__main__":
    # Test del logger
    log = get_logger("test")
    log.debug("Esto es un debug (no se ve si LOG_LEVEL=INFO)")
    log.info("Esto es info")
    log.warning("Esto es un warning")
    log.error("Esto es un error")
    print(f"\nRevisa el archivo {config.LOG_FILE} para ver los logs guardados.")