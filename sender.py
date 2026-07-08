"""
sender.py — Envío de WhatsApp via Meta Cloud API con plantilla primer_contacto

Plantilla usada: primer_contacto
  {{1}} = nombre del dueño/contacto (o nombre del negocio si no hay contacto)
  {{2}} = sector del negocio

Texto que recibe el destinatario:
  "Hola {{1}}, soy Miguel Ángel de La Guía de Sevilla 🔥
   Trabajamos con negocios de {{2}} en Sevilla y me ha llamado
   la atención tu empresa. Tengo una idea que creo que te puede interesar.
   ¿Tienes 2 minutos para que te cuente?"

El envío via plantilla es el único método válido cuando NOSOTROS iniciamos
la conversación (el destinatario no ha escrito antes en las últimas 24h).

Una vez el prospecto responde, la conversación aparece en el CRM
(mismo número +34 681 96 24 89, mismo WABA) y el equipo continúa
desde el chat del CRM normalmente.
"""

import time
import random
from datetime import datetime

import requests
from crm_client import crear_conversacion_crm
import config
from logger import get_logger
from database import actualizar_empresa, obtener_empresas_enviadas_hoy
from phone_validator import normalizar_telefono

log = get_logger(__name__)

# ─── Plantilla a usar para el primer contacto ─────────────────────────────────
PLANTILLA_NOMBRE = "primer_contacto"
PLANTILLA_IDIOMA = "en"   # está creada en English en Meta

# ─── Meta Cloud API ───────────────────────────────────────────────────────────
META_API_URL = (
    f"https://graph.facebook.com/v19.0/"
    f"{config.WHATSAPP_PHONE_NUMBER_ID}/messages"
)


def _headers():
    return {
        "Authorization": f"Bearer {config.WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }


def _limite_efectivo():
    semana = getattr(config, "WARMUP_SEMANA_ACTUAL", max(config.WARMUP.keys()))
    return config.WARMUP.get(semana, config.MAX_ENVIOS_DIA)


def _en_horario_comercial():
    ahora = datetime.now()
    rango = config.HORARIO_ENVIO.get(ahora.weekday())
    if rango is None:
        return False
    return rango[0] <= ahora.hour < rango[1]


def _nombre_para_plantilla(empresa: dict) -> str:
    """
    Devuelve el valor para {{1}}.
    Prioridad: nombre del contacto > nombre del negocio > "amigo"
    """
    nombre = (empresa.get("contacto_nombre") or empresa.get("nombre") or "amigo").strip()
    # Usar solo el primer nombre si es compuesto
    return nombre.split()[0].capitalize()


def _sector_para_plantilla(empresa: dict) -> str:
    """
    Devuelve el valor para {{2}} — sector legible en español.
    """
    mapeo = {
        "restaurantes":        "restauración",
        "clinicas":            "salud y clínicas",
        "clinicas dentales":   "clínicas dentales",
        "inmobiliarias":       "inmobiliarias",
        "talleres":            "talleres mecánicos",
        "talleres mecanicos":  "talleres mecánicos",
        "academias":           "formación y academias",
        "peluquerias":         "peluquería y estética",
        "farmacias":           "farmacias",
        "fontaneros":          "servicios de fontanería",
        "hoteles":             "alojamiento turístico",
        "airbnb":              "alojamiento turístico",
        "gimnasios":           "fitness y salud",
    }
    sector = (empresa.get("sector") or "").lower().strip()
    return mapeo.get(sector, sector or "negocios locales")


# ─────────────────────────────────────────────
# ENVÍO INDIVIDUAL
# ─────────────────────────────────────────────

def enviar_whatsapp(empresa_id: int, telefono: str, empresa: dict) -> dict:
    """
    Envía la plantilla primer_contacto a través de Meta Cloud API.

    Args:
        empresa_id: ID en la BD local
        telefono:   teléfono del destinatario (se normaliza internamente)
        empresa:    dict completo de la empresa (para extraer {{1}} y {{2}})

    Returns:
        {"ok": True,  "message_id": "wamid.xxx"}
        {"ok": False, "error": "descripción"}
    """
    numero = normalizar_telefono(telefono)
    if not numero:
        log.warning("empresa_id=%s — teléfono inválido: %s", empresa_id, telefono)
        return {"ok": False, "error": "Teléfono inválido"}

    nombre = _nombre_para_plantilla(empresa)
    sector = _sector_para_plantilla(empresa)

    payload = {
        "messaging_product": "whatsapp",
        "to": numero,
        "type": "template",
        "template": {
            "name": PLANTILLA_NOMBRE,
            "language": {"code": PLANTILLA_IDIOMA},
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": nombre},   # {{1}}
                        {"type": "text", "text": sector},   # {{2}}
                    ],
                }
            ],
        },
    }

    try:
        resp = requests.post(META_API_URL, json=payload, headers=_headers(), timeout=15)
        resp.raise_for_status()
        data = resp.json()

        # Meta devuelve {"messages": [{"id": "wamid.xxx"}]}
        message_id = data.get("messages", [{}])[0].get("id", "")
        ahora = datetime.now().isoformat()

        actualizar_empresa(empresa_id, {
            "estado":              "enviada",
            "whatsapp_message_id": message_id,
            "fecha_envio":         ahora,
            "fecha_ultimo_intento": ahora,
            "intentos_contacto":   1,
        })

        log.info(
            "ENVIADO empresa_id=%s | numero=%s | nombre=%s | sector=%s | wamid=%s",
            empresa_id, numero, nombre, sector, message_id,
        )

                # Crear conversación en el CRM para que aparezca en el chat
        crear_conversacion_crm(
                telefono=numero,
                nombre=f"[PROSPECTOR] {empresa.get('nombre', '')}",
        )
 

        return {"ok": True, "message_id": message_id}

    except requests.exceptions.HTTPError as e:
        error = f"HTTP {e.response.status_code}: {e.response.text[:300]}"
        log.error("FALLO HTTP empresa_id=%s | %s", empresa_id, error)
        actualizar_empresa(empresa_id, {"fecha_ultimo_intento": datetime.now().isoformat()})
        return {"ok": False, "error": error}

    except requests.exceptions.RequestException as e:
        log.error("FALLO RED empresa_id=%s | %s", empresa_id, str(e))
        actualizar_empresa(empresa_id, {"fecha_ultimo_intento": datetime.now().isoformat()})
        return {"ok": False, "error": str(e)}


