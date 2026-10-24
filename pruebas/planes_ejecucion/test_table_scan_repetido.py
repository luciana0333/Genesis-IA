"""Negocio: Table Scan de la misma tabla en varias consultas → una observación y una imagen."""

import unittest

from app.analizadores.planes_ejecucion import analizar_plan_negocio, construir_diagrama


def _consulta(scans: str) -> str:
    return f"""
<StmtSimple StatementType="SELECT" StatementSubTreeCost="1" StatementText="SELECT 1">
  <QueryPlan>
    <RelOp NodeId="0" PhysicalOp="Nested Loops" LogicalOp="Inner Join" EstimatedTotalSubtreeCost="1" EstimateRows="1">
      <NestedLoops>{scans}</NestedLoops>
    </RelOp>
  </QueryPlan>
</StmtSimple>"""


def _scan(nodo: int, tabla: str, devueltas: int, leidas: int = 86, costo: float = 0.3) -> str:
    return (f'<RelOp NodeId="{nodo}" PhysicalOp="Table Scan" LogicalOp="Table Scan" EstimatedTotalSubtreeCost="{costo}" EstimateRows="1">'
            f'<RunTimeInformation><RunTimeCountersPerThread Thread="0" ActualRows="{devueltas}" ActualRowsRead="{leidas}" ActualExecutions="1"/></RunTimeInformation>'
            f'<TableScan><Object Schema="[dbo]" Table="[{tabla}]"/></TableScan></RelOp>')


def _table_scan(*consultas: str):
    xml = f"<ShowPlanXML><BatchSequence><Batch><Statements>{''.join(consultas)}</Statements></Batch></BatchSequence></ShowPlanXML>"
    return [h for h in analizar_plan_negocio(construir_diagrama(xml)) if h.regla == "TABLE_SCAN_DETECTADO"]


class TestTableScanRepetido(unittest.TestCase):
    def test_caso_de_la_usuaria_agencias_en_dos_consultas(self):
        # Consulta 1: 86 leídas → 1 (30.1 %); consulta 2: 86 → 13 (38.6 %, la más costosa).
        hallazgos = _table_scan(_consulta(_scan(1, "Agencias", 1, costo=0.301)),
                                _consulta(_scan(1, "Agencias", 13, costo=0.386)))
        self.assertEqual(len(hallazgos), 1)
        self.assertEqual(
            hallazgos[0].mensaje,
            "Se ha identificado un Table Scan dentro del procedimiento sobre la tabla [dbo].[Agencias], que se "
            "repite en 2 consultas (1 y 2): se leen 86 filas en cada una y se devuelven 1 (consulta 1) y 13 "
            "(consulta 2). Evaluar agregar la PK CLUSTERED en la tabla, ya que forma parte de las buenas "
            "prácticas y ayuda a agilizar la búsqueda.",
        )
        # Una sola imagen: la del recorrido más costoso.
        self.assertEqual(hallazgos[0].nodos, [{"consulta": 2, "nodo": "1"}])

    def test_filas_distintas_por_consulta(self):
        hallazgo = _table_scan(_consulta(_scan(1, "Agencias", 1)), _consulta(_scan(1, "Agencias", 13, leidas=500)))[0]
        self.assertIn("que se repite en 2 consultas (1 y 2): en la consulta 1 se leen 86 filas y se devuelven 1 y "
                      "en la consulta 2 se leen 500 filas y se devuelven 13.", hallazgo.mensaje)

    def test_otra_tabla_va_aparte_con_su_imagen(self):
        hallazgo = _table_scan(_consulta(_scan(1, "Agencias", 1)), _consulta(_scan(1, "Agencias", 13)),
                               _consulta(_scan(1, "Monedas", 2)))[0]
        self.assertTrue(hallazgo.mensaje.startswith(
            "Se identificaron 3 Table Scan dentro del procedimiento, en las consultas 1, 2, 3: La tabla "
            "[dbo].[Agencias], que se repite en 2 consultas (1 y 2): se leen 86 filas en cada una y se devuelven "
            "1 (consulta 1) y 13 (consulta 2); La tabla [dbo].[Monedas] (consulta 3): se leen 86 filas y se "
            "devuelven 2."))
        self.assertEqual(len(hallazgo.nodos), 2)


if __name__ == "__main__":
    unittest.main()
