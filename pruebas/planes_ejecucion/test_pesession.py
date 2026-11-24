"""Sesiones de SQL Sentry Plan Explorer (.pesession) en Planes (usuaria, 24 nov.).

Caso real (no se guarda en el repositorio: trae la instancia y el usuario de conexión): «PE CONCILIACION.
PA_PagosSeguros_Ins_PagosSegurosDetalleHistorico.pesession», un .zip con meta.json y 1.queryanalysis (objeto .NET
serializado) que guarda un ShowPlanXML por sentencia (6). Genesis lo rechazaba por no ser .sqlplan.

Aquí se arma una sesión con el mismo formato: bytes .NET alrededor de cada plan y el EXEC pegado al byte de su largo.
"""
import io
import re
import unittest
import zipfile
from pathlib import Path

from app.analizadores.planes_ejecucion.lote import analizar_lote, extraer_planes
from app.analizadores.planes_ejecucion.pesession import es_pesession, nombre_del_procedimiento, unir_planes

RECURSOS = Path(__file__).parent / "recursos"


def _plan(archivo: str, numero: int) -> bytes:
    texto = (RECURSOS / archivo).read_bytes().decode("utf-8-sig")
    texto = re.sub(r'StatementId="\d+"', f'StatementId="{numero}"', texto)
    return texto[texto.index("<ShowPlanXML"):].encode("utf-8")


def _consulta(planes, exec_="EXEC Conciliacion.PA_PagosSeguros_Ins_X 29, '25M40244'") -> bytes:
    """Bytes como los del objeto .NET: cabecera binaria, textos con su largo delante y los planes en medio."""
    cuerpo = b"\x00\x01\x00\x00\x00\xff\xff\xff\xff\x01\x00\x00\x00" + b"o" + exec_.encode("utf-8") + b"\x06\x09"
    for plan in planes:
        cuerpo += b"\x06\x0b\x00\x00\x00\xd7\x58" + plan + b"\x09\x0c"
    return cuerpo + b"\x0b"


def _sesion(*consultas) -> bytes:
    salida = io.BytesIO()
    with zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED) as comprimido:
        for numero, datos in enumerate(consultas, start=1):
            comprimido.writestr(f"{numero}.queryanalysis", datos)
        comprimido.writestr("meta.json", '{"Instance":"servidor\\\\instancia","Login":"DOMINIO\\\\usuario"}')
    return salida.getvalue()


class SesionDePlanExplorer(unittest.TestCase):
    def setUp(self):
        # En desorden a propósito: el plan unido las pone por StatementId.
        self.planes = [_plan("conversion_bit_2.sqlplan", 2), _plan("conversion_bit_1.sqlplan", 1),
                       _plan("conversion_bit_3.sqlplan", 3)]

    def test_se_reconoce_y_un_zip_comun_no(self):
        self.assertTrue(es_pesession("x.pesession", _sesion(_consulta(self.planes))))
        comun = io.BytesIO()
        with zipfile.ZipFile(comun, "w") as comprimido:
            comprimido.writestr("plan.sqlplan", self.planes[0])
        self.assertFalse(es_pesession("x.zip", comun.getvalue()))

    def test_un_plan_con_todas_las_sentencias_en_orden(self):
        unido = unir_planes(self.planes)
        self.assertEqual(re.findall(rb'StatementId="(\d+)"', unido), [b"1", b"2", b"3"])
        self.assertEqual(unido.count(b"<ShowPlanXML"), 1)
        resultado = analizar_lote([("PE CONCILIACION.PA_X.pesession", _sesion(_consulta(self.planes)))])
        self.assertEqual(resultado["totales"]["planes"], 1)
        self.assertEqual(resultado["totales"]["conError"], 0)
        plan = resultado["planes"][0]
        self.assertEqual(plan["procedimiento"], "Conciliacion.PA_PagosSeguros_Ins_X")  # del EXEC, no del archivo
        self.assertEqual(len(plan["analisis"]["diagrama"]), 3)
        self.assertEqual(plan["ruta"], "PE CONCILIACION.PA_X.pesession › consulta 1")

    def test_dentro_de_un_zip_y_repetida(self):
        sesion = _sesion(_consulta(self.planes))
        correo = io.BytesIO()
        with zipfile.ZipFile(correo, "w") as comprimido:
            comprimido.writestr("planes/sesion.pesession", sesion)
        extraccion = extraer_planes([("correo.zip", correo.getvalue()), ("copia.pesession", sesion)])
        self.assertEqual(len(extraccion.planes), 1)
        self.assertIn("Es el mismo plan", extraccion.ignorados[0].motivo)

    def test_varias_consultas_dan_varios_planes(self):
        sesion = _sesion(_consulta(self.planes[:1]), _consulta(self.planes[1:], "EXEC dbo.PA_Otro 1"))
        nombres = [p["procedimiento"] for p in analizar_lote([("s.pesession", sesion)])["planes"]]
        self.assertEqual(nombres, ["Conciliacion.PA_PagosSeguros_Ins_X (consulta 1)", "dbo.PA_Otro (consulta 2)"])

    def test_sin_planes_o_sin_exec(self):
        extraccion = extraer_planes([("vacia.pesession", _sesion(b"\x00\x01 sin planes"))])
        self.assertEqual(extraccion.planes, [])
        self.assertIn("no trae un plan", extraccion.ignorados[0].motivo)
        self.assertIsNone(nombre_del_procedimiento(b"SELECT 1"))
        self.assertEqual(nombre_del_procedimiento(b"oEXEC [dbo].[PA_Y] 1"), "dbo.PA_Y")

    def test_los_datos_de_conexion_no_salen(self):
        resultado = str(analizar_lote([("s.pesession", _sesion(_consulta(self.planes)))]))
        self.assertNotIn("DOMINIO", resultado)
        self.assertNotIn("instancia", resultado.lower().replace("consulta", ""))


if __name__ == "__main__":
    unittest.main()
