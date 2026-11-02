"""Recuadro de la consulta (UPDATE, INSERT, SELECT...): memoria, compilación y costo, como Plan Explorer."""

import unittest

from app.analizadores.planes_ejecucion.diagrama import construir_diagrama

PLAN = """<?xml version="1.0" encoding="utf-16"?>
<ShowPlanXML xmlns="http://schemas.microsoft.com/sqlserver/2004/07/showplan" Version="1.6">
 <BatchSequence><Batch><Statements>
  <StmtSimple StatementText="UPDATE A SET nMonto = 1 FROM #FILT A" StatementId="1" StatementEstRows="2721"
              StatementOptmLevel="FULL" StatementSubTreeCost="1.46552" StatementType="UPDATE"
              RetrievedFromCache="true">
   <StatementSetOptions QUOTED_IDENTIFIER="true" ARITHABORT="true" CONCAT_NULL_YIELDS_NULL="true"
                        ANSI_NULLS="true" ANSI_PADDING="true" ANSI_WARNINGS="true" NUMERIC_ROUNDABORT="false"/>
   <QueryPlan DegreeOfParallelism="1" MemoryGrant="2048" CachedPlanSize="56" CompileTime="76" CompileCPU="68"
              CompileMemory="560">
    <MemoryGrantInfo SerialRequiredMemory="1536" SerialDesiredMemory="2048" RequiredMemory="1536"
                     DesiredMemory="2048" RequestedMemory="2048" GrantWaitTime="0" GrantedMemory="2048"
                     MaxUsedMemory="600" MaxQueryMemory="208056"/>
    <OptimizerHardwareDependentProperties EstimatedAvailableMemoryGrant="52428" EstimatedPagesCached="65536"
                                          EstimatedAvailableDegreeOfParallelism="8" MaxCompileMemory="1000"/>
    <RelOp NodeId="0" PhysicalOp="Table Update" LogicalOp="Update" EstimateRows="2721" EstimateIO="0.01"
           EstimateCPU="0.002" AvgRowSize="9" EstimatedTotalSubtreeCost="1.46552" Parallel="0"
           EstimateRebinds="0" EstimateRewinds="0" EstimatedExecutionMode="Row">
     <OutputList/>
     <RunTimeInformation>
      <RunTimeCountersPerThread Thread="0" ActualRows="2665" ActualEndOfScans="1" ActualExecutions="1"
        ActualExecutionMode="Row" ActualElapsedms="30" ActualCPUms="30"/>
     </RunTimeInformation>
     <Update/>
    </RelOp>
   </QueryPlan>
  </StmtSimple>
 </Statements></Batch></BatchSequence>
</ShowPlanXML>"""


def _consulta():
    return construir_diagrama(PLAN)[0]["nodos"][0]


class RecuadroConsultaTest(unittest.TestCase):
    def test_datos_y_orden_de_plan_explorer(self):
        self.assertEqual(_consulta()["propiedades"], [
            ["Execution Mode", "Row"],
            ["Actual Rows", "2,665"],
            ["Estimated Rows", "2,721"],
            ["Estimated Subtree Cost", "1.46552"],
            ["Cached Plan Size", "56 KB"],
            ["Compile CPU", "68"],
            ["Compile Memory", "560"],
            ["Compile Time", "76"],
            ["Degree of Parallelism", "1"],
            ["Memory Grant", "2,048 KB"],
            ["Desired Memory", "2,048 KB"],
            ["Granted Memory", "2,048 KB"],
            ["Grant Wait Time", "0"],
            ["Max Used Memory", "600 KB"],
            ["Requested Memory", "2,048 KB"],
            ["Required Memory", "1,536 KB"],
            ["Serial Desired Memory", "2,048 KB"],
            ["Serial Required Memory", "1,536 KB"],
            ["Estimated Degree of Parallelism", "8"],
            ["Estimated Available Memory Grant", "52,428 KB"],
            ["Estimated Pages Cached", "65,536"],
            ["Retrieved from Cache", "true"],
            ["Optimization Level", "FULL"],
        ])

    def test_set_options(self):
        self.assertEqual(_consulta()["predicados"], [{
            "nombre": "Set Options",
            "texto": "ANSI_NULLS=TRUE, ANSI_PADDING=TRUE, ANSI_WARNINGS=TRUE, ARITHABORT=TRUE, "
                     "CONCAT_NULL_YIELDS_NULL=TRUE, NUMERIC_ROUNDABORT=FALSE, QUOTED_IDENTIFIER=TRUE",
        }])

    def test_plan_estimado_sin_datos_reales(self):
        estimado = PLAN.replace(PLAN[PLAN.index("     <RunTimeInformation>"):PLAN.index("     <Update/>")], "")
        etiquetas = [fila[0] for fila in construir_diagrama(estimado)[0]["nodos"][0]["propiedades"]]
        self.assertNotIn("Actual Rows", etiquetas)
        self.assertEqual(etiquetas[:2], ["Execution Mode", "Estimated Rows"])


if __name__ == "__main__":
    unittest.main()
