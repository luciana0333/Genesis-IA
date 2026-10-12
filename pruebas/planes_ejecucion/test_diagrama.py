import unittest
from pathlib import Path

from app.analizadores.planes_ejecucion import construir_diagrama

EJEMPLO = Path(__file__).resolve().parents[2] / "frontend" / "public" / "ejemplos" / "plan-ejemplo.sqlplan"

PLAN_ADVERTENCIAS = """
<ShowPlanXML><BatchSequence><Batch><Statements>
  <StmtSimple StatementType="SELECT" StatementSubTreeCost="10" StatementText="SELECT 1">
    <QueryPlan>
      <Warnings>
        <PlanAffectingConvert ConvertIssue="Seek Plan" Expression="[DC].[nDocTpo]=CONVERT_IMPLICIT(int,[CL].[nCons],0)" />
        <MemoryGrantWarning GrantWarningKind="Excessive Grant" RequestedMemory="920576" GrantedMemory="920576" MaxUsedMemory="3072" />
      </Warnings>
      <MissingIndexes><MissingIndexGroup Impact="80" /></MissingIndexes>
      <RelOp NodeId="0" PhysicalOp="Nested Loops" LogicalOp="Inner Join" EstimatedTotalSubtreeCost="10" EstimateRows="5">
        <NestedLoops>
          <RelOp NodeId="1" PhysicalOp="Table Scan" LogicalOp="Table Scan" EstimatedTotalSubtreeCost="6" EstimateRows="5">
            <TableScan><Object Schema="[dbo]" Table="[Cliente]" /></TableScan>
          </RelOp>
          <RelOp NodeId="2" PhysicalOp="Index Seek" LogicalOp="Index Seek" EstimatedTotalSubtreeCost="1" EstimateRows="1">
            <IndexScan><Object Schema="[dbo]" Table="[Credito]" Index="[IX_Credito]" /></IndexScan>
          </RelOp>
        </NestedLoops>
      </RelOp>
    </QueryPlan>
  </StmtSimple>
</Statements></Batch></BatchSequence></ShowPlanXML>
"""


class TestDiagramaPlan(unittest.TestCase):
    def test_arbol_con_padres_costos_y_objetos(self):
        nodos = {n["id"]: n for n in construir_diagrama(PLAN_ADVERTENCIAS)[0]["nodos"]}
        self.assertEqual(nodos["raiz"]["fisica"], "SELECT")
        self.assertEqual((nodos["0"]["padre"], nodos["1"]["padre"], nodos["2"]["padre"]), ("raiz", "0", "0"))
        self.assertEqual((nodos["0"]["costoPct"], nodos["1"]["costoPct"]), (30.0, 60.0))
        self.assertEqual((nodos["2"]["objeto"], nodos["2"]["indice"]), ("[dbo].[Credito]", "[IX_Credito]"))

    def test_advertencias_con_el_texto_de_ssms(self):
        textos = [a["texto"] for a in construir_diagrama(PLAN_ADVERTENCIAS)[0]["nodos"][0]["advertencias"]]
        self.assertEqual(textos, [
            "Convert Issue: SeekPlan [DC].[nDocTpo]=CONVERT_IMPLICIT(int,[CL].[nCons],0)",
            "Excessive Grant: Requested (899 MB), Granted (899 MB), Max Used (3 MB)",
            "Missing indexes found.",
        ])

    def test_plan_de_ejemplo_con_spills_y_filas_reales(self):
        sentencia = construir_diagrama(EJEMPLO.read_bytes())[0]
        self.assertEqual(len(sentencia["nodos"]), 28)
        spills = [a for n in sentencia["nodos"] for a in n["advertencias"] if a["tipo"] == "spill"]
        self.assertEqual(len(spills), 3)
        self.assertTrue(all(n["filasReales"] is not None for n in sentencia["nodos"][1:]))


    def test_datos_de_la_grilla_de_sentencias(self):
        sentencia = construir_diagrama(EJEMPLO.read_bytes())[0]
        self.assertEqual(
            (sentencia["compilacionMs"], sentencia["duracionMs"], sentencia["cpuMs"], sentencia["lecturas"]),
            (18, 1076, 944, 101041),
        )
        self.assertEqual((round(sentencia["filasEstimadas"]), sentencia["filasReales"]), (855, 250))

    def test_codigo_de_la_sentencia_tal_cual(self):
        codigo = construir_diagrama(EJEMPLO.read_bytes())[0]["codigo"]
        self.assertTrue(codigo.startswith("SELECT\n    U.Nombre,\n    A.Descripcion,"))
        self.assertIn("-- ❌ conversión en JOIN", codigo)
        self.assertNotIn("\r", codigo)


if __name__ == "__main__":
    unittest.main()
