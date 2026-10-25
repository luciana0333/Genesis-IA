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


def _alerta(expresion: str, problema: str = "Cardinality Estimate") -> str:
    return f'<PlanAffectingConvert ConvertIssue="{problema}" Expression="{expresion}"/>'


def _insert(advertencias: str, numero_consultas: int = 1) -> str:
    """Varias consultas; la última es un INSERT con las alertas (como la consulta 8 de la usuaria)."""
    previas = "".join(
        f'<StmtSimple StatementType="SELECT" StatementSubTreeCost="1" StatementText="SELECT {n}"><QueryPlan>{_SCAN}</QueryPlan></StmtSimple>'
        for n in range(1, numero_consultas)
    )
    return f"""
<ShowPlanXML><BatchSequence><Batch><Statements>{previas}
<StmtSimple StatementType="INSERT" StatementSubTreeCost="1" StatementText="INSERT INTO #T SELECT ...">
  <QueryPlan><Warnings>{advertencias}</Warnings>{_SCAN}</QueryPlan>
</StmtSimple></Statements></Batch></BatchSequence></ShowPlanXML>"""


# Las 12 conversiones del caso de la usuaria (consulta 8): 2 a varchar(100), 4 a int y 6 a varchar(10).
DOCE = "".join(
    [_alerta(f"CONVERT_IMPLICIT(varchar(100),[Expr{n}],0)") for n in (1019, 1018)]
    + [_alerta(f"CONVERT_IMPLICIT(int,[Expr{n}],0)") for n in (1034, 1033, 1049, 1048)]
    + [_alerta(f"CONVERT_IMPLICIT(varchar(10),[Expr{n}],0)") for n in (1064, 1063, 1079, 1078, 1094, 1093)]
)


class TestConversionesEnUnMismoOperador(unittest.TestCase):
    def test_caso_de_la_usuaria_doce_en_el_insert(self):
        for analizar in (analizar_plan_reporte, analizar_plan_negocio):
            with self.subTest(modulo=analizar.__name__):
                hallazgos = _conversiones(_insert(DOCE, numero_consultas=8), analizar)
                self.assertEqual(len(hallazgos), 1)
                self.assertEqual(
                    hallazgos[0].mensaje,
                    "Se han identificado 12 conversiones implícitas en el operador INSERT de la consulta 8, que "
                    "alteran la estimación de filas (CardinalityEstimate): 6 a varchar(10), 4 a int y 2 a "
                    "varchar(100). Se recomienda revisar que los tipos de datos de las columnas de la tabla donde se "
                    "inserta coincidan con los de los valores del SELECT, para evitar conversiones implícitas y "
                    "mejorar el rendimiento de la consulta.",
                )
                self.assertEqual(hallazgos[0].nodos, [{"consulta": 8, "nodo": "raiz"}])

    def test_columna_real_se_muestra_y_las_internas_se_resumen(self):
        alertas = (_alerta("CONVERT_IMPLICIT(int,[CL].[nConsEquivalente],0)")
                   + _alerta("CONVERT_IMPLICIT(int,[Expr1001],0)") + _alerta("CONVERT_IMPLICIT(int,[Expr1002],0)"))
        hallazgo = _conversiones(_simple(alertas))[0]
        self.assertTrue(hallazgo.mensaje.startswith(
            "Se han identificado 3 conversiones implícitas en el operador SELECT, que alteran la estimación de filas "
            "(CardinalityEstimate): «CONVERT_IMPLICIT(int,[CL].[nConsEquivalente],0)» y 2 a int. Se recomienda "
            "revisar las alertas por conversiones implícitas"))
        self.assertTrue(hallazgo.mensaje.endswith("de la consulta."))

    def test_varios_operadores_una_linea_por_operador(self):
        xml = _insert(DOCE, numero_consultas=8).replace(
            '<StmtSimple StatementType="SELECT" StatementSubTreeCost="1" StatementText="SELECT 3"><QueryPlan>',
            '<StmtSimple StatementType="SELECT" StatementSubTreeCost="1" StatementText="SELECT 3"><QueryPlan>'
            '<Warnings>' + _alerta("[DC].[nDocTpo]=CONVERT_IMPLICIT(int,[CL].[nConsEquivalente],0)", "Seek Plan")
            + '</Warnings>')
        hallazgo = _conversiones(xml)[0]
        self.assertEqual(
            hallazgo.mensaje,
            "Se identificaron 13 conversiones implícitas, en las consultas 3, 8: Operador SELECT de la consulta 3: "
            "«[DC].[nDocTpo]=CONVERT_IMPLICIT(int,[CL].[nConsEquivalente],0)», que impide buscar en el índice "
            "(SeekPlan); Operador INSERT de la consulta 8: 12 conversiones (6 a varchar(10), 4 a int y 2 a "
            "varchar(100)), que alteran la estimación de filas (CardinalityEstimate). Se recomienda revisar las "
            "alertas por conversiones implícitas y homologar los tipos de datos de las columnas involucradas para "
            "evitar conversiones implícitas y mejorar el rendimiento de las consultas.",
        )


if __name__ == "__main__":
    unittest.main()
