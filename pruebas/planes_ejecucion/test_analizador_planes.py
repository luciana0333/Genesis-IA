import unittest

from app.analizadores.planes_ejecucion import analizar_plan_ejecucion


PLAN_REAL_MINIMO = """
<ShowPlanXML xmlns="http://schemas.microsoft.com/sqlserver/2004/07/showplan">
  <BatchSequence><Batch><Statements><StmtSimple>
    <QueryPlan>
      <MemoryGrantInfo RequestedMemory="4096" GrantedMemory="8192" MaxUsedMemory="1024" />
      <RelOp NodeId="1" PhysicalOp="Table Scan" LogicalOp="Table Scan" EstimateRows="10">
        <IndexScan><Object Database="[DB]" Schema="[dbo]" Table="[Cliente]" /></IndexScan>
        <RunTimeInformation><RunTimeCountersPerThread ActualRows="100" ActualRowsRead="1000" ActualLogicalReads="150000" /></RunTimeInformation>
        <ComputeScalar><Convert Implicit="1" DataType="varchar" /></ComputeScalar>
        <Warnings><SpillOccurred /></Warnings>
      </RelOp>
    </QueryPlan>
  </StmtSimple></Statements></Batch></BatchSequence>
</ShowPlanXML>
"""


class TestAnalizadorPlanes(unittest.TestCase):
    def test_analiza_operadores_alertas_y_memoria(self):
        hallazgos, operadores, memoria = analizar_plan_ejecucion(PLAN_REAL_MINIMO)
        reglas = {hallazgo.regla for hallazgo in hallazgos}

        self.assertEqual(len(operadores), 1)
        self.assertEqual(operadores[0].objeto, "[DB].[dbo].[Cliente]")
        self.assertEqual(memoria.memoria_concedida_kb, 8192)
        self.assertTrue({
            "CONVERSION_IMPLICITA",
            "SPILL_TEMPDB",
            "TABLE_SCAN",
            "LECTURAS_LOGICAS_ELEVADAS",
            "SOBREESTIMACION_FILAS",
            "MEMORIA_CONCEDIDA_SOBREDIMENSIONADA",
        }.issubset(reglas))

    def test_acepta_plan_sin_namespace_y_sin_alertas(self):
        hallazgos, operadores, memoria = analizar_plan_ejecucion(
            "<ShowPlanXML><QueryPlan><RelOp NodeId='1' PhysicalOp='Index Seek' LogicalOp='Index Seek' EstimateRows='10' /></QueryPlan></ShowPlanXML>"
        )

        self.assertEqual(hallazgos, [])
        self.assertEqual(len(operadores), 1)
        self.assertIsNone(memoria)


if __name__ == "__main__":
    unittest.main()