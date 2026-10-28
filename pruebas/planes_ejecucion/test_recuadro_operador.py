"""Recuadro del operador: todos los datos del XML con los nombres y el orden de SQL Server (SSMS)."""

import unittest

from app.analizadores.planes_ejecucion.diagrama import construir_diagrama

PLAN = """<?xml version="1.0" encoding="utf-16"?>
<ShowPlanXML xmlns="http://schemas.microsoft.com/sqlserver/2004/07/showplan" Version="1.6">
 <BatchSequence><Batch><Statements>
  <StmtSimple StatementText="SELECT @n = SUBSTRING(cCtaCod,9,1) FROM dbo.T WHERE bEstado = 1" StatementId="1"
              StatementSubTreeCost="0.0695343" StatementType="SELECT">
   <QueryPlan>
    <RelOp NodeId="0" PhysicalOp="Compute Scalar" LogicalOp="Compute Scalar" EstimateRows="1.11156"
           EstimateIO="0" EstimateCPU="0.0004593" AvgRowSize="29" EstimatedTotalSubtreeCost="0.0695343"
           Parallel="0" EstimateRebinds="0" EstimateRewinds="0" EstimatedExecutionMode="Row">
     <OutputList><ColumnReference Column="Expr1002"/></OutputList>
     <ComputeScalar>
      <DefinedValues><DefinedValue>
       <ColumnReference Column="Expr1002"/>
       <ScalarOperator ScalarString="CONVERT_IMPLICIT(int,substring([DB].[dbo].[T].[cCtaCod],(9),(1)),0)"/>
      </DefinedValue></DefinedValues>
      <RelOp NodeId="1" PhysicalOp="Clustered Index Scan" LogicalOp="Clustered Index Scan" EstimateRows="1.11156"
             EstimatedRowsRead="4593" EstimateIO="0.0638657" EstimateCPU="0.0052093" AvgRowSize="37"
             EstimatedTotalSubtreeCost="0.069075" Parallel="0" EstimateRebinds="0" EstimateRewinds="0"
             EstimatedExecutionMode="Row">
       <OutputList><ColumnReference Database="[DB]" Schema="[dbo]" Table="[T]" Column="cCtaCod"/></OutputList>
       <RunTimeInformation>
        <RunTimeCountersPerThread Thread="0" ActualRows="0" ActualRowsRead="4593" Batches="0" ActualEndOfScans="1"
          ActualExecutions="1" ActualExecutionMode="Row" ActualElapsedms="3" ActualCPUms="3" ActualScans="1"
          ActualLogicalReads="85" ActualPhysicalReads="0"/>
       </RunTimeInformation>
       <IndexScan Ordered="0" ForcedIndex="0" ForceScan="0" NoExpandHint="0" Storage="RowStore">
        <Object Database="[DB]" Schema="[dbo]" Table="[T]" Index="[PK_T]" IndexKind="Clustered" Storage="RowStore"/>
       </IndexScan>
      </RelOp>
     </ComputeScalar>
    </RelOp>
   </QueryPlan>
  </StmtSimple>
 </Statements></Batch></BatchSequence>
</ShowPlanXML>"""


def _nodo(fisica):
    return next(n for n in construir_diagrama(PLAN)[0]["nodos"] if n["fisica"] == fisica)


class RecuadroOperadorTest(unittest.TestCase):
    def test_defined_values_muestra_la_conversion(self):
        predicados = {p["nombre"]: p["texto"] for p in _nodo("Compute Scalar")["predicados"]}
        self.assertEqual(
            predicados["Defined Values"],
            "[Expr1002] = Scalar Operator(CONVERT_IMPLICIT(int,substring([DB].[dbo].[T].[cCtaCod],(9),(1)),0))",
        )

    def test_datos_con_nombres_y_orden_de_sql_server(self):
        propiedades = dict(_nodo("Clustered Index Scan")["propiedades"])
        self.assertEqual(list(propiedades)[:5], [
            "Physical Operation", "Logical Operation", "Actual Execution Mode", "Estimated Execution Mode", "Storage",
        ])
        self.assertEqual(propiedades["Number of Rows Read"], "4593")
        self.assertEqual(propiedades["Estimated I/O Cost"], "0.0638657")
        self.assertEqual(propiedades["Estimated CPU Cost"], "0.0052093")
        self.assertEqual(propiedades["Estimated Subtree Cost"], "0.069075")
        self.assertEqual(propiedades["Estimated Number of Rows to be Read"], "4593")
        self.assertEqual(propiedades["Estimated Row Size"], "37 B")
        self.assertEqual(propiedades["Ordered"], "False")
        self.assertEqual(propiedades["Node ID"], "1")
        self.assertTrue(propiedades["Estimated Operator Cost"].startswith("0.069075 ("))

    def test_plan_estimado_no_inventa_datos_reales(self):
        propiedades = dict(_nodo("Compute Scalar")["propiedades"])
        self.assertNotIn("Actual Execution Mode", propiedades)
        self.assertNotIn("Number of Executions", propiedades)


if __name__ == "__main__":
    unittest.main()
