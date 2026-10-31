"""Negocio, variables sin uso (regla de la usuaria, 30 oct.): se observa solo la variable que se declara y
nunca más aparece. Si vuelve a aparecer (aunque solo reciba un valor con SET o SELECT), ya tiene uso.
"""

import re
import unittest

from app.analizadores.analizador_procedimientos_normales import verificar_procedimiento_normal

# Mismos patrones que el PA RRHH.PA_MemorandoDocPersona_Ins_DocumentoMemorando de la usuaria (reducido).
_MEMORANDO = """ALTER PROCEDURE RRHH.PA_Memorando_Ins_Documento
(
 @cPersCodUserMod VARCHAR(13),
 @nTipoVista INT,
 @cResult VARCHAR(1000) = '' OUTPUT
)
AS
BEGIN
 DECLARE @cResult2 VARCHAR(1000)= '';
 DECLARE @cUser2 VARCHAR(5)=''

  DECLARE
  @nTotal INT,
  @nCont INT = 1,
  @cPersCodMod VARCHAR(13),
  @NombreUser VARCHAR(10),
  @cNum  VARCHAR(6),
  @cNum2 VARCHAR(6)=''

  DECLARE @nID INT
  DECLARE @nID2 INT
  SELECT @cPersCodMod=RH.cPersCod,
         @NombreUser = RH.cUser
  FROM DBCMACICA.dbo.RRHH RH  WITH(NOLOCK)
  WHERE RH.cPersCod = @cPersCodUserMod

 DECLARE @cDocumento VARCHAR(1000),@cDocumento2 VARCHAR(1000)='', @cPersCodModDesc VARCHAR(250)

 SELECT TOP 1 @cPersCodModDesc = PU.cPersNombre FROM DBCMACICA.dbo.Persona PU WITH(NOLOCK)

 IF @nTipoVista=3
 BEGIN
 EXEC  RRHH.PA_Memorando_SelNumDoc @cPersCodUserMod, @cNum OUTPUT
 SET @cNum2= (select right(concat('000000',(cast(@cNum as int) + 1  )),6))
 END

 -- @nTotal solo aparece en este comentario: no cuenta
 SET @cDocumento = 'x' /* SELECT @nCont */
 INSERT INTO DBCMACICA.RRHH.MemorandoFirmas (nId, cPersCodMod, cDocumento) VALUES (@nID, @cPersCodMod, @cDocumento)
 EXEC RRHH.PA_Metas_Ins @nID, @cUser2, @cResult2 OUTPUT
 SET @cResult = @cResult2
END
"""


def _sin_uso(sql: str):
    return sorted({v for h in verificar_procedimiento_normal(sql) if h.regla == "VARIABLE_DECLARADA_SIN_USO"
                   for v in re.findall(r"@\w+", h.mensaje)})


def _pa(cuerpo: str) -> str:
    return f"CREATE PROCEDURE dbo.PA_Prueba_Sel_Datos\n@nP INT\nAS\nBEGIN\n{cuerpo}\nEND"


