"""
config.py — Configuración centralizada del Prospector

Single source of truth. TODA la configuración del sistema vive aquí.
Si Miguel Ángel quiere cambiar el límite de envíos o el horario,
solo se toca este archivo.

Justificación de arquitectura:
  Tener las constantes repartidas por los archivos es deuda técnica.
  Centralizar permite cambiar comportamiento sin tocar lógica.
"""

import os
from dotenv import load_dotenv

load_dotenv()


# ─────────────────────────────────────────────
# EVOLUTION API (WhatsApp)
# ─────────────────────────────────────────────
EVOLUTION_API_URL = os.getenv(
    "EVOLUTION_API_URL",
    "https://evolution-api-production-a35e2.up.railway.app"
)
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY", "laguia_evo_2026")
EVOLUTION_INSTANCE = os.getenv("EVOLUTION_INSTANCE", "laguia")


# ─────────────────────────────────────────────
# APIs externas
# ─────────────────────────────────────────────
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
PAGESPEED_KEY = os.getenv("PAGESPEED_KEY", "")

# Modelo de Claude para generar mensajes
CLAUDE_MODEL = "claude-sonnet-4-5"
CLAUDE_MAX_TOKENS = 300


# ─────────────────────────────────────────────
# CRM (integración para crear leads)
# ─────────────────────────────────────────────
CRM_API_URL = os.getenv(
    "CRM_API_URL",
    "https://crm-automatizacion-production-089b.up.railway.app"
)
# Token de servicio para que el prospector pueda crear leads en el CRM
CRM_API_TOKEN = os.getenv("CRM_API_TOKEN", "")


# ─────────────────────────────────────────────
# LÍMITES Y VELOCIDAD DE ENVÍO
# ─────────────────────────────────────────────
MAX_ENVIOS_DIA = 50           # máximo de mensajes nuevos por día
ESPERA_MIN_SEGUNDOS = 120     # 2 minutos entre envíos
ESPERA_MAX_SEGUNDOS = 480     # 8 minutos entre envíos

# Warm-up gradual (días desde el primer uso → límite ese día)
# Para no levantar sospechas en WhatsApp con un número nuevo
WARMUP = {
    1: 5,    # semana 1: 5/día
    2: 10,   # semana 2: 10/día
    3: 20,   # semana 3: 20/día
    4: 30,   # semana 4: 30/día
    5: 50,   # semana 5+: 50/día (máximo)
}


# ─────────────────────────────────────────────
# HORARIO COMERCIAL (hora de España)
# (día_semana: (hora_inicio, hora_fin)) — None = no enviar
# ─────────────────────────────────────────────
HORARIO_ENVIO = {
    0: (9, 20),   # Lunes
    1: (9, 20),   # Martes
    2: (9, 20),   # Miércoles
    3: (9, 20),   # Jueves
    4: (9, 20),   # Viernes
    5: (10, 14),  # Sábado
    6: None,      # Domingo — NO ENVIAR
}


# ─────────────────────────────────────────────
# SEGUIMIENTO (follow-up)
# ─────────────────────────────────────────────
DIAS_PARA_FOLLOWUP_1 = 4   # días sin respuesta → primer follow-up
DIAS_PARA_FOLLOWUP_2 = 5   # días desde follow-up 1 → segundo follow-up
MAX_INTENTOS = 3           # tras 3 intentos sin respuesta → PERDIDA


# ─────────────────────────────────────────────
# SCORING
# ─────────────────────────────────────────────
SCORE_MINIMO_ENVIO = 40    # solo se contactan empresas con score >= 40


# ─────────────────────────────────────────────
# BASE DE DATOS
# ─────────────────────────────────────────────
DB_PATH = "prospector.db"


# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────
LOG_FILE = "prospector.log"
LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR
LOG_MAX_BYTES = 5 * 1024 * 1024  # 5 MB por archivo
LOG_BACKUP_COUNT = 3             # mantener 3 archivos rotados


def validar_config():
    """
    Comprueba que las variables críticas están configuradas.
    Llamar al arrancar para fallar rápido si falta algo.
    """
    errores = []

    if not SERPAPI_KEY:
        errores.append("SERPAPI_KEY no configurada")
    if not ANTHROPIC_API_KEY:
        errores.append("ANTHROPIC_API_KEY no configurada")
    if not EVOLUTION_API_KEY:
        errores.append("EVOLUTION_API_KEY no configurada")

    if errores:
        print("⚠ Errores de configuración:")
        for e in errores:
            print(f"  - {e}")
        return False

    return True


if __name__ == "__main__":
    print("Configuración del Prospector:")
    print(f"  Evolution API: {EVOLUTION_API_URL}")
    print(f"  Instancia: {EVOLUTION_INSTANCE}")
    print(f"  Máx envíos/día: {MAX_ENVIOS_DIA}")
    print(f"  Score mínimo: {SCORE_MINIMO_ENVIO}")
    print()
    if validar_config():
        print("✓ Configuración válida")
    else:
        print("✗ Faltan variables")