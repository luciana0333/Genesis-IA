# -*- coding: utf-8 -*-
"""Revisión de planes por lote: sueltos, .zip con carpetas, .rar, repetidos, dañados y archivos que no son planes."""

import io
import struct
import unittest
import zipfile
import zlib
from pathlib import Path

from app.analizadores.planes_ejecucion.lote import (
    _tar_de_windows,
    analizar_lote,
    es_plan,
    extraer_planes,
    nombre_procedimiento,
)
from app.analizadores.planes_ejecucion.servicio import analizar_plan_completo

EJEMPLOS = Path(__file__).resolve().parents[2] / "frontend" / "public" / "ejemplos"
NEGOCIO = (EJEMPLOS / "plan-ejemplo-negocio.sqlplan").read_bytes()
REPORTES = (EJEMPLOS / "plan-ejemplo-reportes.sqlplan").read_bytes()

PLAN_CON_PROCEDIMIENTO = b"""<?xml version="1.0" encoding="utf-8"?>
<ShowPlanXML xmlns="http://schemas.microsoft.com/sqlserver/2004/07/showplan" Version="1.5">
  <BatchSequence><Batch><Statements>
    <StmtSimple StatementId="1" StatementText="EXEC [dbo].[PA_ConsultarCliente] @nIdCliente = 1" StatementType="EXECUTE PROC">
      <StoredProc ProcName="[dbo].[PA_ConsultarCliente]" />
    </StmtSimple>
  </Statements></Batch></BatchSequence>
</ShowPlanXML>"""


def _rar(archivos):
    """Un .rar (formato 4, sin compresión) armado a mano: bsdtar lo abre pero no sabe crearlos."""
    def bloque(tipo, banderas, cuerpo):
        sin_crc = struct.pack("<BHH", tipo, banderas, 7 + len(cuerpo)) + cuerpo
        return struct.pack("<H", zlib.crc32(sin_crc) & 0xFFFF) + sin_crc

    salida = b"Rar!\x1a\x07\x00" + bloque(0x73, 0, b"\x00" * 6)
    for nombre, datos in archivos:
        ruta = nombre.replace("/", "\\").encode()
        cabecera = struct.pack("<IIBIIBBHI", len(datos), len(datos), 2, zlib.crc32(datos), 0x21000000,
                               20, 0x30, len(ruta), 0x20) + ruta
        salida += bloque(0x74, 0x8000, cabecera) + datos
    return salida + bloque(0x7B, 0x4000, b"")


def _zip(archivos):
    memoria = io.BytesIO()
    with zipfile.ZipFile(memoria, "w") as comprimido:
        for nombre, contenido in archivos:
            comprimido.writestr(nombre, contenido)
    return memoria.getvalue()


