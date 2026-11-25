"""Lectura completa de tabla (área Negocio; usuaria, 25 nov.).

Caso real PA_CuentasOrden_Ajuste_EstadisticoCapitalMensual: el Index Scan de Producto lee 4,658,459 filas y devuelve
4,612,906 (casi todo, por eso no es «lectura residual»), pero el Filter (bitmap) que sigue deja solo 6,875.
"""
import unittest

from app.analizadores.planes_ejecucion.reglas_negocio import analizar_plan_negocio
from app.analizadores.planes_ejecucion.reglas_reporte import analizar_plan_reporte


def _nodo(id_, padre, fisica, reales, leidas=None, objeto=""):
    return {"id": id_, "padre": padre, "fisica": fisica, "logica": fisica, "objeto": objeto, "indice": "",
            "costoPct": 0, "filasReales": reales, "filasLeidas": leidas, "advertencias": [], "predicados": [],
            "duracionMs": None}


def _plan(leidas, devueltas, usadas, intermedio=None):
    nodos = [_nodo("0", None, "Table Insert", 0), _nodo("1", "0", "Hash Match", usadas)]
    padre_del_filtro = "1"
    nodos.append(_nodo("2", padre_del_filtro, "Filter", usadas))
    padre_del_scan = "2"
    if intermedio:
        nodos.append(_nodo("3", "2", intermedio, devueltas))
        padre_del_scan = "3"
    nodos.append(_nodo("9", padre_del_scan, "Index Scan", devueltas, leidas, "[dbo].[Producto]"))
    return [{"numero": 29, "nodos": nodos, "duracionMs": None, "memoria": None}]


def _reglas(hallazgos):
    return [h.regla for h in hallazgos if h.regla in ("LECTURA_COMPLETA_TABLA", "LECTURA_RESIDUAL_ELEVADA")]


class LecturaCompletaDeTabla(unittest.TestCase):
    def test_caso_real_se_marca_con_el_mensaje_de_la_usuaria(self):
        hallazgos = [h for h in analizar_plan_negocio(_plan(4_658_459, 4_612_906, 6_875))
                     if h.regla.startswith("LECTURA_")]
        self.assertEqual([h.regla for h in hallazgos], ["LECTURA_COMPLETA_TABLA"])  # ya no como lectura residual
        self.assertEqual(hallazgos[0].mensaje, (
            "Se observa que se estaría leyendo la totalidad o casi la totalidad de la tabla [dbo].[Producto]. "
            "¿Este comportamiento está validado? De no ser así, se recomienda revisar las condiciones de filtrado, "
            "ya que posteriormente solo se utiliza una cantidad mínima de los registros leídos."))
        self.assertEqual(hallazgos[0].nodos, [{"consulta": 29, "nodo": "9"}])  # solo el Scan de la tabla

    def test_sube_por_parallelism_hasta_el_filter(self):
        self.assertEqual(_reglas(analizar_plan_negocio(_plan(3_000_000, 3_000_000, 50, "Parallelism"))),
                         ["LECTURA_COMPLETA_TABLA"])

    def test_sin_where_tambien_se_marca(self):
        # Leídas = devueltas: antes no salía en ninguna regla.
        self.assertEqual(_reglas(analizar_plan_negocio(_plan(3_000_000, 3_000_000, 1_000))), ["LECTURA_COMPLETA_TABLA"])

    def test_no_se_marca(self):
        casos = {
            "se usa más del 10 %": _plan(4_000_000, 4_000_000, 500_000),
            "menos de un millón de filas": _plan(900_000, 900_000, 10),
            "el Scan ya descarta la mayoría (es lectura residual)": _plan(4_000_000, 1_000_000, 10),
        }
        for nombre, plan in casos.items():
            with self.subTest(nombre):
                self.assertNotIn("LECTURA_COMPLETA_TABLA", _reglas(analizar_plan_negocio(plan)))
        self.assertEqual(_reglas(analizar_plan_negocio(casos["el Scan ya descarta la mayoría (es lectura residual)"])),
                         ["LECTURA_RESIDUAL_ELEVADA"])

    def test_reportes_no_cambia(self):
        self.assertEqual(_reglas(analizar_plan_reporte(_plan(4_658_459, 4_612_906, 6_875))), ["LECTURA_RESIDUAL_ELEVADA"])


if __name__ == "__main__":
    unittest.main()
