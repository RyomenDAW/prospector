import json

def generar_dafo(empresa):
    """Genera checklist de debilidades de la empresa."""
    checklist = []

    if not empresa.get("tiene_web"):
        checklist.append({"item": "Sin página web", "gravedad": "critica"})
    elif not empresa.get("tiene_ssl"):
        checklist.append({"item": "Web sin SSL (aparece como 'No seguro')", "gravedad": "alta"})

    velocidad = empresa.get("velocidad_movil")
    if velocidad is not None:
        if velocidad < 50:
            checklist.append({"item": f"Web muy lenta en móvil ({velocidad}/100)", "gravedad": "alta"})
        elif velocidad < 70:
            checklist.append({"item": f"Web lenta en móvil ({velocidad}/100)", "gravedad": "media"})

    resenas = empresa.get("num_resenas") or 0
    valoracion = empresa.get("valoracion") or 0
    if resenas == 0:
        checklist.append({"item": "Sin reseñas en Google", "gravedad": "alta"})
    elif resenas < 10:
        checklist.append({"item": f"Muy pocas reseñas ({resenas})", "gravedad": "media"})

    if 0 < valoracion < 3.5:
        checklist.append({"item": f"Valoración baja ({valoracion}★)", "gravedad": "alta"})

    if not empresa.get("telefono"):
        checklist.append({"item": "Sin teléfono visible en Google", "gravedad": "media"})

    if not checklist:
        checklist.append({"item": "Sin debilidades críticas detectadas", "gravedad": "ok"})

    return checklist

def actualizar_dafo_todas():
    from database import obtener_empresas, actualizar_empresa
    import json
    empresas = obtener_empresas()
    for e in empresas:
        dafo = generar_dafo(e)
        actualizar_empresa(e["id"], {"dafo": json.dumps(dafo, ensure_ascii=False)})
    print(f"DAFO generado para {len(empresas)} empresas.")

if __name__ == "__main__":
    actualizar_dafo_todas()