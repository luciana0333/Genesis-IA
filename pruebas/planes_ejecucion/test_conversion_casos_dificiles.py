"""Conversión implícita en casos que antes se perdían: paréntesis anidados y consultas de cursores."""

import unittest

from app.analizadores.planes_ejecucion import analizar_plan_negocio, analizar_plan_reporte, construir_diagrama

_SCAN = """
<RelOp NodeId="0" PhysicalOp="Clustered Index Scan" LogicalOp="Clustered Index Scan" EstimatedTotalSubtreeCost="1" EstimateRows="10">
  <IndexScan><Object Schema="[dbo]" Table="[Movimiento]" Index="[PK_Movimiento]"/></IndexScan>
</RelOp>"""


def _simple(advertencia: str) -> str:
    return f"""
<ShowPlanXML><BatchSequence><Batch><Statements>
<StmtSimple StatementType="SELECT" StatementSubTreeCost="1" StatementText="SELECT 1">
  <QueryPlan><Warnings>{advertencia}</Warnings>{_SCAN}</QueryPlan>
</StmtSimple></Statements></Batch></BatchSequence></ShowPlanXML>"""


def _cursor(advertencia: str) -> str:
    return f"""
<ShowPlanXML><BatchSequence><Batch><Statements>
<StmtCursor StatementType="DECLARE CURSOR" StatementText="DECLARE cur CURSOR FOR SELECT cCtaCod FROM dbo.Movimiento">
  <CursorPlan CursorName="cur" CursorActualType="Dynamic">
    <Operation OperationType="FetchQuery">
      <QueryPlan><Warnings>{advertencia}</Warnings>{_SCAN}</QueryPlan>
    </Operation>
  </CursorPlan>
</StmtCursor></Statements></Batch></BatchSequence></ShowPlanXML>"""


ANIDADA = ('<PlanAffectingConvert ConvertIssue="Seek Plan" '
           'Expression="[M].[nId]=CONVERT_IMPLICIT(int,substring([M].[cMovNro],(1),(14)),0)"/>')
SIMPLE = '<PlanAffectingConvert ConvertIssue="Seek Plan" Expression="[M].[nId]=CONVERT_IMPLICIT(int,[M].[cCod],0)"/>'


def _conversiones(xml: str, analizar=analizar_plan_reporte):
    return [h for h in analizar(construir_diagrama(xml)) if h.regla == "CONVERSION_IMPLICITA_DETECTADA"]


class TestConversionCasosDificiles(unittest.TestCase):
    def test_parentesis_anidados_dentro_de_la_conversion(self):
        for analizar in (analizar_plan_reporte, analizar_plan_negocio):
            with self.subTest(modulo=analizar.__name__):
                hallazgos = _conversiones(_simple(ANIDADA), analizar)
                self.assertEqual(len(hallazgos), 1)
                self.assertIn("CONVERT_IMPLICIT(int,substring([M].[cMovNro],(1),(14)),0)", hallazgos[0].mensaje)

    def test_consulta_de_un_cursor(self):
        sentencias = construir_diagrama(_cursor(SIMPLE))
        self.assertEqual(len(sentencias), 1)
        self.assertEqual(sentencias[0]["tipo"], "DECLARE")
        self.assertEqual([n["fisica"] for n in sentencias[0]["nodos"]], ["DECLARE", "Clustered Index Scan"])
        for analizar in (analizar_plan_reporte, analizar_plan_negocio):
            with self.subTest(modulo=analizar.__name__):
                self.assertEqual(len(_conversiones(_cursor(SIMPLE), analizar)), 1)

    def test_conversion_explicita_sigue_sin_marcarse(self):
        explicita = '<PlanAffectingConvert ConvertIssue="Cardinality Estimate" Expression="CONVERT(int,substring([M].[c],(1),(2)),0)"/>'
        self.assertEqual(_conversiones(_simple(explicita)), [])


if __name__ == "__main__":
    unittest.main()
