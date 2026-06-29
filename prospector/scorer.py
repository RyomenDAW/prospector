import json
from database import obtener_empresas, actualizar_empresa

def calcular_score(empresa):
    """
    Cuanto más alto el score, más nos necesita la empresa.
    Máximo 100 puntos.
    """
    score = 0
    debilidades = []

    # Sin web — oportunidad máxima
    if not empresa.get("tiene_web"):
        score += 30
        debilidades.append("Sin página web")

    # Sin SSL
    if empresa.get("tiene_web") and not empresa.get("tiene_ssl"):
        score += 15
        debilidades.append("Web sin SSL (no segura)")

    # Web lenta en móvil
    velocidad = empresa.get("velocidad_movil")
    if velocidad is not None:
        if velocidad < 50:
            score += 20
            debilidades.append(f"Web muy lenta en móvil ({velocidad}/100)")
        elif velocidad < 70:
            score += 10
            debilidades.append(f"Web lenta en móvil ({velocidad}/100)")

    # Pocas o ninguna reseña
    resenas = empresa.get("num_resenas") or 0
    if resenas == 0:
        score += 20
        debilidades.append("Sin reseñas en Google")
    elif resenas < 10:
        score += 10
        debilidades.append(f"Muy pocas reseñas ({resenas})")

    # Valoración baja
    valoracion = empresa.get("valoracion") or 0
    if 0 < valoracion < 3.5:
        score += 15
        debilidades.append(f"Valoración baja ({valoracion}★)")

    # Sin teléfono
    if not empresa.get("telefono"):
        score += 10
        debilidades.append("Sin teléfono visible en Google")

    return min(score, 100), debilidades

def puntuar_todas():
    empresas = obtener_empresas(estado="auditada")
    print(f"\nEmpresas a puntuar: {len(empresas)}")

    for empresa in empresas:
        score, debilidades = calcular_score(empresa)
        actualizar_empresa(empresa["id"], {
            "score":      score,
            "debilidades": json.dumps(debilidades, ensure_ascii=False),
            "estado":     "cualificada",
        })
        print(f"  {empresa['nombre'][:40]} → Score: {score} | {', '.join(debilidades[:2])}")

    print("\nPuntuación completada.")

if __name__ == "__main__":
    puntuar_todas()