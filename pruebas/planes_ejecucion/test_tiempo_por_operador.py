"""Tiempo real por operador: duración, CPU y lecturas físicas (como el tooltip de SSMS)."""

import unittest

from app.analizadores.planes_ejecucion import analizar_plan_ejecucion, construir_diagrama

PLAN = """
<ShowPlanXML><BatchSequence><Batch><Statements>
<StmtSimple StatementType="SELECT" StatementSubTreeCost="1" StatementText="SELECT 1">
  <QueryPlan>
    <RelOp NodeId="0" PhysicalOp="Clustered Index Scan" LogicalOp="Clustered Index Scan" EstimateRows="10" EstimatedTotalSubtreeCost="1">
      <RunTimeInformation>
        <RunTimeCountersPerThread Thread="1" ActualRows="6" ActualExecutions="1" ActualLogicalReads="40" ActualPhysicalReads="3" ActualElapsedms="120" ActualCPUms="70"/>
        <RunTimeCountersPerThread Thread="2" ActualRows="4" ActualExecutions="1" ActualLogicalReads="30" ActualPhysicalReads="2" ActualElapsedms="150" ActualCPUms="60"/>
      </RunTimeInformation>
      <IndexScan><Object Schema="[dbo]" Table="[Cliente]" Index="[PK_Cliente]"/></IndexScan>
    </RelOp>
  </QueryPlan>
</StmtSimple></Statements></Batch></BatchSequence></ShowPlanXML>
"""


class TestTiempoPorOperador(unittest.TestCase):
    def test_en_el_diagrama(self):
        nodo = construir_diagrama(PLAN)[0]["nodos"][1]  # [0] es el SELECT
        self.assertEqual(nodo["duracionMs"], 150)  # el hilo que más tardó
        self.assertEqual(nodo["cpuMs"], 130)  # suma de los hilos
        self.assertEqual(nodo["lecturasFisicas"], 5)
        self.assertEqual(nodo["lecturas"], 70)

    def test_en_la_tabla_de_operadores(self):
        _, operadores, _ = analizar_plan_ejecucion(PLAN)
        operador = operadores[0]
        self.assertEqual((operador.duracion_ms, operador.cpu_ms), (150, 130))

    def test_plan_estimado_sin_tiempos(self):
        estimado = PLAN.replace("<RunTimeInformation>", "<!--").replace("</RunTimeInformation>", "-->")
        nodo = construir_diagrama(estimado)[0]["nodos"][1]
        self.assertIsNone(nodo["duracionMs"])
        self.assertIsNone(nodo["cpuMs"])


if __name__ == "__main__":
    unittest.main()
