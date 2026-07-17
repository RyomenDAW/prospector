import os
import json
import anthropic
from dotenv import load_dotenv
from database import obtener_empresas, actualizar_empresa

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = """
Actúa como un experto en ventas B2B y Programación Neurolingüística (PNL). Eres el alter ego digital de Miguel Ángel Soto, Director Comercial de "La Guía de Sevilla" (Agencia de Marketing Digital). Tu objetivo es abrir conversaciones por WhatsApp con dueños de negocios en Sevilla y provincia, no vender directamente.

Psicología y Tono:
- Tono cercano, franco, de empresario a empresario. Cero lenguaje corporativo.
- Tutea siempre con respeto, buscando la conexión local andaluza pero manteniendo estatus de Alta Dirección.
- Transmite autoridad tranquila: eres un sherpa digital que guía hacia la rentabilidad, no un vendedor desesperado.

Estructura del Mensaje (Máximo 5 líneas):
1. Patrón de Interrupción (Línea 1): Saludo directo por su nombre y mención inmediata de su negocio.
2. Dedo en la Llaga (Líneas 2-3): UN SOLO problema digital concreto detectado. Usa PNL para asociarlo a pérdida de dinero o clientes que se van a la competencia. Sé quirúrgico, no genérico.
3. Puente de Valor (Línea 4): Posiciónate como solución sin vender nada aún.
4. Pregunta de Doble Vínculo (Línea 5): Cierra con pregunta corta casi imposible de no responder. Evita Sí/No cerradas. Busca el micro-compromiso.

Reglas Inquebrantables:
- NUNCA uses más de 1 emoji.
- NUNCA pidas una reunión en el primer mensaje.
- NUNCA suenes a bot o mensaje masivo.
- Firma SIEMPRE exactamente así al final: "Miguel Ángel Soto - La Guía de Sevilla"
"""

DEBILIDADES_UNIVERSALES = [
    "Sin estrategia de captación activa de reseñas",
    "Presencia en redes sociales sin estrategia de contenidos",
    "Sin sistema de fidelización de clientes recurrentes",
    "Visibilidad en Google Maps sin optimizar al detalle",
]


def generar_mensaje(empresa):
    debilidades = json.loads(empresa.get("debilidades") or "[]")
    


    # Si no tiene debilidades detectadas, usar universales
    if not debilidades:
        debilidades = DEBILIDADES_UNIVERSALES

        if empresa.get("tiene_web"):
            debilidades = [d for d in debilidades if "sin web" not in d.lower()]
    
        if not debilidades:
            debilidades = DEBILIDADES_UNIVERSALES

    user_prompt = f"""
Genera un mensaje de WhatsApp para:
- Nombre del negocio: {empresa['nombre']}
- Sector: {empresa['sector']}
- Ubicación: {empresa['direccion']}
- Principales problemas detectados: {', '.join(debilidades[:2])}

El mensaje debe:
- Ser informal pero profesional
- Mencionar solo el problema más relevante
- Terminar con una pregunta que invite a responder
- Máximo 5 líneas
- No mencionar que somos una agencia al principio, primero genera curiosidad
"""

    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=300,
        messages=[{"role": "user", "content": user_prompt}],
        system=SYSTEM_PROMPT,
    )

    return response.content[0].text.strip()

def generar_mensajes_todos(min_score=20):
    """Solo genera mensajes para empresas con score mínimo."""
    empresas = obtener_empresas(estado="cualificada")
    empresas_filtradas = [e for e in empresas if e.get("score", 0) >= min_score]
    
    print(f"\nEmpresas con score >= {min_score}: {len(empresas_filtradas)}")

    for empresa in empresas_filtradas:
        try:
            mensaje = generar_mensaje(empresa)
            if mensaje:
                actualizar_empresa(empresa["id"], {
                    "mensaje_generado": mensaje,
                    "estado": "lista",
                })
                print(f"  ✓ {empresa['nombre'][:20]}")
            else:
                print(f"  ✗ {empresa['nombre'][:20]} — sin debilidades")
        except Exception as e:
            print(f"  ✗ Error en {empresa['nombre']}: {e}")

    print("\nMensajes generados.")

if __name__ == "__main__":
    generar_mensajes_todos(min_score=20)