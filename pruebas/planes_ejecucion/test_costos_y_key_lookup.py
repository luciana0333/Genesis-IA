"""% de costo sobre la suma de los operadores (row goal) y Key Lookup, como SSMS y Plan Explorer."""

import unittest

from app.analizadores.planes_ejecucion.diagrama import construir_diagrama


def _relop(nodo, fisica, subarbol, hijos="", indice=""):
    return (f'<RelOp NodeId="{nodo}" PhysicalOp="{fisica}" LogicalOp="{fisica}" EstimateRows="1" '
            f'EstimatedTotalSubtreeCost="{subarbol}" EstimateRebinds="0" EstimateRewinds="0">'
            f'{indice}<X>{hijos}</X></RelOp>')


# IF ... OR EXISTS: por el «row goal», el Scan (0.0135965) cuesta más que su padre (Concatenation, 0.013591).
LOOKUP = '<IndexScan Lookup="true"><Object Database="[DB]" Schema="[dbo]" Table="[Eval]" Index="[PK_Eval]"/></IndexScan>'
ARBOL = _relop(3, "Concatenation", "0.013591",
               _relop(7, "Nested Loops", "0.013589",
                      _relop(8, "Index Seek", "0.009782") + _relop(10, "Clustered Index Seek", "0.0032831", "", LOOKUP))
               + _relop(11, "Clustered Index Scan", "0.0135965"))
PLAN = (f'<ShowPlanXML xmlns="http://schemas.microsoft.com/sqlserver/2004/07/showplan"><BatchSequence><Batch>'
        f'<Statements><StmtSimple StatementId="1" StatementType="COND WITH QUERY" StatementSubTreeCost="0.0135965" '
        f'StatementText="IF ... OR EXISTS (...)"><QueryPlan>{ARBOL}</QueryPlan></StmtSimple></Statements>'
        f'</Batch></BatchSequence></ShowPlanXML>')


class CostosYKeyLookupTest(unittest.TestCase):
    def setUp(self):
        self.sentencia = construir_diagrama(PLAN)[0]
        self.nodos = {n["id"]: n for n in self.sentencia["nodos"]}

    def test_porcentajes_sobre_la_suma_como_plan_explorer(self):
        self.assertEqual(self.nodos["11"]["costoPct"], 50.0)
        self.assertEqual(self.nodos["8"]["costoPct"], 36.0)
        self.assertEqual(self.nodos["10"]["costoPct"], 12.1)
        self.assertEqual(self.nodos["7"]["costoPct"], 1.9)

    def test_key_lookup(self):
        lookup = self.nodos["10"]
        self.assertEqual((lookup["fisica"], lookup["logica"]), ("Key Lookup", "Key Lookup"))
        propiedades = dict(lookup["propiedades"])
        self.assertEqual(propiedades["Physical Operation"], "Key Lookup")
        self.assertEqual(propiedades["Estimated Operator Cost"], "0.0032831 (12%)")

    def test_cond_with_query_completo(self):
        self.assertEqual(self.sentencia["tipo"], "COND WITH QUERY")


if __name__ == "__main__":
    unittest.main()
