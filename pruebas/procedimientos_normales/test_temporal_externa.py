"""«Tabla temporal externa» (usuaria, 13 nov.), en Reportes y Negocio.

Una temporal local que crea el PA que lo llama y cuya creación está documentada en el encabezado es una tabla
externa (bajo). Sin esa documentación sigue siendo «Tabla temporal usada sin crear» (crítico).
"""

import unittest

from app.analizadores.analizador_procedimientos_normales import verificar_procedimiento_normal
from app.analizadores.analizador_reportes import verificar_reporte

MODULOS = (verificar_reporte, verificar_procedimiento_normal)

# Caso de la usuaria: PA_RHConceptoTabla_Sel_ConceptosBoletaMasivo, con #Personas en la sección «Pruebas».
_ENCABEZADO = """/******************************************************************************
' Nombre del PA       : PA_RHConceptoTabla_Sel_ConceptosBoletaMasivo
' Descripción         : Lista los conceptos de la boleta para múltiples colaboradores.
' Autor / Fecha       : LGQL / 2026-11-04
Pruebas:
-- Crear tabla temporal de colaboradores
CREATE TABLE #Personas (
    cPersCod VARCHAR(13) COLLATE SQL_Latin1_General_CP1_CI_AS
)
INSERT INTO #Personas (cPersCod) VALUES ('1080100000213')
EXEC PA_RHConceptoTabla_Sel_ConceptosBoletaMasivo '202301'
DROP TABLE #Personas
******************************************************************************/
"""
_CUERPO = """ALTER PROCEDURE dbo.PA_RHConceptoTabla_Sel_ConceptosBoletaMasivo
(
 @cPeriodo varchar(6)
)
AS
BEGIN
 SET NOCOUNT ON;
 SELECT P.cPersCod FROM #Personas P;
 SELECT 1 WHERE EXISTS (SELECT 1 FROM #Personas X);
END"""


def _reglas(sql, verificar):
    return {h.regla: h for h in verificar(sql) if h.regla in ("TEMPORAL_EXTERNA", "TEMPORAL_SIN_CREAR")}


