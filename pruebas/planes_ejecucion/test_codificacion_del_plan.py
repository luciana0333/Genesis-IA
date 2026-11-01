"""Planes guardados en otra codificación de la que declaran (caso de la usuaria, 1 nov.).

SSMS guarda el .sqlplan en UTF-16 y lo declara (encoding="utf-16"). Si se vuelve a guardar con otro editor
queda en UTF-8 con la misma declaración, y antes Genesis respondía «El archivo no contiene un plan XML
válido de SQL Server».
"""

import unittest
from pathlib import Path

from app.analizadores.planes_ejecucion.lote import nombre_procedimiento
from app.analizadores.planes_ejecucion.servicio import analizar_plan_completo, texto_del_plan

_CUERPO = Path(__file__).parent.joinpath("recursos", "plan-funcion-de-tabla.sqlplan").read_text(encoding="utf-8")
_UTF16 = '<?xml version="1.0" encoding="utf-16"?>\n'
_UTF8 = '<?xml version="1.0" encoding="utf-8"?>\n'


class CodificacionTest(unittest.TestCase):
    def _consultas(self, contenido: bytes) -> int:
        return len(analizar_plan_completo("dbo.PA_Prueba_Sel_Datos.sqlplan", contenido, "negocio")["diagrama"])

    def test_todas_las_formas_se_leen_igual(self):
        esperado = self._consultas((_UTF16 + _CUERPO).encode("utf-16"))  # como lo guarda SSMS
        self.assertGreater(esperado, 0)
        formas = {
            "UTF-8 que declara UTF-16 (caso de la usuaria)": (_UTF16 + _CUERPO).encode("utf-8"),
            "UTF-8 con marca (BOM)": (_UTF8 + _CUERPO).encode("utf-8-sig"),
            "UTF-8 sin declaración": _CUERPO.encode("utf-8"),
            "UTF-16 sin marca": (_UTF16 + _CUERPO).encode("utf-16-le"),
            "UTF-16 big endian sin marca": (_UTF16 + _CUERPO).encode("utf-16-be"),
        }
        for nombre, contenido in formas.items():
            with self.subTest(forma=nombre):
                self.assertEqual(self._consultas(contenido), esperado)

    def test_texto_del_plan_no_cambia_un_texto(self):
        self.assertIs(texto_del_plan(_CUERPO), _CUERPO)

    def test_lote_lee_el_nombre_aunque_la_declaracion_no_coincida(self):
        contenido = (_UTF16 + _CUERPO).encode("utf-8")
        self.assertTrue(nombre_procedimiento(contenido, "plan.sqlplan"))

    def test_un_archivo_que_no_es_plan_sigue_dando_error(self):
        import xml.etree.ElementTree as ET
        with self.assertRaises(ET.ParseError):
            analizar_plan_completo("x.sqlplan", "esto no es un plan".encode("utf-8"), "negocio")


if __name__ == "__main__":
    unittest.main()
