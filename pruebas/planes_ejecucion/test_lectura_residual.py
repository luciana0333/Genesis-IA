"""Regla de Reportes: lectura residual elevada (lee más de un millón de filas y devuelve pocas)."""

import unittest

from app.analizadores.planes_ejecucion import analizar_plan_reporte, construir_diagrama


def _scan(nodo: int, tabla: str, leidas: int, devueltas: int, filtro: str = "[T].[cEstado]='ABIERTO'") -> str:
    return f"""
      <RelOp NodeId="{nodo}" PhysicalOp="Clustered Index Scan" LogicalOp="Clustered Index Scan" EstimateRows="10" EstimatedTotalSubtreeCost="0.4">
        <RunTimeInformation><RunTimeCountersPerThread Thread="0" ActualRows="{devueltas}" ActualRowsRead="{leidas}" ActualExecutions="1"/></RunTimeInformation>
        <IndexScan>
          <Object Database="[DB]" Schema="[dbo]" Table="[{tabla}]" Index="[PK_{tabla}]" Alias="[T]"/>
          <Predicate><ScalarOperator ScalarString="{filtro}"/></Predicate>
        </IndexScan>
      </RelOp>"""


def _plan(*operadores: str) -> str:
    hijos = "".join(operadores)
    return f"""
<ShowPlanXML><BatchSequence><Batch><Statements>
<StmtSimple StatementType="SELECT" StatementSubTreeCost="1" StatementText="SELECT 1">
  <QueryPlan>
    <RelOp NodeId="0" PhysicalOp="Nested Loops" LogicalOp="Inner Join" EstimatedTotalSubtreeCost="1" EstimateRows="10">
      <NestedLoops>{hijos}</NestedLoops>
    </RelOp>
  </QueryPlan>
</StmtSimple></Statements></Batch></BatchSequence></ShowPlanXML>
"""


def _residuales(xml: str):
    return [h for h in analizar_plan_reporte(construir_diagrama(xml)) if h.regla == "LECTURA_RESIDUAL_ELEVADA"]


class TestLecturaResidual(unittest.TestCase):
    def test_lee_tres_millones_y_devuelve_300(self):
        hallazgos = _residuales(_plan(_scan(1, "Tickets", 3_000_000, 300)))
        self.assertEqual(len(hallazgos), 1)
        self.assertEqual(hallazgos[0].severidad.value, "alto")
        self.assertEqual(
            hallazgos[0].mensaje,
            "Se ha identificado una lectura residual elevada sobre la tabla [dbo].[Tickets] (Clustered Index Scan, "
            "índice PK_Tickets): "
            "se leen 3,000,000 filas y solo se devuelven 300. Optimizar las condiciones de filtrado "
            "o revisar los índices existentes, ya que la lectura abarca la totalidad o casi la totalidad de los registros.",
        )
        self.assertEqual(hallazgos[0].nodos, [{"consulta": 1, "nodo": "1"}])

    def test_menos_de_un_millon_no_se_marca(self):
        self.assertEqual(_residuales(_plan(_scan(1, "Tickets", 900_000, 10))), [])

    def test_sin_filas_descartadas_no_se_marca(self):
        self.assertEqual(_residuales(_plan(_scan(1, "Tickets", 2_000_000, 2_000_000))), [])

    def test_varios_operadores_se_agrupan(self):
        hallazgos = _residuales(_plan(_scan(1, "Tickets", 3_000_000, 300), _scan(2, "Pagos", 1_500_000, 20)))
        self.assertEqual(len(hallazgos), 1)
        self.assertTrue(hallazgos[0].mensaje.startswith("Se identificaron 2 lecturas residuales elevadas, en la consulta 1: "))
        self.assertIn("; La tabla [dbo].[Pagos] (Clustered Index Scan, índice PK_Pagos): se leen 1,500,000 filas", hallazgos[0].mensaje)
        self.assertTrue(hallazgos[0].mensaje.endswith(
            "Optimizar las condiciones de filtrado o revisar los índices existentes, ya que estas "
            "lecturas abarcan, en algunos casos, la totalidad de los registros."))

    def test_un_seek_no_se_marca_aunque_pase_el_millon(self):
        seek = _scan(1, "Tickets", 3_000_000, 300).replace("Clustered Index Scan", "Clustered Index Seek")
        self.assertEqual(_residuales(_plan(seek)), [])

    def test_table_scan_e_index_scan_si_se_marcan(self):
        for operador in ("Table Scan", "Index Scan"):
            with self.subTest(operador=operador):
                scan = _scan(1, "Tickets", 3_000_000, 300).replace("Clustered Index Scan", operador)
                self.assertEqual(len(_residuales(_plan(scan))), 1)


if __name__ == "__main__":
    unittest.main()