class TestVariablesSinUsoNegocio(unittest.TestCase):
    def test_caso_de_la_usuaria(self):
        # Solo las 4 que se declaran y nunca más aparecen (los comentarios no cuentan).
        self.assertEqual(_sin_uso(_MEMORANDO), ["@cDocumento2", "@nCont", "@nID2", "@nTotal"])

    def test_las_que_aparecen_mas_abajo_no_se_observan(self):
        observadas = _sin_uso(_MEMORANDO)
        for variable in ("@NombreUser", "@cNum2", "@cPersCodModDesc", "@cPersCodMod", "@cNum", "@nID",
                         "@cUser2", "@cResult2", "@cDocumento"):
            with self.subTest(variable=variable):
                self.assertNotIn(variable, observadas)

    def test_solo_declarada(self):
        self.assertEqual(_sin_uso(_pa("DECLARE @nTotal INT\nSELECT 1")), ["@nTotal"])
        self.assertEqual(_sin_uso(_pa("DECLARE @nTotal INT = 0, @nCont INT = 1\nSELECT @nCont")), ["@nTotal"])

    def test_solo_en_un_comentario_o_en_un_texto_no_cuenta(self):
        self.assertEqual(_sin_uso(_pa("DECLARE @nTotal INT\n-- SELECT @nTotal\nSELECT 1")), ["@nTotal"])
        self.assertEqual(_sin_uso(_pa("DECLARE @nTotal INT\n/* SET @nTotal = 1 */\nSELECT 1")), ["@nTotal"])
        self.assertEqual(_sin_uso(_pa("DECLARE @nTotal INT\nSELECT 'Total: @nTotal'")), ["@nTotal"])

    def test_nombre_parecido_no_cuenta(self):
        # @nTotal2 o @nTotalGeneral no son @nTotal.
        self.assertEqual(_sin_uso(_pa("DECLARE @nTotal INT, @nTotal2 INT\nSELECT @nTotal2")), ["@nTotal"])
        self.assertEqual(_sin_uso(_pa("DECLARE @nTotal INT, @nTotalGeneral INT\nSELECT @nTotalGeneral")), ["@nTotal"])

    def test_una_asignacion_ya_es_uso(self):
        for cuerpo in ("DECLARE @n INT\nSET @n = 5", "DECLARE @d DATE\nSELECT @d = MAX(dFecha) FROM dbo.Mov WITH(NOLOCK)",
                       "DECLARE @T TABLE (n INT)\nINSERT INTO @T (n) VALUES (1)",
                       "DECLARE @c VARCHAR(6)\nEXEC dbo.PA_Otro @c OUTPUT"):
            with self.subTest(cuerpo=cuerpo):
                self.assertEqual(_sin_uso(_pa(cuerpo)), [])

    def test_mensaje_en_plural_si_son_varias(self):
        from app.analizadores.analizador_reportes import verificar_reporte
        sql = _pa("DECLARE @nTotal INT, @nCont INT\nDECLARE @nID2 INT\nSELECT 1")
        esperados = {
            verificar_procedimiento_normal:
                "Se identificaron 3 variables que se declaran, pero no se usan: @nTotal, @nCont y @nID2. Se recomienda "
                "eliminarlas, ya que no cumplen ninguna función dentro del procedimiento.",
            verificar_reporte:
                "Se identificaron 3 variables que se declaran pero no se usan en el procedimiento: @nTotal, @nCont y "
                "@nID2. Se recomienda eliminarlas, ya que solo ocupan espacio y dificultan la lectura del código.",
        }
        for verificar, mensaje in esperados.items():
            with self.subTest(modulo=verificar.__name__):
                hallazgos = [h for h in verificar(sql) if h.regla == "VARIABLE_DECLARADA_SIN_USO"]
                self.assertEqual(len(hallazgos), 1)
                self.assertEqual(hallazgos[0].mensaje, mensaje)
                self.assertEqual(hallazgos[0].lineas, [5, 6])

    def test_mensaje_en_singular_si_es_una(self):
        from app.analizadores.analizador_reportes import verificar_reporte
        sql = _pa("DECLARE @nTotal INT\nSELECT 1")
        esperados = {
            verificar_procedimiento_normal:
                "La variable @nTotal se declara, pero no se usa. Se recomienda eliminarla, ya que no cumple ninguna "
                "función dentro del procedimiento.",
            verificar_reporte:
                "Se identificó que la variable @nTotal se declara pero no se usa en el procedimiento. Se recomienda "
                "eliminarla, ya que solo ocupa espacio y dificulta la lectura del código.",
        }
        for verificar, mensaje in esperados.items():
            with self.subTest(modulo=verificar.__name__):
                hallazgos = [h for h in verificar(sql) if h.regla == "VARIABLE_DECLARADA_SIN_USO"]
                self.assertEqual([h.mensaje for h in hallazgos], [mensaje])
                self.assertEqual(hallazgos[0].linea, 5)

    def test_dos_variables_dicen_y(self):
        sql = _pa("DECLARE @nTotal INT, @nCont INT\nSELECT 1")
        mensaje = [h.mensaje for h in verificar_procedimiento_normal(sql) if h.regla == "VARIABLE_DECLARADA_SIN_USO"][0]
        self.assertIn("Se identificaron 2 variables que se declaran, pero no se usan: @nTotal y @nCont.", mensaje)

    def test_mayusculas_distintas_es_la_misma_variable(self):
        self.assertEqual(_sin_uso(_pa("DECLARE @nTotal INT = 1\nSELECT @NTOTAL")), [])


if __name__ == "__main__":
    unittest.main()
