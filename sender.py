"""
sender.py — Envío de WhatsApp via Meta Cloud API con plantillas

REGISTRO DE PLANTILLAS (PLANTILLAS):
  Cada plantilla define su idioma, sus variables y su texto espejo.
  Para cambiar de plantilla activa basta con tocar PLANTILLA_ACTIVA.

  - primer_contacto            {{1}}=nombre, {{2}}=sector   (idioma: es)
  - primer_contacto_web        {{1}}=nombre                 (idioma: es)
  - primer_contacto_escaparate {{1}}=nombre, {{2}}=sector   (idioma: es) + botón URL
  - seguimiento                {{1}}=nombre                 (idioma: es)

El texto espejo se registra en el chat del CRM tras el envío, para que
Miguel vea en el CRM exactamente lo que se le mandó al prospecto.
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

# ─── Plantilla activa ─────────────────────────────────────────────────────────
# Cambia SOLO esta línea para alternar entre plantillas.
PLANTILLA_ACTIVA = "primer_contacto_escaparate"

# URL del escaparate de servicios (botón de la plantilla).
# Es estática en Meta, aquí se guarda solo para referencia/logs.
URL_ESCAPARATE = "https://laguiadesevilla.es/servicios"


# ─── Registro de plantillas ───────────────────────────────────────────────────
# "vars" define qué variables lleva el body, en orden.
# "texto" debe coincidir con el contenido aprobado en Meta (texto espejo).
# IMPORTANTE: todas las plantillas están en español (idioma: es).
# Asegúrate de que en Meta también están aprobadas con language: es.
PLANTILLAS = {
    "primer_contacto": {
        "idioma": "es",
        "vars": ["nombre", "sector"],
        "texto": (
            "Hola {nombre}, soy Miguel Ángel de La Guía de Sevilla 👋\n\n"
            "Llevamos más de 13 años trabajando con negocios de {sector} en Sevilla. "
            "Los que más crecen digitalmente tienen algo en común "
            "— y creo que tu empresa lo puede aplicar.\n\n"
            "¿Tienes 2 minutos para que te cuente?"
        ),
    },
    "primer_contacto_web": {
        "idioma": "es",
        "vars": ["nombre"],
        "texto": (
            "Hola {nombre}, soy Miguel Ángel de La Guía de Sevilla 👋\n\n"
            "He visto que nos has dejado tus datos a través de nuestra web. "
            "Llevamos más de 13 años ayudando a negocios en Sevilla a crecer "
            "digitalmente y quería escribirte directamente.\n\n"
            "¿Qué es lo que más te preocupa ahora mismo de tu negocio a nivel digital?"
        ),
    },
    "primer_contacto_escaparate": {
        "idioma": "es",
        "vars": ["nombre", "sector"],
        "texto": (
            "Hola {nombre}, soy Miguel Ángel de La Guía de Sevilla 👋\n\n"
            "Llevamos más de 13 años trabajando con negocios de {sector} en Sevilla. "
            "Los que más crecen digitalmente tienen algo en común "
            "— y creo que tu empresa lo puede aplicar.\n\n"
            "Te dejo lo que hacemos, con precios reales y sin relleno:\n\n"
            "👉 " + URL_ESCAPARATE
        ),
    },
    "seguimiento": {
        "idioma": "es",
        "vars": ["nombre"],
        "texto": (
            "Hola {nombre}, soy Miguel Ángel de La Guía de Sevilla 👋\n\n"
            "Hablamos hace unos días y me quedé con ganas de contarte "
            "la idea que tenía para tu negocio.\n\n"
            "¿Te viene bien esta semana o la próxima para que te la cuente "
            "en 10 minutos?"
        ),
    },
}


# ─── Meta Cloud API ───────────────────────────────────────────────────────────
META_API_URL = (
    f"https://graph.facebook.com/v19.0/"
    f"{config.WHATSAPP_PHONE_NUMBER_ID}/messages"
)


def _plantilla():
    """Devuelve la config de la plantilla activa."""
    return PLANTILLAS[PLANTILLA_ACTIVA]


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
    # Si hay nombre de contacto real, usarlo (solo primer nombre)
    contacto = empresa.get("contacto_nombre", "").strip()
    if contacto:
        return contacto.split()[0].capitalize()

    # Si no, usar el nombre completo de la empresa
    nombre_empresa = (empresa.get("nombre") or "").strip()
    if nombre_empresa:
        return nombre_empresa

    return "amigo"


def _sector_para_plantilla(empresa: dict) -> str:
    """Devuelve el valor para {{2}} — sector legible en español."""
    mapeo = {
        "restaurantes":          "restauración",
        "clinicas":              "salud y clínicas",
        "clinicas dentales":     "clínicas dentales",
        "inmobiliarias":         "inmobiliarias",
        "talleres":              "talleres mecánicos",
        "talleres mecanicos":    "talleres mecánicos",
        "academias":             "formación y academias",
        "peluquerias":           "peluquería y estética",
        "farmacias":             "farmacias",
        "fontaneros":            "servicios de fontanería",
        "hoteles":               "alojamiento turístico",
        "airbnb":                "alojamiento turístico",
        "gimnasios":             "fitness y salud",
        "clinicas veterinarias": "clínicas veterinarias",
        "autoescuelas":          "autoescuelas",
        "centros de estetica":   "estética y belleza",
        "general":               "distintos sectores",
    }
    sector = (empresa.get("sector") or "").lower().strip()
    return mapeo.get(sector, sector or "distintos sectores")


def _construir_componentes(valores: dict) -> list:
    """
    Construye los componentes de la plantilla activa.

    Lee "vars" del registro y monta los parámetros en ese orden, así añadir
    una plantilla nueva no obliga a tocar esta función.
    El botón es de URL estática, por lo que no requiere componente extra.
    """
    nombres_vars = _plantilla()["vars"]
    parametros = [
        {"type": "text", "text": valores.get(v, "")}
        for v in nombres_vars
    ]
    return [{"type": "body", "parameters": parametros}]


# ─────────────────────────────────────────────
# ENVÍO INDIVIDUAL
# ─────────────────────────────────────────────

def enviar_whatsapp(empresa_id: int, telefono: str, empresa: dict) -> dict:
    """
    Envía la plantilla activa a través de Meta Cloud API
    y registra la conversación + mensaje saliente en el CRM.

    Returns:
        {"ok": True,  "message_id": "wamid.xxx"}
        {"ok": False, "error": "descripción"}
    """
    numero = normalizar_telefono(telefono)
    if not numero:
        log.warning("empresa_id=%s — teléfono inválido: %s", empresa_id, telefono)
        return {"ok": False, "error": "Teléfono inválido"}

    valores = {
        "nombre": _nombre_para_plantilla(empresa),
        "sector": _sector_para_plantilla(empresa),
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": numero,
        "type": "template",
        "template": {
            "name": PLANTILLA_ACTIVA,
            "language": {"code": _plantilla()["idioma"]},
            "components": _construir_componentes(valores),
        },
    }

    try:
        resp = requests.post(META_API_URL, json=payload, headers=_headers(), timeout=15)
        resp.raise_for_status()
        data = resp.json()

        message_id = data.get("messages", [{}])[0].get("id", "")
        ahora = datetime.now().isoformat()

        actualizar_empresa(empresa_id, {
            "estado":               "enviada",
            "whatsapp_message_id":  message_id,
            "fecha_envio":          ahora,
            "fecha_ultimo_intento": ahora,
            "intentos_contacto":    1,
        })

        log.info(
            "ENVIADO empresa_id=%s | plantilla=%s | numero=%s | nombre=%s | sector=%s | wamid=%s",
            empresa_id, PLANTILLA_ACTIVA, numero,
            valores["nombre"], valores["sector"], message_id,
        )

        # Texto espejo de la plantilla para registrarlo en el CRM
        texto_enviado = _plantilla()["texto"].format(**valores)

        crear_conversacion_crm(
            telefono=numero,
            nombre=f"[PROSPECTOR] {empresa.get('nombre', '')}",
            mensaje_texto=texto_enviado,
            wamid=message_id,
        )

        # Enviar ficha de empresa al CRM para que Nova pueda personalizar
        _enviar_contexto_nova(
            telefono=numero,
            empresa=empresa,
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
    Envía la plantilla activa a una lista de empresas
    respetando todos los controles de seguridad.
    """
    resumen = {"enviados": 0, "fallidos": 0, "omitidos": 0}

    if not _en_horario_comercial():
        hora = datetime.now().strftime("%H:%M")
        msg = f"Fuera de horario comercial ({hora})"
        log.warning(msg)
        return {**resumen, "omitidos": len(empresas), "motivo": msg}

    limite       = _limite_efectivo()
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

        hay_mas = (i < len(empresas) - 1) and (resumen["enviados"] < disponibles)
        if hay_mas:
            espera = random.randint(config.ESPERA_MIN_SEGUNDOS, config.ESPERA_MAX_SEGUNDOS)
            log.info("Esperando %ds...", espera)
            time.sleep(espera)

    log.info("Lote completado: %s", resumen)
    return resumen


