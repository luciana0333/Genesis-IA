"""Riesgo identificado por Genesis: conversión de una columna (BIT, número, fecha) dentro de un filtro (usuaria, 18 nov.).

Comprobado en SQL Server Express: bEnfermedadTerminal (BIT) convertida a int en el resultado no afecta; en el filtro obliga
a recorrer la tabla y SQL Server no lo alerta. Solo se marca cuando cuesta (lee muchas filas y devuelve pocas), para no
llenar el informe: en los 13 planes reales de la usuaria no sale ninguna vez.

Los planes de recursos/conversion_bit_*.sqlplan son reales (SQL Server Express, 30 000 filas):
  1) WHERE B.bEnfermedadTerminal + 0 = @nEnf          → lee 30 000 y devuelve 2: se marca.
  2) la misma conversión solo en el SELECT              → no se marca.
  3) conversión en el filtro de una tabla de 50 filas   → no se marca.
"""

import unittest
from pathlib import Path

from app.analizadores.planes_ejecucion.riesgos_genesis import conversion_columna_en_filtro
from app.analizadores.planes_ejecucion.servicio import analizar_plan_completo

RECURSOS = Path(__file__).parent / "recursos"


def _observaciones(numero: int, area: str):
    contenido = (RECURSOS / f"conversion_bit_{numero}.sqlplan").read_bytes()
    resultado = analizar_plan_completo(f"conversion_bit_{numero}.sqlplan", contenido, area, None)
    return [h for h in resultado["hallazgos"] if h["regla"] == "CONVERSION_COLUMNA_EN_FILTRO"]


def _sentencia(nodos):
    return [{"numero": 1, "nodos": nodos}]


def _scan(leidas, devueltas, nodo_id="1", tabla="dbo.Cts"):
    return {"id": nodo_id, "fisica": "Clustered Index Scan", "objeto": tabla, "filasLeidas": leidas,
            "filasReales": devueltas, "advertencias": [], "predicados": []}


class ConversionEnFiltroTest(unittest.TestCase):
    def test_planes_reales_en_los_dos_modulos(self):
        for area in ("negocio", "reporte"):
            with self.subTest(area=area):
                hallazgos = _observaciones(1, area)
                self.assertEqual(len(hallazgos), 1)
                self.assertEqual(hallazgos[0]["severidad"], "bajo")
                self.assertEqual(
                    hallazgos[0]["mensaje"],
                    "Se identificó una conversión implícita en un filtro de la columna bEnfermedadTerminal de "
                    "DisponibilidadRetiroCuentaCTS a int, que obliga a leer 30,000 filas para devolver 2. Se recomienda "
                    "corregir la conversión implícita identificada, comparando la columna con un valor del mismo tipo "
                    "de dato y validando que el cambio no altere el resultado esperado.",
                )
                self.assertEqual(_observaciones(2, area), [])  # solo en el resultado
                self.assertEqual(_observaciones(3, area), [])  # tabla pequeña

    def test_compute_scalar_usado_en_un_filtro(self):
        # [Expr1003] se calcula en un Compute Scalar y un Filter lo usa: la conversión está en el filtro.
        definida = ("[Expr1003] = Scalar Operator(CONVERT_IMPLICIT(int,[DBCMACICA].[dbo].[Cts].[bEnfermedadTerminal] "
                    "as [B].[bEnfermedadTerminal],0))")
        nodos = [
            {"id": "0", "fisica": "Filter", "objeto": "", "advertencias": [],
             "predicados": [{"nombre": "Predicate", "texto": "[Expr1003]=[@nEnf]"}]},
            {"id": "1", "fisica": "Compute Scalar", "objeto": "", "advertencias": [],
             "predicados": [{"nombre": "Defined Values", "texto": definida}]},
            _scan(29592, 2, "2"),
        ]
        hallazgos = conversion_columna_en_filtro(_sentencia(nodos))
        self.assertEqual(len(hallazgos), 1)
        self.assertIn("bEnfermedadTerminal de Cts a int, que obliga a leer 29,592 filas para devolver 2",
                      hallazgos[0].mensaje)
        self.assertEqual(hallazgos[0].nodos, [{"consulta": 1, "nodo": "0"}, {"consulta": 1, "nodo": "2"}])

    def test_compute_scalar_solo_en_el_resultado_no_se_marca(self):
        # Caso de la captura: [Expr1003] solo va en la lista de salida; nadie filtra con él.
        definida = ("[Expr1003] = Scalar Operator(CONVERT_IMPLICIT(int,[DBCMACICA].[dbo].[Cts].[bEnfermedadTerminal] "
                    "as [B].[bEnfermedadTerminal],0))")
        nodos = [
            {"id": "0", "fisica": "Compute Scalar", "objeto": "", "advertencias": [],
             "predicados": [{"nombre": "Defined Values", "texto": definida},
                            {"nombre": "Output List", "texto": "[cCtaCod], [Expr1003]"}]},
            _scan(29592, 2),
        ]
        self.assertEqual(conversion_columna_en_filtro(_sentencia(nodos)), [])

    def test_limites_para_no_llenar_el_informe(self):
        filtro = {"id": "1", "fisica": "Clustered Index Scan", "objeto": "dbo.Cts", "advertencias": [],
                  "predicados": [{"nombre": "Predicate",
                                  "texto": "CONVERT_IMPLICIT(int,[dbo].[Cts].[bActivo],0)=[@n]"}]}
        casos = {
            "lee pocas filas": (9_999, 2, False),
            "devuelve más del 10 %": (50_000, 6_000, False),
            "lee mucho y devuelve poco": (50_000, 4_000, True),
        }
        for nombre, (leidas, devueltas, marca) in casos.items():
            with self.subTest(nombre):
                nodo = {**filtro, "filasLeidas": leidas, "filasReales": devueltas}
                self.assertEqual(bool(conversion_columna_en_filtro(_sentencia([nodo]))), marca)

    def test_columnas_de_texto_y_alertadas_no_se_repiten(self):
        # Texto (cFecha): lo ve «columna de texto convertida». Alertada por SQL Server: «Conversión implícita detectada».
        texto = {"id": "1", "fisica": "Table Scan", "objeto": "dbo.Cts", "filasLeidas": 50_000, "filasReales": 1,
                 "advertencias": [], "predicados": [{"nombre": "Predicate",
                                                     "texto": "CONVERT_IMPLICIT(datetime,[dbo].[Cts].[cFecha],0)>[@d]"}]}
        alertada = {**texto, "advertencias": [{"tipo": "conversion",
                                               "texto": "CONVERT_IMPLICIT(int,[dbo].[Cts].[bActivo],0)"}],
                    "predicados": [{"nombre": "Predicate", "texto": "CONVERT_IMPLICIT(int,[dbo].[Cts].[bActivo],0)=1"}]}
        self.assertEqual(conversion_columna_en_filtro(_sentencia([texto])), [])
        self.assertEqual(conversion_columna_en_filtro(_sentencia([alertada])), [])


if __name__ == "__main__":
    unittest.main()
