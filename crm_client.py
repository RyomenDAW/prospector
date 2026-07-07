"""
crm_client.py — Cliente HTTP para la API del CRM

Responsabilidad única: comunicar el prospector con el CRM.
  - Login automático al arrancar (token en memoria, sin caducidad problemática)
  - Refresh automático si el token caduca (401 → relogin → reintento)
  - Crear conversación en el CRM tras enviar un WhatsApp desde el prospector

Uso en sender.py:
    from crm_client import crear_conversacion_crm
    crear_conversacion_crm(telefono=empresa["telefono"], nombre=empresa["nombre"])
"""

import requests
import config
from logger import get_logger

log = get_logger(__name__)

# Token en memoria — se rellena en el primer uso y se refresca si caduca
_access_token: str = ""


def _login() -> bool:
    """
    Hace login con el usuario de servicio del prospector y guarda el token.
    Devuelve True si tuvo éxito.
    """
    global _access_token
    url = f"{config.CRM_API_URL}/api/auth/login/"
    try:
        resp = requests.post(url, json={
            "username": config.CRM_SERVICE_USER,
            "password": config.CRM_SERVICE_PASSWORD,
        }, timeout=10)
        resp.raise_for_status()
        _access_token = resp.json().get("access", "")
        log.info("CRM login OK — token obtenido")
        return bool(_access_token)
    except Exception as e:
        log.error("CRM login FALLO: %s", e)
        return False


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {_access_token}",
        "Content-Type": "application/json",
    }


def crear_conversacion_crm(telefono: str, nombre: str = "") -> bool:
    """
    Crea (o recupera si ya existe) una conversación en el CRM para este teléfono.
    Se llama justo después de enviar el WhatsApp desde el prospector.

    Args:
        telefono: número normalizado (ej: "34954191560")
        nombre:   nombre del negocio o contacto (para identificarlo en el chat del CRM)

    Returns:
        True si la conversación quedó creada/existente en el CRM.
        False si hubo error (no bloquea el flujo del prospector).
    """
    global _access_token

    # Login si no tenemos token todavía
    if not _access_token:
        if not _login():
            return False

    url = f"{config.CRM_API_URL}/api/whatsapp/conversaciones/nueva/"
    payload = {"telefono": telefono, "nombre_contacto": nombre}

    try:
        resp = requests.post(url, json=payload, headers=_headers(), timeout=10)

        # Token caducado → relogin y reintento
        if resp.status_code == 401:
            log.warning("Token CRM caducado — relogin...")
            if not _login():
                return False
            resp = requests.post(url, json=payload, headers=_headers(), timeout=10)

        resp.raise_for_status()
        data = resp.json()
        log.info(
            "Conversación CRM %s | telefono=%s | nombre=%s",
            "creada" if resp.status_code == 201 else "ya existía",
            telefono,
            nombre,
        )
        return True

    except Exception as e:
        log.error("Error creando conversación en CRM: %s", e)
        return False  # No bloqueamos el flujo del prospector por esto