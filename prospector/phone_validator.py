"""
phone_validator.py — Validación y normalización de teléfonos

Funciones:
  - Normalizar formato (quitar espacios, +, añadir 34)
  - Detectar fijos vs móviles
  - Verificar si tiene WhatsApp (via Evolution API)
"""

import os
import re
import requests
from dotenv import load_dotenv
from database import obtener_empresas, actualizar_empresa

load_dotenv()

EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL", "https://evolution-api-production-a35e2.up.railway.app")
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY", "laguia_evo_2026")
EVOLUTION_INSTANCE = os.getenv("EVOLUTION_INSTANCE", "laguia")


def normalizar_telefono(telefono):
    """
    Limpia y normaliza un número de teléfono español.

    Ejemplos:
      "650 318 597"     → "34650318597"
      "+34 650318597"   → "34650318597"
      "650318597"       → "34650318597"
      "34650318597"     → "34650318597"
      "956 12 34 56"    → "34956123456"  (fijo)
      None              → None
    """
    if not telefono:
        return None

    # Quitar todo lo que no sea dígito
    limpio = re.sub(r'[^\d]', '', telefono)

    # Si empieza por 0034 (código internacional largo)
    if limpio.startswith("0034"):
        limpio = limpio[4:]

    # Si empieza por 34 y tiene 11 dígitos → ya tiene prefijo
    if limpio.startswith("34") and len(limpio) == 11:
        return limpio

    # Si tiene 9 dígitos → número español sin prefijo
    if len(limpio) == 9:
        return "34" + limpio

    # Si tiene 11 dígitos y empieza por 34 → OK
    if len(limpio) == 11 and limpio.startswith("34"):
        return limpio

    # Otros formatos → devolver tal cual (se marcará como inválido)
    return limpio if limpio else None


def es_movil(telefono_normalizado):
    """
    Detecta si un número español es móvil.
    Los fijos empiezan por 9 (después del 34).
    Los móviles empiezan por 6 o 7 (después del 34).
    """
    if not telefono_normalizado or len(telefono_normalizado) != 11:
        return False

    digito = telefono_normalizado[2]  # primer dígito después del 34
    return digito in ('6', '7')


def verificar_whatsapp(telefono_normalizado):
    """
    Verifica si un número tiene WhatsApp usando Evolution API.
    Devuelve True/False o None si no se pudo verificar.
    """
    if not telefono_normalizado:
        return None

    try:
        url = f"{EVOLUTION_API_URL}/chat/whatsappNumbers/{EVOLUTION_INSTANCE}"
        headers = {
            "apikey": EVOLUTION_API_KEY,
            "Content-Type": "application/json",
        }
        payload = {
            "numbers": [telefono_normalizado]
        }

        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        # Evolution devuelve una lista con los resultados
        if isinstance(data, list) and len(data) > 0:
            return data[0].get("exists", False)

        return None

    except Exception as e:
        print(f"  ⚠ Error verificando WhatsApp para {telefono_normalizado}: {e}")
        return None


def validar_todas():
    """
    Normaliza todos los teléfonos en la BD y verifica WhatsApp.
    Solo verifica los móviles (los fijos no tienen WhatsApp).
    """
    empresas = obtener_empresas()
    print(f"\nEmpresas a validar: {len(empresas)}")

    stats = {"total": 0, "movil": 0, "fijo": 0, "sin_tel": 0, "con_whatsapp": 0}

    for empresa in empresas:
        telefono_raw = empresa.get("telefono")
        stats["total"] += 1

        if not telefono_raw:
            stats["sin_tel"] += 1
            continue

        # Normalizar
        normalizado = normalizar_telefono(telefono_raw)

        if not normalizado:
            stats["sin_tel"] += 1
            actualizar_empresa(empresa["id"], {
                "telefono_normalizado": None,
                "tiene_whatsapp": 0,
            })
            continue

        # Detectar si es móvil o fijo
        if es_movil(normalizado):
            stats["movil"] += 1
            tiene_wa = -1  # pendiente de verificar

            # Solo verificar WhatsApp si no se ha verificado antes
            if empresa.get("tiene_whatsapp", -1) == -1:
                resultado = verificar_whatsapp(normalizado)
                if resultado is True:
                    tiene_wa = 1
                    stats["con_whatsapp"] += 1
                    print(f"  ✓ {empresa['nombre'][:40]} — {normalizado} — WhatsApp ✓")
                elif resultado is False:
                    tiene_wa = 0
                    print(f"  ✗ {empresa['nombre'][:40]} — {normalizado} — Sin WhatsApp")
                else:
                    tiene_wa = -1  # no se pudo verificar
                    print(f"  ? {empresa['nombre'][:40]} — {normalizado} — No verificado")
            else:
                tiene_wa = empresa.get("tiene_whatsapp", -1)

            actualizar_empresa(empresa["id"], {
                "telefono_normalizado": normalizado,
                "tiene_whatsapp": tiene_wa,
            })
        else:
            stats["fijo"] += 1
            actualizar_empresa(empresa["id"], {
                "telefono_normalizado": normalizado,
                "tiene_whatsapp": 0,  # fijos no tienen WhatsApp
            })
            print(f"  ☎ {empresa['nombre'][:40]} — {normalizado} — Fijo (sin WhatsApp)")

    print(f"\n--- Resumen ---")
    print(f"  Total: {stats['total']}")
    print(f"  Móviles: {stats['movil']}")
    print(f"  Fijos: {stats['fijo']}")
    print(f"  Sin teléfono: {stats['sin_tel']}")
    print(f"  Con WhatsApp confirmado: {stats['con_whatsapp']}")


if __name__ == "__main__":
    validar_todas()