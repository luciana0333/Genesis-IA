"""Parámetros, predicados de cada operador e índices faltantes del plan, tal cual el XML."""

import unittest

from app.analizadores.planes_ejecucion import construir_diagrama

PLAN = """
<ShowPlanXML xmlns="http://schemas.microsoft.com/sqlserver/2004/07/showplan"><BatchSequence><Batch><Statements>
<StmtSimple StatementType="SELECT" StatementSubTreeCost="2.5" StatementEstRows="10" StatementText="SELECT c.cNombre FROM dbo.Credito c">
<QueryPlan CompileTime="5">
  <MissingIndexes><MissingIndexGroup Impact="87.35"><MissingIndex Database="[DBCMAICA]" Schema="[dbo]" Table="[Credito]">
    <ColumnGroup Usage="EQUALITY"><Column Name="[nClienteId]" ColumnId="2"/></ColumnGroup>
    <ColumnGroup Usage="INEQUALITY"><Column Name="[dFecha]" ColumnId="5"/></ColumnGroup>
    <ColumnGroup Usage="INCLUDE"><Column Name="[cNombre]" ColumnId="3"/></ColumnGroup>
  </MissingIndex></MissingIndexGroup></MissingIndexes>
  <RelOp NodeId="0" PhysicalOp="Index Seek" LogicalOp="Index Seek" EstimateRows="10" EstimatedTotalSubtreeCost="2.5">
    <OutputList><ColumnReference Database="[DBCMAICA]" Schema="[dbo]" Table="[Credito]" Alias="[c]" Column="cNombre"/></OutputList>
    <RunTimeInformation><RunTimeCountersPerThread Thread="0" ActualRows="1500" ActualRowsRead="1800" ActualExecutions="1" ActualLogicalReads="12"/></RunTimeInformation>
    <IndexScan>
      <Object Database="[DBCMAICA]" Schema="[dbo]" Table="[Credito]" Index="[IX_Credito_nClienteId]" Alias="[c]"/>
      <SeekPredicates><SeekPredicateNew><SeekKeys><Prefix ScanType="EQ">
        <RangeColumns><ColumnReference Database="[DBCMAICA]" Schema="[dbo]" Table="[Credito]" Alias="[c]" Column="nClienteId"/></RangeColumns>
        <RangeExpressions><ScalarOperator ScalarString="[@nClienteId]"/></RangeExpressions>
      </Prefix></SeekKeys></SeekPredicateNew></SeekPredicates>
      <Predicate><ScalarOperator ScalarString="[DBCMAICA].[dbo].[Credito].[dFecha] as [c].[dFecha]&gt;=[@dDesde]"/></Predicate>
    </IndexScan>
  </RelOp>
  <ParameterList>
    <ColumnReference Column="@dDesde" ParameterDataType="date" ParameterCompiledValue="'2026-01-01'" ParameterRuntimeValue="'2020-01-01'"/>
    <ColumnReference Column="@nClienteId" ParameterDataType="int" ParameterCompiledValue="(15)" ParameterRuntimeValue="(15)"/>
  </ParameterList>
</QueryPlan></StmtSimple></Statements></Batch></BatchSequence></ShowPlanXML>
"""


class TestDetallePlan(unittest.TestCase):
    def setUp(self):
        self.sentencia = construir_diagrama(PLAN)[0]
        self.seek = next(n for n in self.sentencia["nodos"] if n["id"] == "0")

    def test_parametros_con_valor_al_compilar_y_al_ejecutar(self):
        self.assertEqual(self.sentencia["parametros"], [
            {"nombre": "@dDesde", "tipo": "date", "valorCompilado": "'2026-01-01'", "valorEjecucion": "'2020-01-01'"},
            {"nombre": "@nClienteId", "tipo": "int", "valorCompilado": "(15)", "valorEjecucion": "(15)"},
        ])

    def test_predicados_con_el_formato_de_ssms(self):
        predicados = {p["nombre"]: p["texto"] for p in self.seek["predicados"]}
        self.assertEqual(
            predicados["Seek Predicates"],
            "Seek Keys[1]: Prefix: [DBCMAICA].[dbo].[Credito].[nClienteId] as [c].[nClienteId] = Scalar Operator([@nClienteId])",
        )
        self.assertEqual(predicados["Predicate"], "[DBCMAICA].[dbo].[Credito].[dFecha] as [c].[dFecha]>=[@dDesde]")
        self.assertEqual(predicados["Output List"], "[DBCMAICA].[dbo].[Credito].[cNombre] as [c].[cNombre]")

    def test_objeto_y_filas_leidas_del_operador(self):
        self.assertEqual(self.seek["objetoCompleto"], "[DBCMAICA].[dbo].[Credito].[IX_Credito_nClienteId] [c]")
        self.assertEqual(self.seek["filasLeidas"], 1800)

    def test_indice_faltante_con_su_create_index(self):
        indice = self.sentencia["indicesFaltantes"][0]
        self.assertEqual(indice["impacto"], 87.35)
        self.assertEqual((indice["igualdad"], indice["desigualdad"], indice["incluidas"]),
                         (["[nClienteId]"], ["[dFecha]"], ["[cNombre]"]))
        self.assertEqual(
            indice["sentencia"],
            "CREATE NONCLUSTERED INDEX [<Name of Missing Index, sysname,>]\n"
            "ON [dbo].[Credito] ([nClienteId], [dFecha])\nINCLUDE ([cNombre])",
        )
        raiz = self.sentencia["nodos"][0]
        self.assertIn("Missing indexes found.", [a["texto"] for a in raiz["advertencias"]])


if __name__ == "__main__":
    unittest.main()
