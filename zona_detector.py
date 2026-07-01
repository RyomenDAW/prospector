import unicodedata

CP_SEVILLA_CAPITAL = {
    "41001", "41002", "41003", "41004", "41005",
    "41006", "41007", "41008", "41009", "41010",
    "41011", "41012", "41013", "41014", "41015",
    "41016", "41017", "41018", "41019", "41020",
}

ZONAS = {
    "medio": [
        "dos hermanas", "alcala de guadaira", "mairena del aljarafe",
        "san juan de aznalfarache", "gelves", "coria del rio",
        "la rinconada", "mairena del alcor", "bormujos", "tomares",
        "gines", "espartinas", "umbrete", "castilleja", "valencina",
        "salteras", "bollullos", "almensilla", "palomares",
    ],
    "lejos": [
        "utrera", "carmona", "ecija", "marchena", "osuna",
        "moron", "estepa", "cazalla", "constantina", "lora del rio",
        "lebrija", "los palacios", "villamanrique", "aznalcazar",
    ],
}

def normalizar(texto):
    """Elimina tildes y convierte a minúsculas."""
    return ''.join(
        c for c in unicodedata.normalize('NFD', texto.lower())
        if unicodedata.category(c) != 'Mn'
    )

def detectar_zona(direccion):
    if not direccion:
        return "desconocida"

    direccion_norm = normalizar(direccion)

    # Primero CP — más fiable
    for cp in CP_SEVILLA_CAPITAL:
        if cp in direccion:
            return "cerca"

    # Municipios normalizados
    for zona, palabras in ZONAS.items():
        for palabra in palabras:
            if palabra in direccion_norm:
                return zona

    if "sevilla" in direccion_norm:
        return "medio"

    return "desconocida"