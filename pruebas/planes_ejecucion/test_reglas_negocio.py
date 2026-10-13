"""Reglas de planes de ejecución del área Negocio."""

import unittest
from pathlib import Path

from app.analizadores.planes_ejecucion import analizar_plan_negocio, construir_diagrama

EJEMPLOS = Path(__file__).resolve().parents[2] / "frontend" / "public" / "ejemplos"


def _plan(advertencias_sentencia: str = "", operadores: str = "") -> str:
    return f"""
<ShowPlanXML><BatchSequence><Batch><Statements>
<StmtSimple StatementType="SELECT" StatementSubTreeCost="1" StatementText="SELECT 1">
  <QueryPlan>
    <Warnings>{advertencias_sentencia}</Warnings>
    <RelOp NodeId="0" PhysicalOp="Nested Loops" LogicalOp="Inner Join" EstimatedTotalSubtreeCost="1" EstimateRows="1">
      <NestedLoops>{operadores}</NestedLoops>
    </RelOp>
  </QueryPlan>
</StmtSimple></Statements></Batch></BatchSequence></ShowPlanXML>"""


def _table_scan(nodo: int, tabla: str, leidas: int = 5000, devueltas: int = 10) -> str:
    return (f'<RelOp NodeId="{nodo}" PhysicalOp="Table Scan" LogicalOp="Table Scan" EstimatedTotalSubtreeCost="0.5" EstimateRows="1">'
            f'<RunTimeInformation><RunTimeCountersPerThread Thread="0" ActualRows="{devueltas}" ActualRowsRead="{leidas}" ActualExecutions="1"/></RunTimeInformation>'
            f'<TableScan><Object Schema="[dbo]" Table="[{tabla}]"/></TableScan></RelOp>')


SPILL = ('<RelOp NodeId="5" PhysicalOp="Sort" LogicalOp="Sort" EstimatedTotalSubtreeCost="0.2" EstimateRows="1">'
         '<Warnings><SpillToTempDb SpillLevel="1" SpilledThreadCount="1"/>'
         '<SortSpillDetails GrantedMemoryKb="1840" UsedMemoryKb="1840" WritesToTempDb="194" ReadsFromTempDb="194"/></Warnings></RelOp>')
MEMORIA = '<MemoryGrantWarning GrantWarningKind="Excessive Grant" RequestedMemory="920576" GrantedMemory="920576" MaxUsedMemory="3072"/>'


def _reglas(xml: str):
    return {h.regla: h for h in analizar_plan_negocio(construir_diagrama(xml))}


class TestReglasNegocio(unittest.TestCase):
    def test_table_scan_sobre_tabla_fisica(self):
        hallazgo = _reglas(_plan(operadores=_table_scan(1, "Clientes")))["TABLE_SCAN_DETECTADO"]
        self.assertEqual(hallazgo.severidad.value, "alto")
        self.assertTrue(hallazgo.mensaje.startswith(
            "Se ha identificado un Table Scan sobre la tabla [dbo].[Clientes]: se leen 5,000 filas y se devuelven 10. "
            "Se recomienda revisar los filtros de la consulta o crear un índice adecuado"))

    def test_table_scan_de_temporales_no_se_marca(self):
        self.assertNotIn("TABLE_SCAN_DETECTADO", _reglas(_plan(operadores=_table_scan(1, "#Temporal"))))
        self.assertNotIn("TABLE_SCAN_DETECTADO", _reglas(_plan(operadores=_table_scan(1, "@Variable"))))

    def test_spill_a_tempdb(self):
        hallazgo = _reglas(_plan(operadores=SPILL))["SPILL_TEMPDB_DETECTADO"]
        self.assertEqual(hallazgo.severidad.value, "alto")
        self.assertIn("Se ha identificado un spill a TempDB en el operador Sort: se escribieron 194 páginas en TempDB.",
                      hallazgo.mensaje)

    def test_sobreestimacion_de_memoria_con_el_estilo_de_la_usuaria(self):
        hallazgo = _reglas(_plan(advertencias_sentencia=MEMORIA))["MEMORIA_SOBREESTIMADA"]
        self.assertEqual(hallazgo.severidad.value, "medio")
        self.assertTrue(hallazgo.mensaje.startswith(
            "Se observa una sobreestimación en la reserva de memoria, ya que se solicitan y reservan 899 MB, "
            "mientras que solo se utilizan 3 MB durante la ejecución."))
        self.assertEqual(hallazgo.nodos, [{"consulta": 1, "nodo": "raiz"}])

    def test_sin_alertas_no_hay_spill_ni_memoria(self):
        reglas = _reglas(_plan(operadores=_table_scan(1, "#T")))
        self.assertEqual(reglas, {})

    def test_plan_de_ejemplo_de_negocio_rompe_las_cinco_reglas(self):
        reglas = _reglas((EJEMPLOS / "plan-ejemplo-negocio.sqlplan").read_bytes())
        self.assertEqual(set(reglas), {
            "TABLE_SCAN_DETECTADO", "CONVERSION_IMPLICITA_DETECTADA", "LECTURA_RESIDUAL_ELEVADA",
            "SPILL_TEMPDB_DETECTADO", "MEMORIA_SOBREESTIMADA",
        })
        self.assertIn("se solicitan y reservan 1,264 MB, mientras que solo se utilizan 136 KB",
                      reglas["MEMORIA_SOBREESTIMADA"].mensaje)


if __name__ == "__main__":
    unittest.main()
