import unittest

from app.analizadores.planes_ejecucion import analizar_plan_ejecucion
from app.reglas.reglas_diccionario import obtener_regla


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
    def test_reglas_de_planes_estan_registradas_en_el_catalogo(self):
        self.assertEqual(obtener_regla("CONVERSION_IMPLICITA").alcance, "plan_ejecucion")
        self.assertEqual(obtener_regla("SPILL_TEMPDB").alcance, "plan_ejecucion")
        self.assertEqual(obtener_regla("TABLE_SCAN").alcance, "plan_ejecucion")

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


def _table_scan(nodo, tabla):
    return (f'<RelOp NodeId="{nodo}" PhysicalOp="Table Scan" LogicalOp="Table Scan" EstimateRows="10">'
            f'<TableScan><Object Database="[DB]" Schema="[dbo]" Table="[{tabla}]" /></TableScan></RelOp>')


def _plan(*consultas):
    return "<ShowPlanXML>" + "".join(
        f"<StmtSimple><QueryPlan>{''.join(operadores)}</QueryPlan></StmtSimple>" for operadores in consultas
    ) + "</ShowPlanXML>"


class TestAgrupacionPlanes(unittest.TestCase):
    def test_varios_table_scan_se_agrupan_con_tablas_y_nodos(self):
        plan = _plan([_table_scan(9, "Cliente"), _table_scan(3, "Credito"), _table_scan(1, "Cliente")])
        hallazgos, _, _ = analizar_plan_ejecucion(plan)
        self.assertEqual([h.regla for h in hallazgos], ["TABLE_SCAN"])
        self.assertIn("Se identificaron 2 tablas que se leen completas con un Table Scan, en los nodos 1, 3, 9: "
                      "[DB].[dbo].[Cliente] (nodos 1, 9); [DB].[dbo].[Credito] (nodo 3).", hallazgos[0].mensaje)

    def test_con_varias_consultas_indica_la_consulta_de_cada_nodo(self):
        plan = _plan([_table_scan(1, "Cliente")], [_table_scan(4, "Cliente"), _table_scan(2, "Mov")])
        hallazgos, _, _ = analizar_plan_ejecucion(plan)
        self.assertEqual(len(hallazgos), 1)
        self.assertIn("en las consultas 1, 2: [DB].[dbo].[Cliente] (nodo 1 de la consulta 1, nodo 4 de la "
                      "consulta 2); [DB].[dbo].[Mov] (nodo 2 de la consulta 2).", hallazgos[0].mensaje)

    def test_un_solo_table_scan_indica_su_nodo(self):
        hallazgos, _, _ = analizar_plan_ejecucion(_plan([_table_scan(2, "Mov")]))
        self.assertTrue(hallazgos[0].mensaje.startswith(
            "Se lee la tabla [DB].[dbo].[Mov] completa con un Table Scan (nodo 2). Confirme"))


if __name__ == "__main__":
    unittest.main()