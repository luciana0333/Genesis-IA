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
        self.assertIn(
            "Se ha identificado una lectura residual elevada en el operador Clustered Index Scan (nodo 1) sobre "
            "[dbo].[Tickets]: lee 3,000,000 filas y solo devuelve 300 a la consulta, "
            "por lo que se recomienda revisar el filtro del operador (Predicate)",
            hallazgos[0].mensaje,
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
        self.assertIn("; Operador Clustered Index Scan (nodo 2) sobre [dbo].[Pagos]: lee 1,500,000 filas", hallazgos[0].mensaje)


if __name__ == "__main__":
    unittest.main()