class TemporalExternaTest(unittest.TestCase):
    def test_caso_de_la_usuaria(self):
        for verificar in MODULOS:
            with self.subTest(modulo=verificar.__name__):
                reglas = _reglas(_ENCABEZADO + _CUERPO, verificar)
                self.assertEqual(list(reglas), ["TEMPORAL_EXTERNA"])
                hallazgo = reglas["TEMPORAL_EXTERNA"]
                self.assertEqual(hallazgo.severidad.value, "bajo")
                self.assertEqual(hallazgo.lineas, [21, 22])
                # Lo encontrado ocupa dos oraciones: la pantalla corta el «Qué hacer» donde indica la regla.
                self.assertEqual(hallazgo.mensaje[hallazgo.inicio_que_hacer:][:22], "Se recomienda verifica")
                self.assertEqual(
                    hallazgo.mensaje,
                    "Se identificó que la tabla temporal #Personas no se crea en este procedimiento. Según lo "
                    "indicado en el encabezado, esta es creada por otro procedimiento que se ejecuta previamente. Se "
                    "recomienda verificar que dicho procedimiento cree la tabla #Personas antes de ejecutar este "
                    "procedimiento, para evitar errores al intentar utilizarla.",
                )

    def test_sin_documentar_sigue_siendo_critico(self):
        for verificar in MODULOS:
            with self.subTest(modulo=verificar.__name__):
                reglas = _reglas(_CUERPO, verificar)
                self.assertEqual(list(reglas), ["TEMPORAL_SIN_CREAR"])
                self.assertEqual(reglas["TEMPORAL_SIN_CREAR"].severidad.value, "critico")

    def test_otras_formas_de_documentarla(self):
        casos = {
            "SELECT … INTO en el encabezado": _ENCABEZADO.replace(
                "CREATE TABLE #Personas (\n    cPersCod VARCHAR(13) COLLATE SQL_Latin1_General_CP1_CI_AS\n)",
                "SELECT cPersCod INTO #Personas FROM dbo.Persona"),
            "comentario de línea": "-- Prueba: CREATE TABLE #Personas (cPersCod VARCHAR(13))\n",
            "mayúsculas distintas y corchetes": _ENCABEZADO.replace("#Personas (", "#PERSONAS ("),
        }
        for nombre, encabezado in casos.items():
            for verificar in MODULOS:
                with self.subTest(caso=nombre, modulo=verificar.__name__):
                    self.assertEqual(list(_reglas(encabezado + _CUERPO.replace("FROM #Personas P", "FROM [#Personas] P"),
                                                  verificar)), ["TEMPORAL_EXTERNA"])

    def test_documentada_despues_del_as_tambien_cuenta(self):
        cuerpo = _CUERPO.replace(" SET NOCOUNT ON;", " /* Prueba: CREATE TABLE #Personas (cPersCod VARCHAR(13)) */\n"
                                                      " SET NOCOUNT ON;")
        for verificar in MODULOS:
            with self.subTest(modulo=verificar.__name__):
                self.assertEqual(list(_reglas(cuerpo, verificar)), ["TEMPORAL_EXTERNA"])

    def test_lo_que_no_es_documentar_su_creacion(self):
        casos = {
            # Un CREATE comentado en el cuerpo es código viejo, no documentación del encabezado.
            "CREATE comentado en el cuerpo": _CUERPO.replace(
                " SELECT P.cPersCod", " -- CREATE TABLE #Personas (cPersCod VARCHAR(13))\n SELECT P.cPersCod"),
            # Nombrarla o llenarla en el encabezado no es crearla.
            "solo la nombra": "/* Usa la tabla #Personas que llena el PA que lo llama */\n" + _CUERPO,
            "solo INSERT INTO": "/* INSERT INTO #Personas (cPersCod) VALUES ('1') */\n" + _CUERPO,
            # Otra temporal documentada no cubre a esta.
            "documenta otra": _ENCABEZADO.replace("#Personas (", "#Agencias (") + _CUERPO,
        }
        for nombre, sql in casos.items():
            for verificar in MODULOS:
                with self.subTest(caso=nombre, modulo=verificar.__name__):
                    self.assertEqual(list(_reglas(sql, verificar)), ["TEMPORAL_SIN_CREAR"])

    def test_una_documentada_y_otra_no(self):
        cuerpo = _CUERPO.replace(" SELECT 1 WHERE", " SELECT * FROM #Agencias;\n SELECT 1 WHERE")
        for verificar in MODULOS:
            with self.subTest(modulo=verificar.__name__):
                reglas = _reglas(_ENCABEZADO + cuerpo, verificar)
                self.assertIn("#Personas", reglas["TEMPORAL_EXTERNA"].mensaje)
                self.assertNotIn("#Agencias", reglas["TEMPORAL_EXTERNA"].mensaje)
                self.assertIn("#Agencias", reglas["TEMPORAL_SIN_CREAR"].mensaje)
                self.assertNotIn("#Personas", reglas["TEMPORAL_SIN_CREAR"].mensaje)

    def test_dos_externas_en_plural(self):
        encabezado = _ENCABEZADO.replace("DROP TABLE #Personas", "CREATE TABLE #Agencias (cAgeCod VARCHAR(2))")
        cuerpo = _CUERPO.replace(" SELECT 1 WHERE", " SELECT * FROM #Agencias;\n SELECT 1 WHERE")
        mensaje = _reglas(encabezado + cuerpo, verificar_procedimiento_normal)["TEMPORAL_EXTERNA"].mensaje
        self.assertEqual(
            mensaje,
            "Se identificó que las tablas temporales #Personas y #Agencias no se crean en este procedimiento. Según "
            "lo indicado en el encabezado, estas son creadas por otro procedimiento que se ejecuta previamente. Se "
            "recomienda verificar que dicho procedimiento cree las tablas #Personas y #Agencias antes de ejecutar "
            "este procedimiento, para evitar errores al intentar utilizarlas.",
        )

    def test_si_la_crea_el_propio_procedimiento_no_se_marca(self):
        cuerpo = _CUERPO.replace(" SET NOCOUNT ON;", " SET NOCOUNT ON;\n CREATE TABLE #Personas (cPersCod VARCHAR(13));")
        for verificar in MODULOS:
            with self.subTest(modulo=verificar.__name__):
                self.assertEqual(_reglas(_ENCABEZADO + cuerpo, verificar), {})


if __name__ == "__main__":
    unittest.main()