# ─────────────────────────────────────────────
# CONTEXTO NOVA → CRM
# ─────────────────────────────────────────────

def _enviar_contexto_nova(telefono: str, empresa: dict) -> None:
    """
    Envía la ficha de empresa al CRM para poblar nova_contexto
    y activar Nova automáticamente en esa conversación.
    """
    import os

    crm_url = os.environ.get("CRM_URL", "").rstrip("/")
    secret  = os.environ.get("PROSPECTOR_SECRET", "")

    if not crm_url or not secret:
        log.warning("[Nova] CRM_URL o PROSPECTOR_SECRET no configurados — contexto no enviado")
        return

    debilidades = []
    dafo_raw = empresa.get("dafo") or empresa.get("debilidades") or ""
    if isinstance(dafo_raw, str) and dafo_raw:
        debilidades = [d.strip() for d in dafo_raw.split(",") if d.strip()]
    elif isinstance(dafo_raw, list):
        debilidades = dafo_raw

    contexto = {
        "nombre_empresa": empresa.get("nombre", ""),
        "sector":         empresa.get("sector", ""),
        "zona":           empresa.get("zona", ""),
        "score":          empresa.get("score", 0),
        "debilidades":    debilidades,
    }

    try:
        resp = requests.post(
            f"{crm_url}/api/whatsapp/nova/contexto/",
            json={
                "telefono": telefono,
                "secret":   secret,
                "contexto": contexto,
            },
            timeout=10,
        )
        if resp.status_code == 200:
            log.info(
                "[Nova] Contexto enviado al CRM — telefono=%s, score=%s",
                telefono, contexto["score"],
            )
        else:
            log.warning(
                "[Nova] CRM rechazó el contexto — status=%s, body=%s",
                resp.status_code, resp.text[:200],
            )
    except requests.RequestException as exc:
        log.warning("[Nova] Error enviando contexto al CRM: %s", exc)