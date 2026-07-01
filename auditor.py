import os
import requests
from dotenv import load_dotenv
from database import obtener_empresas, actualizar_empresa
from zona_detector import detectar_zona

load_dotenv()

PAGESPEED_KEY = os.getenv("PAGESPEED_KEY", "")

def verificar_web(url):
    """Comprueba si la web responde y tiene SSL."""
    if not url:
        return False, False
    try:
        if not url.startswith("http"):
            url = "https://" + url
        response = requests.get(url, timeout=8, allow_redirects=True)
        tiene_web = response.status_code == 200
        tiene_ssl = url.startswith("https")
        return tiene_web, tiene_ssl
    except Exception:
        return False, False

def obtener_velocidad_movil(url):
    """Consulta Google PageSpeed API — completamente gratis."""
    if not url:
        return None
    try:
        if not url.startswith("http"):
            url = "https://" + url
        api_url = f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
        params = {
            "url": url,
            "strategy": "mobile",
        }
        if PAGESPEED_KEY:
            params["key"] = PAGESPEED_KEY
        response = requests.get(api_url, params=params, timeout=15)
        data = response.json()
        score = data.get("lighthouseResult", {}) \
                    .get("categories", {}) \
                    .get("performance", {}) \
                    .get("score", None)
        return int(score * 100) if score is not None else None
    except Exception:
        return None

def auditar_empresa(empresa):
    """Audita una empresa y actualiza su registro en BD."""
    print(f"Auditando: {empresa['nombre']}...")

    tiene_web, tiene_ssl = verificar_web(empresa.get("web"))
    velocidad = obtener_velocidad_movil(empresa.get("web")) if tiene_web else None

    zona = detectar_zona(empresa.get("direccion", ""))
    actualizar_empresa(empresa["id"], {
        "tiene_web":      int(tiene_web),
        "tiene_ssl":      int(tiene_ssl),
        "velocidad_movil": velocidad,
        "zona":            zona,
        "estado":         "auditada",
    })

    print(f"  Web: {tiene_web} | SSL: {tiene_ssl} | Velocidad móvil: {velocidad}")
    return tiene_web, tiene_ssl, velocidad

def auditar_todas():
    """Audita todas las empresas detectadas."""
    empresas = obtener_empresas(estado="detectada")
    print(f"\nEmpresas a auditar: {len(empresas)}")
    for empresa in empresas:
        if empresa.get("web"):
            auditar_empresa(empresa)
        else:
            actualizar_empresa(empresa["id"], {
                "tiene_web": 0,
                "tiene_ssl": 0,
                "estado":    "auditada",
            })

if __name__ == "__main__":
    auditar_todas()