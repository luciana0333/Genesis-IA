"""Negocio: sobreestimación de memoria.

Con la alerta Excessive Grant en el operador inicial: observación en medio (desde 80 MB y usando menos del 50 %).
Sin la alerta (usuaria, 25 nov.): solo si reserva 100 MB o más y usa 30 % o menos, como riesgo identificado por
Genesis, con el mismo texto y en bajo.
"""

import unittest

from app.analizadores.planes_ejecucion import analizar_plan_negocio, construir_diagrama


def _plan(concedida_kb: int, usada_kb: int, con_alerta: bool = False) -> str:
    alerta = (
        f'<Warnings><MemoryGrantWarning GrantWarningKind="Excessive Grant" RequestedMemory="{concedida_kb}" '
        f'GrantedMemory="{concedida_kb}" MaxUsedMemory="{usada_kb}"/></Warnings>'
    ) if con_alerta else ""
    return f"""
<ShowPlanXML><BatchSequence><Batch><Statements>
<StmtSimple StatementType="SELECT" StatementSubTreeCost="1" StatementText="SELECT 1">
  <QueryPlan>
    {alerta}
    <MemoryGrantInfo RequestedMemory="{concedida_kb}" GrantedMemory="{concedida_kb}" MaxUsedMemory="{usada_kb}"/>
    <RelOp NodeId="0" PhysicalOp="Sort" LogicalOp="Sort" EstimateRows="1" EstimatedTotalSubtreeCost="1">
      <Sort><OrderBy/></Sort>
    </RelOp>
  </QueryPlan>
</StmtSimple></Statements></Batch></BatchSequence></ShowPlanXML>"""


def _memoria(xml: str):
    return [h for h in analizar_plan_negocio(construir_diagrama(xml)) if h.regla == "MEMORIA_SOBREESTIMADA"]


def _riesgo(xml: str):
    return [h for h in analizar_plan_negocio(construir_diagrama(xml)) if h.regla == "MEMORIA_SOBREESTIMADA_GENESIS"]


class TestMemoriaDesproporcionada(unittest.TestCase):
    def test_sin_alerta_reserva_grande_y_poco_uso_va_en_riesgos_en_bajo(self):
        self.assertEqual(_memoria(_plan(200 * 1024, 30)), [])  # sin la alerta ya no va arriba
        riesgos = _riesgo(_plan(200 * 1024, 30))
        self.assertEqual(len(riesgos), 1)
        self.assertEqual(riesgos[0].severidad.value.lower(), "bajo")
        self.assertTrue(riesgos[0].complementario)  # «Riesgos identificados por Genesis»
        self.assertEqual(
            riesgos[0].mensaje,
            "Se observa una sobreestimación en la reserva de memoria, ya que se solicitan y reservan 200 MB, "
            "mientras que solo se utilizan 30 KB durante la ejecución. Corregir la sobreestimación de memoria, ya "
            "que la cantidad reservada es muy alta para la cantidad utilizada; si bien se trata de tablas "
            "transaccionales, se debe reducir lo más posible.",
        )

    def test_sin_alerta_limites(self):
        # Casos reales de la usuaria (25 nov.): 126 MB → 11 MB y 644 MB → 35 MB sí; 80 MB → 18 MB no.
        self.assertEqual(len(_riesgo(_plan(126 * 1024, 11 * 1024))), 1)
        self.assertEqual(len(_riesgo(_plan(100 * 1024, 30 * 1024))), 1)  # justo 100 MB y 30 %: se marca
        self.assertEqual(_riesgo(_plan(100 * 1024, 31 * 1024)), [])  # usa más del 30 %
        self.assertEqual(_riesgo(_plan(99 * 1024, 1024)), [])  # menos de 100 MB
        self.assertEqual(_riesgo(_plan(80 * 1024, 18 * 1024)), [])
        self.assertEqual(_riesgo(_plan(1000 * 1024, 400 * 1024)), [])  # 40 %: no

    def test_uso_razonable_no_se_marca(self):
        self.assertEqual(_memoria(_plan(200 * 1024, 160 * 1024)), [])  # usa el 80 %
        self.assertEqual(_riesgo(_plan(200 * 1024, 160 * 1024)), [])

    def test_reserva_pequena_no_se_marca(self):
        self.assertEqual(_memoria(_plan(5 * 1024, 10)), [])
        self.assertEqual(_riesgo(_plan(79 * 1024, 10)), [])

    def test_con_alerta_y_desproporcion_sale_una_sola_vez(self):
        self.assertEqual(len(_memoria(_plan(200 * 1024, 30, con_alerta=True))), 1)
        self.assertEqual(_riesgo(_plan(200 * 1024, 30, con_alerta=True)), [])  # no se repite en riesgos

    def test_alerta_con_reserva_minima_no_se_marca(self):
        # Caso de la usuaria: Excessive Grant de 1 MB reservado y 16 KB usados; en un entorno transaccional
        # es mínimo. La alerta se sigue viendo en el diagrama, pero no es observación.
        self.assertEqual(_memoria(_plan(1024, 16, con_alerta=True)), [])
        self.assertEqual(_memoria(_plan(79 * 1024, 16, con_alerta=True)), [])

    def test_alerta_desde_80_mb_se_marca(self):
        self.assertEqual(len(_memoria(_plan(80 * 1024, 16, con_alerta=True))), 1)

    def test_alerta_con_uso_de_la_mitad_o_mas_no_se_marca(self):
        self.assertEqual(_memoria(_plan(100 * 1024, 90 * 1024, con_alerta=True)), [])
        self.assertEqual(_memoria(_plan(100 * 1024, 50 * 1024, con_alerta=True)), [])  # justo el 50 %

    def test_alerta_desde_80_mb_y_menos_de_la_mitad_se_marca(self):
        self.assertEqual(len(_memoria(_plan(100 * 1024, 49 * 1024, con_alerta=True))), 1)
        self.assertEqual(len(_memoria(_plan(80 * 1024, 39 * 1024, con_alerta=True))), 1)


if __name__ == "__main__":
    unittest.main()
