"""Cada observación del Validador tiene su título en la pantalla (usuaria, 18 nov.: salió «VARCHAR_SIN_TAMANO_FECHA»
con guiones bajos). Si se agrega una regla y no su título en frontend/src/config/reglas.js, esta prueba falla."""

import re
import unittest
from pathlib import Path

from app.analizadores.scriptdom_mensajes import MENSAJES

REGLAS_JS = Path(__file__).resolve().parents[2] / "frontend" / "src" / "config" / "reglas.js"


class TitulosTest(unittest.TestCase):
    def test_todas_las_reglas_del_validador_tienen_titulo(self):
        titulos = set(re.findall(r"^\s*([A-Z][A-Z0-9_]+):\s*'", REGLAS_JS.read_text(encoding="utf-8"), re.MULTILINE))
        faltan = sorted((set(MENSAJES) | {"ERROR_SINTAXIS"}) - titulos)
        self.assertEqual(faltan, [], f"Reglas sin título en reglas.js: {faltan}")


if __name__ == "__main__":
    unittest.main()
