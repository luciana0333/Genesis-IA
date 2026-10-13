"""Regla de Reportes: el procedimiento supera el límite de tiempo del área."""

import unittest

from app.analizadores.planes_ejecucion import analizar_plan_reporte, construir_diagrama


def _sentencia(texto: str, duracion_ms: int = None) -> str:
    tiempos = f'<QueryTimeStats ElapsedTime="{duracion_ms}" CpuTime="{duracion_ms}"/>' if duracion_ms is not None else ""
    return f"""
<StmtSimple StatementType="SELECT" StatementSubTreeCost="1" StatementText="{texto}">
  <QueryPlan>{tiempos}
    <RelOp NodeId="0" PhysicalOp="Table Scan" LogicalOp="Table Scan" EstimatedTotalSubtreeCost="1" EstimateRows="1">
      <TableScan><Object Schema="[dbo]" Table="[Cliente]"/></TableScan>
    </RelOp>
  </QueryPlan>
</StmtSimple>"""


def _plan(*sentencias: str) -> str:
    return f"<ShowPlanXML><BatchSequence><Batch><Statements>{''.join(sentencias)}</Statements></Batch></BatchSequence></ShowPlanXML>"


def _tiempo(xml: str, limite):
    return [h for h in analizar_plan_reporte(construir_diagrama(xml), limite) if h.regla == "TIEMPO_EJECUCION_SUPERADO"]


class TestTiempoSuperado(unittest.TestCase):
    def test_supera_el_limite_y_senala_el_bloque_mas_lento(self):
        xml = _plan(_sentencia("SELECT 1", 23_900), _sentencia("SELECT 2", 24_200), _sentencia("SELECT 3", 24_400))
        hallazgos = _tiempo(xml, 30)
        self.assertEqual(len(hallazgos), 1)
        self.assertEqual(hallazgos[0].severidad.value, "alto")
        self.assertEqual(
            hallazgos[0].mensaje,
            "El procedimiento supera el umbral de tiempo establecido: su ejecución tomó 72.5 segundos y el límite "
            "es de 30 segundos. Se recomienda revisar y optimizar la consulta 3, ya que presenta un tiempo de "
            "ejecución de 24.4 segundos, equivalente al 34 % del tiempo total.",
        )
        self.assertEqual(hallazgos[0].nodos, [{"consulta": 3, "nodo": "raiz"}])
        self.assertEqual(hallazgos[0].codigo, "SELECT 3")

    def test_una_sola_consulta(self):
        hallazgos = _tiempo(_plan(_sentencia("SELECT 1", 8_200)), 5)
        self.assertIn("su ejecución tomó 8.20 segundos y el límite es de 5 segundos", hallazgos[0].mensaje)
        self.assertTrue(hallazgos[0].mensaje.endswith(
            "Se recomienda revisar y optimizar la consulta 1, ya que presenta un tiempo de ejecución de 8.20 segundos."))

    def test_dentro_del_limite_no_se_marca(self):
        self.assertEqual(_tiempo(_plan(_sentencia("SELECT 1", 8_200)), 10), [])

    def test_sin_limite_definido_no_se_marca(self):
        self.assertEqual(_tiempo(_plan(_sentencia("SELECT 1", 80_000)), None), [])

    def test_plan_estimado_sin_tiempos_no_se_marca(self):
        self.assertEqual(_tiempo(_plan(_sentencia("SELECT 1")), 1), [])


if __name__ == "__main__":
    unittest.main()