# ─────────────────────────────────────────────
# ENVÍO EN LOTE
# ─────────────────────────────────────────────

def enviar_lote(empresas: list) -> dict:
    """
    Envía la plantilla primer_contacto a una lista de empresas
    respetando todos los controles de seguridad.
    """
    resumen = {"enviados": 0, "fallidos": 0, "omitidos": 0}

    if not _en_horario_comercial():
        hora = datetime.now().strftime("%H:%M")
        msg = f"Fuera de horario comercial ({hora})"
        log.warning(msg)
        return {**resumen, "omitidos": len(empresas), "motivo": msg}

    limite      = _limite_efectivo()
    enviadas_hoy = obtener_empresas_enviadas_hoy()

    if enviadas_hoy >= limite:
        msg = f"Límite diario alcanzado: {enviadas_hoy}/{limite}"
        log.warning(msg)
        return {**resumen, "omitidos": len(empresas), "motivo": msg}

    disponibles = limite - enviadas_hoy
    log.info("Inicio lote: %d empresas | disponibles hoy: %d", len(empresas), disponibles)

    for i, empresa in enumerate(empresas):
        if resumen["enviados"] >= disponibles:
            resumen["omitidos"] += len(empresas) - i
            break

        # Guards de seguridad
        if empresa.get("opt_out"):
            log.info("Omitida empresa_id=%s — opt-out", empresa["id"])
            resumen["omitidos"] += 1
            continue

        if not empresa.get("telefono"):
            log.warning("Omitida empresa_id=%s — sin teléfono", empresa["id"])
            resumen["omitidos"] += 1
            continue

        if empresa.get("estado") == "enviada":
            resumen["omitidos"] += 1
            continue

        resultado = enviar_whatsapp(
            empresa_id=empresa["id"],
            telefono=empresa["telefono"],
            empresa=empresa,
        )

        if resultado["ok"]:
            resumen["enviados"] += 1
        else:
            resumen["fallidos"] += 1

        # Espera aleatoria entre mensajes
        hay_mas = (i < len(empresas) - 1) and (resumen["enviados"] < disponibles)
        if hay_mas:
            espera = random.randint(config.ESPERA_MIN_SEGUNDOS, config.ESPERA_MAX_SEGUNDOS)
            log.info("Esperando %ds...", espera)
            time.sleep(espera)

    log.info("Lote completado: %s", resumen)
    return resumen