class PruebasLote(unittest.TestCase):
    def test_reconoce_plan_por_su_contenido_en_utf8_y_utf16(self):
        self.assertTrue(es_plan(NEGOCIO))
        self.assertTrue(es_plan(NEGOCIO.decode("utf-8").encode("utf-16")))
        self.assertFalse(es_plan(b"SELECT 1"))

    def test_planes_sueltos_con_cualquier_extension(self):
        lote = analizar_lote([("a.sqlplan", NEGOCIO), ("b.xml", REPORTES)])
        self.assertEqual([p["archivo"] for p in lote["planes"]], ["a.sqlplan", "b.xml"])
        self.assertEqual(lote["totales"]["planes"], 2)
        self.assertEqual(lote["ignorados"], [])

    def test_cada_plan_trae_el_mismo_analisis_que_un_plan_suelto(self):
        lote = analizar_lote([("a.sqlplan", NEGOCIO)], "negocio", 2)
        suelto = analizar_plan_completo("a.sqlplan", NEGOCIO, "negocio", 2)
        self.assertEqual(lote["planes"][0]["analisis"], suelto)
        self.assertEqual(lote["planes"][0]["resumen"], suelto["resumen"])

    def test_zip_con_carpetas_y_archivos_que_no_son_planes(self):
        comprimido = _zip([
            ("Reportes/uno.sqlplan", NEGOCIO),
            ("Reportes/sub/dos.sqlplan", REPORTES),
            ("leeme.txt", b"hola"),
            ("__MACOSX/._uno.sqlplan", b"basura"),
        ])
        extraccion = extraer_planes([("Planes.zip", comprimido)])
        self.assertEqual([p.ruta for p in extraccion.planes],
                         ["Planes.zip › Reportes/uno.sqlplan", "Planes.zip › Reportes/sub/dos.sqlplan"])
        self.assertEqual([i.ruta for i in extraccion.ignorados], ["Planes.zip › leeme.txt"])
        self.assertIn("No es un plan", extraccion.ignorados[0].motivo)

    def test_zip_dentro_de_zip(self):
        interno = _zip([("uno.sqlplan", NEGOCIO)])
        extraccion = extraer_planes([("externo.zip", _zip([("interno.zip", interno)]))])
        self.assertEqual(len(extraccion.planes), 1)

    def test_planes_repetidos_se_revisan_una_vez(self):
        extraccion = extraer_planes([("a.sqlplan", NEGOCIO), ("copia.sqlplan", NEGOCIO)])
        self.assertEqual(len(extraccion.planes), 1)
        self.assertIn("mismo plan que a.sqlplan", extraccion.ignorados[0].motivo)

    def test_zip_danado(self):
        extraccion = extraer_planes([("roto.zip", b"PK\x03\x04no es zip")])
        self.assertEqual(extraccion.planes, [])
        self.assertIn("dañado", extraccion.ignorados[0].motivo)

    def test_plan_danado_no_detiene_a_los_demas(self):
        roto = NEGOCIO[: len(NEGOCIO) // 2]
        lote = analizar_lote([("roto.sqlplan", roto), ("bueno.sqlplan", REPORTES)])
        self.assertIn("error", lote["planes"][0])
        self.assertNotIn("error", lote["planes"][1])
        self.assertEqual(lote["totales"]["conError"], 1)
        self.assertEqual(lote["totales"]["planes"], 1)

    def test_nombre_del_procedimiento(self):
        self.assertEqual(nombre_procedimiento(PLAN_CON_PROCEDIMIENTO, "x.sqlplan"), "dbo.PA_ConsultarCliente")
        self.assertEqual(nombre_procedimiento(b"<roto", "Carpeta/PA_Prueba.sqlplan"), "PA_Prueba")

    def test_supera_limite_suma_las_sentencias(self):
        lote = analizar_lote([("a.sqlplan", NEGOCIO)], "negocio", 0.000001)
        plan = lote["planes"][0]
        if plan["duracionMs"]:
            self.assertTrue(plan["superaLimite"])
            self.assertEqual(lote["totales"]["superanLimite"], 1)
        sin_limite = analizar_lote([("a.sqlplan", NEGOCIO)], "negocio", None)
        self.assertFalse(sin_limite["planes"][0]["superaLimite"])

    @unittest.skipUnless(_tar_de_windows(), "Esta computadora no tiene el tar de Windows (bsdtar)")
    def test_rar_con_carpetas(self):
        contenido = _rar([("Negocio/uno.sqlplan", NEGOCIO), ("Negocio/dos.sqlplan", REPORTES), ("nota.txt", b"hola")])
        extraccion = extraer_planes([("lote.rar", contenido)])
        self.assertEqual([p.ruta for p in extraccion.planes],
                         ["lote.rar › Negocio/dos.sqlplan", "lote.rar › Negocio/uno.sqlplan"])
        self.assertEqual([i.ruta for i in extraccion.ignorados], ["lote.rar › nota.txt"])

    def test_rar_que_no_se_puede_abrir_avisa_como_extraerlo(self):
        extraccion = extraer_planes([("roto.rar", b"Rar!\x1a\x07\x00basura")])
        self.assertEqual(extraccion.planes, [])
        self.assertIn("Extraer todo", extraccion.ignorados[0].motivo)


if __name__ == "__main__":
    unittest.main()
