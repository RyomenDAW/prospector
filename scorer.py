import json
from database import obtener_empresas, actualizar_empresa

# Umbral de reseñas por sector — cuántas necesita un negocio para considerarse "bien posicionado"
UMBRAL_RESENAS = {
    "academias":       50,
    "clinicas dentales": 50,
    "clinicas":        50,
    "inmobiliarias":   30,
    "restaurantes":    100,
    "farmacias":       30,
    "peluquerias":     30,
    "talleres mecanicos": 20,
    "talleres":        20,
    "fontaneros":      20,
    "hoteles":         100,
    "airbnb":          30,
    "gimnasios":       50,
}
UMBRAL_RESENAS_DEFAULT = 25


def _umbral_resenas(sector: str) -> int:
    return UMBRAL_RESENAS.get((sector or "").lower().strip(), UMBRAL_RESENAS_DEFAULT)


def calcular_score(empresa):
    """
    Cuanto más alto el score, más nos necesita la empresa.
    Máximo 100 puntos.
    """
    score = 0
    debilidades = []

    sector = (empresa.get("sector") or "").lower().strip()
    resenas = empresa.get("num_resenas") or 0
    valoracion = empresa.get("valoracion") or 0
    velocidad = empresa.get("velocidad_movil")
    tiene_web = empresa.get("tiene_web")
    tiene_ssl = empresa.get("tiene_ssl")

    # ── 1. Presencia web ──────────────────────────────────────────────────────

    if not tiene_web:
        score += 30
        debilidades.append("Sin página web")
    else:
        if not tiene_ssl:
            score += 15
            debilidades.append("Web sin SSL (no segura)")

        if velocidad is not None:
            if velocidad < 50:
                score += 20
                debilidades.append(f"Web muy lenta en móvil ({velocidad}/100)")
            elif velocidad < 70:
                score += 10
                debilidades.append(f"Web lenta en móvil ({velocidad}/100)")

    # ── 2. Reseñas en Google ──────────────────────────────────────────────────

    umbral = _umbral_resenas(sector)

    if resenas == 0:
        score += 25
        debilidades.append("Sin reseñas en Google")
    elif resenas < 10:
        score += 20
        debilidades.append(f"Muy pocas reseñas ({resenas})")
    elif resenas < umbral // 2:
        score += 15
        debilidades.append(f"Pocas reseñas para el sector ({resenas} reseñas)")
    elif resenas < umbral:
        score += 10
        debilidades.append(f"Reseñas por debajo de la media del sector ({resenas} reseñas)")

    # ── 3. Valoración ─────────────────────────────────────────────────────────

    if 0 < valoracion < 3.5:
        score += 20
        debilidades.append(f"Valoración baja ({valoracion}★)")
    elif 3.5 <= valoracion < 4.0:
        score += 10
        debilidades.append(f"Valoración mejorable ({valoracion}★)")

    # ── 4. Perfil Google Maps incompleto ──────────────────────────────────────
    # Si tiene web pero pocas reseñas → GMB descuidado

    if tiene_web and resenas < 30:
        # Solo añadir si no hay ya una debilidad de reseñas más específica
        ya_tiene_debilidad_resenas = any(
            "reseña" in d.lower() for d in debilidades
        )
        if not ya_tiene_debilidad_resenas:
            score += 10
            debilidades.append(f"Perfil de Google Maps mejorable ({resenas} reseñas)")

    return min(score, 100), debilidades


def puntuar_todas():
    empresas = obtener_empresas(estado="auditada")
    print(f"\nEmpresas a puntuar: {len(empresas)}")

    for empresa in empresas:
        score, debilidades = calcular_score(empresa)
        actualizar_empresa(empresa["id"], {
            "score":       score,
            "debilidades": json.dumps(debilidades, ensure_ascii=False),
            "estado":      "cualificada" if empresa.get("telefono") else "rechazada",
        })
        print(f"  {empresa['nombre'][:40]} → Score: {score} | {', '.join(debilidades[:2])}")

    print("\nPuntuación completada.")


if __name__ == "__main__":
    puntuar_todas()