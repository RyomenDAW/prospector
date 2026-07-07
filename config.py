"""
config.py — Configuración centralizada del Prospector
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
# META CLOUD API (envío de plantillas desde el prospector)
# Mismo token y número que el CRM → los chats aparecen en el CRM
# ─────────────────────────────────────────────
WHATSAPP_ACCESS_TOKEN    = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")


# ─────────────────────────────────────────────
# APIs externas
# ─────────────────────────────────────────────
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
PAGESPEED_KEY = os.getenv("PAGESPEED_KEY", "")

CLAUDE_MODEL = "claude-sonnet-4-5"
CLAUDE_MAX_TOKENS = 300


# ─────────────────────────────────────────────
# CRM (integración para crear leads)
# ─────────────────────────────────────────────

CRM_API_TOKEN = os.getenv("CRM_API_TOKEN", "")
CRM_API_URL          = os.getenv("CRM_API_URL", "https://crm-automatizacion-production-089b.up.railway.app")
CRM_SERVICE_USER     = os.getenv("CRM_SERVICE_USER", "prospector")
CRM_SERVICE_PASSWORD = os.getenv("CRM_SERVICE_PASSWORD", "")

# ─────────────────────────────────────────────
# LÍMITES Y VELOCIDAD DE ENVÍO
# ─────────────────────────────────────────────
MAX_ENVIOS_DIA = 50
ESPERA_MIN_SEGUNDOS = 120
ESPERA_MAX_SEGUNDOS = 480

WARMUP = {
    1: 5,
    2: 10,
    3: 20,
    4: 30,
    5: 50,
}


# ─────────────────────────────────────────────
# HORARIO COMERCIAL
# ─────────────────────────────────────────────
HORARIO_ENVIO = {
    0: (9, 20),
    1: (9, 20),
    2: (9, 20),
    3: (9, 20),
    4: (9, 20),
    5: (10, 14),
    6: None,
}


# ─────────────────────────────────────────────
# SEGUIMIENTO
# ─────────────────────────────────────────────
DIAS_PARA_FOLLOWUP_1 = 4
DIAS_PARA_FOLLOWUP_2 = 5
MAX_INTENTOS = 3


# ─────────────────────────────────────────────
# SCORING
# ─────────────────────────────────────────────
SCORE_MINIMO_ENVIO = 40


# ─────────────────────────────────────────────
# BASE DE DATOS
# ─────────────────────────────────────────────
DB_PATH = "prospector.db"


# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────
LOG_FILE = "prospector.log"
LOG_LEVEL = "INFO"
LOG_MAX_BYTES = 5 * 1024 * 1024
LOG_BACKUP_COUNT = 3


def validar_config():
    errores = []

    if not SERPAPI_KEY:
        errores.append("SERPAPI_KEY no configurada")
    if not ANTHROPIC_API_KEY:
        errores.append("ANTHROPIC_API_KEY no configurada")
    if not WHATSAPP_ACCESS_TOKEN:
        errores.append("WHATSAPP_ACCESS_TOKEN no configurada")
    if not WHATSAPP_PHONE_NUMBER_ID:
        errores.append("WHATSAPP_PHONE_NUMBER_ID no configurada")

    if errores:
        print("⚠ Errores de configuración:")
        for e in errores:
            print(f"  - {e}")
        return False

    return True


if __name__ == "__main__":
    print("Configuración del Prospector:")
    print(f"  Meta Phone Number ID: {WHATSAPP_PHONE_NUMBER_ID}")
    print(f"  Máx envíos/día: {MAX_ENVIOS_DIA}")
    print(f"  Score mínimo: {SCORE_MINIMO_ENVIO}")
    print()
    if validar_config():
        print("✓ Configuración válida")
    else:
        print("✗ Faltan variables")