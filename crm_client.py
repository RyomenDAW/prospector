"""
crm_client.py — Cliente HTTP para la API del CRM

- Login automático con usuario de servicio (token en memoria)
- Refresh automático si el token caduca (401 → relogin → reintento)
- Crear conversación en el CRM tras enviar desde el prospector
- Registrar el mensaje saliente para que aparezca en el chat del CRM
"""

import requests
import config
from logger import get_logger

log = get_logger(__name__)

_access_token: str = ""


def _login() -> bool:
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


def _post(url: str, payload: dict) -> requests.Response | None:
    """
    POST con reintento automático si el token caduca (401).
    Devuelve el Response o None si falla.
    """
    global _access_token

    if not _access_token:
        if not _login():
            return None

    resp = requests.post(url, json=payload, headers=_headers(), timeout=10)

    if resp.status_code == 401:
        log.warning("Token CRM caducado — relogin...")
        if not _login():
            return None
        resp = requests.post(url, json=payload, headers=_headers(), timeout=10)

    return resp


def crear_conversacion_crm(telefono: str, nombre: str, mensaje_texto: str, wamid: str = "") -> bool:
    """
    1. Crea (o recupera) la conversación en el CRM para este teléfono.
    2. Registra el mensaje saliente para que aparezca en el chat del CRM.

    Args:
        telefono:      número normalizado (ej: "34954140565")
        nombre:        nombre para el sidebar (ej: "[PROSPECTOR] Farmacia Martín López")
        mensaje_texto: texto exacto de la plantilla enviada (para mostrarlo en el chat)
        wamid:         ID de mensaje de Meta (wamid.xxx) para trazabilidad

    Returns:
        True si todo fue bien. False si hubo error (no bloquea el flujo).
    """
    # ── 1. Crear o recuperar conversación ────────────────────────────────────
    url_conv = f"{config.CRM_API_URL}/api/whatsapp/conversaciones/nueva/"
    resp = _post(url_conv, {"telefono": telefono, "nombre_contacto": nombre})

    if not resp or not resp.ok:
        log.error("Error creando conversación CRM: %s", resp.text if resp else "sin respuesta")
        return False

    conv_id = resp.json().get("id")
    accion = "creada" if resp.status_code == 201 else "ya existía"
    log.info("Conversación CRM %s | id=%s | telefono=%s", accion, conv_id, telefono)

    # ── 2. Registrar mensaje saliente ────────────────────────────────────────
    if not conv_id or not mensaje_texto:
        return True  # conversación creada pero sin mensaje que registrar

    url_msg = f"{config.CRM_API_URL}/api/whatsapp/conversaciones/{conv_id}/registrar-prospector/"
    resp_msg = _post(url_msg, {
        "contenido": mensaje_texto,
        "whatsapp_message_id": wamid,
    })

    if not resp_msg or not resp_msg.ok:
        log.error("Error registrando mensaje en CRM: %s", resp_msg.text if resp_msg else "sin respuesta")
        return False

    log.info("Mensaje saliente registrado en CRM | conv_id=%s", conv_id)
    return True