"""
test_prospector.py — Tests de las funciones críticas

Solo testeo lo que, si falla, causa DAÑO REAL:
  - Normalización de teléfonos → si falla, envías al número equivocado
  - Detección de opt-out → si falla, escribes a quien dijo "no" = spam
  - Similitud de nombres → si falla, contactas duplicados = spam
  - Horario de envío → si falla, envías a las 3AM = baneo

No testeo todo por testear. Testeo lo que protege de un desastre.

Ejecutar:
    python -m pytest test_prospector.py -v

O sin pytest:
    python test_prospector.py
"""

import unittest
from datetime import datetime
from unittest.mock import patch


# ─────────────────────────────────────────────
# TESTS — Normalización de teléfonos
# ─────────────────────────────────────────────

class TestNormalizarTelefono(unittest.TestCase):

    def setUp(self):
        from phone_validator import normalizar_telefono
        self.normalizar = normalizar_telefono

    def test_movil_sin_prefijo(self):
        self.assertEqual(self.normalizar("650318597"), "34650318597")

    def test_movil_con_espacios(self):
        self.assertEqual(self.normalizar("650 318 597"), "34650318597")

    def test_movil_con_prefijo(self):
        self.assertEqual(self.normalizar("34650318597"), "34650318597")

    def test_movil_con_plus(self):
        self.assertEqual(self.normalizar("+34650318597"), "34650318597")

    def test_movil_con_codigo_internacional(self):
        self.assertEqual(self.normalizar("0034650318597"), "34650318597")

    def test_fijo_sevilla(self):
        self.assertEqual(self.normalizar("954123456"), "34954123456")

    def test_vacio(self):
        self.assertIsNone(self.normalizar(""))

    def test_none(self):
        self.assertIsNone(self.normalizar(None))


# ─────────────────────────────────────────────
# TESTS — Detección de móvil vs fijo
# ─────────────────────────────────────────────

class TestEsMovil(unittest.TestCase):

    def setUp(self):
        from phone_validator import es_movil
        self.es_movil = es_movil

    def test_movil_6(self):
        self.assertTrue(self.es_movil("34650318597"))

    def test_movil_7(self):
        self.assertTrue(self.es_movil("34750318597"))

    def test_fijo_9(self):
        self.assertFalse(self.es_movil("34954123456"))

    def test_formato_invalido(self):
        self.assertFalse(self.es_movil("123"))


# ─────────────────────────────────────────────
# TESTS — Detección de opt-out
# ─────────────────────────────────────────────

class TestOptOut(unittest.TestCase):

    def setUp(self):
        from blacklist import es_opt_out
        self.es_opt_out = es_opt_out

    def test_no_solo(self):
        self.assertTrue(self.es_opt_out("no"))

    def test_no_me_interesa(self):
        self.assertTrue(self.es_opt_out("No me interesa, gracias"))

    def test_stop(self):
        self.assertTrue(self.es_opt_out("STOP"))

    def test_quita_numero(self):
        self.assertTrue(self.es_opt_out("Quita mi número de tu lista"))

    def test_spam(self):
        self.assertTrue(self.es_opt_out("esto es spam"))

    def test_respuesta_positiva(self):
        self.assertFalse(self.es_opt_out("Hola, sí me interesa, cuéntame más"))

    def test_pregunta(self):
        self.assertFalse(self.es_opt_out("¿Cuánto cuesta?"))

    def test_vacio(self):
        self.assertFalse(self.es_opt_out(""))


# ─────────────────────────────────────────────
# TESTS — Similitud de nombres (duplicados)
# ─────────────────────────────────────────────

class TestSimilitud(unittest.TestCase):

    def setUp(self):
        from dedup import similitud, normalizar_nombre
        self.similitud = similitud
        self.normalizar = normalizar_nombre

    def test_identicos(self):
        self.assertGreaterEqual(self.similitud("Bar Pepe", "Bar Pepe"), 0.99)

    def test_con_sufijo_legal(self):
        # "Bar Pepe" y "Bar Pepe S.L." deben ser muy similares
        self.assertGreaterEqual(self.similitud("Bar Pepe", "Bar Pepe S.L."), 0.87)

    def test_mayusculas(self):
        self.assertGreaterEqual(self.similitud("BAR PEPE", "bar pepe"), 0.99)

    def test_con_tildes(self):
        self.assertGreaterEqual(self.similitud("José García", "Jose Garcia"), 0.95)

    def test_distintos(self):
        self.assertLess(self.similitud("Bar Pepe", "Clínica Dental Sur"), 0.5)

    def test_normalizar_quita_sufijo(self):
        self.assertEqual(self.normalizar("Bar Pepe S.L."), "bar pepe")


# ─────────────────────────────────────────────
# TESTS — Horario de envío
# ─────────────────────────────────────────────

class TestHorario(unittest.TestCase):

    def test_lunes_mediodia_si(self):
        from sender_evolution import en_horario_comercial
        # Lunes 12:00 → debe poder enviar
        lunes_mediodia = datetime(2026, 6, 15, 12, 0)  # 15 junio 2026 es lunes
        with patch("sender_evolution.datetime") as mock_dt:
            mock_dt.now.return_value = lunes_mediodia
            self.assertTrue(en_horario_comercial())

    def test_domingo_no(self):
        from sender_evolution import en_horario_comercial
        # Domingo → nunca enviar
        domingo = datetime(2026, 6, 14, 12, 0)  # 14 junio 2026 es domingo
        with patch("sender_evolution.datetime") as mock_dt:
            mock_dt.now.return_value = domingo
            self.assertFalse(en_horario_comercial())

    def test_madrugada_no(self):
        from sender_evolution import en_horario_comercial
        # Lunes 3AM → no enviar
        madrugada = datetime(2026, 6, 15, 3, 0)
        with patch("sender_evolution.datetime") as mock_dt:
            mock_dt.now.return_value = madrugada
            self.assertFalse(en_horario_comercial())


if __name__ == "__main__":
    unittest.main(verbosity=2)