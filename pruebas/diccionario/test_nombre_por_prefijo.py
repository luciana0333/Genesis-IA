"""Columna o parámetro documentado con el prefijo de tipo equivocado (caso de la usuaria, 7 nov.).

El diccionario documenta cFechaRegularizacion (no existe) y la tabla tiene dFechaRegularizacion sin documentar:
una sola observación crítica que dice a cuál parece referirse. Solo si coincide el esquema, el objeto y el nombre
salvo el prefijo; lo demás sigue como «no documentada» / «no existe» (que también hace fallar el script: crítico).
"""

import unittest

from app.analizadores.analizador_diccionario_procedimientos import verificar_diccionario
from app.analizadores.analizador_diccionario_tablas import verificar_diccionario_tablas
from app.analizadores.nombre_por_prefijo import emparejar_por_prefijo, sin_prefijo

TABLA = ("CREATE TABLE COLOCACIONES.ConstRegularizacionDeudaDet (\n"
         "  nConstRegularizacionDeudaDetId INT IDENTITY(1,1),\n"
         "  nSolicitudEmisionDocumentoCredId INT NOT NULL,\n"
         "  dFechaRegularizacion DATE NOT NULL,\n"
         "  CONSTRAINT PK_ConstRegularizacionDeudaDet PRIMARY KEY CLUSTERED (nConstRegularizacionDeudaDetId)\n);")


def _columna(columna, valor, esquema="COLOCACIONES"):
    return (f"EXEC sys.sp_addextendedproperty @name=N'MS_Description', @value=N'{valor}', "
            f"@level0type=N'SCHEMA', @level0name=N'{esquema}', @level1type=N'TABLE', "
            f"@level1name=N'ConstRegularizacionDeudaDet', @level2type=N'COLUMN', @level2name=N'{columna}'\n")


DICCIONARIO = (
    "EXEC sys.sp_addextendedproperty @name=N'MS_Description', @value=N'Tabla de constancias', "
    "@level0type=N'SCHEMA', @level0name=N'COLOCACIONES', @level1type=N'TABLE', "
    "@level1name=N'ConstRegularizacionDeudaDet'\n"
    + _columna("nConstRegularizacionDeudaDetId", "Identificador de la tabla")
    + _columna("nConstRegularizacionDeudaId", "Numero de la constancia emitida")
    + _columna("cFechaRegularizacion", "Fecha en que se regulariza la deuda")
)


class PrefijoTest(unittest.TestCase):
    def test_sin_prefijo(self):
        self.assertEqual(sin_prefijo("cFechaRegularizacion"), "fecharegularizacion")
        self.assertEqual(sin_prefijo("@nCodAge"), "codage")
        self.assertEqual(sin_prefijo("[dFecha]"), "fecha")

    def test_solo_empareja_si_solo_cambia_el_prefijo(self):
        self.assertEqual(
            emparejar_por_prefijo(["cFechaRegularizacion", "nConstRegularizacionDeudaId"],
                                  ["dFechaRegularizacion", "nSolicitudEmisionDocumentoCredId"]),
            {"cFechaRegularizacion": "dFechaRegularizacion"},
        )
        # Dos candidatas posibles: no es seguro, no se empareja.
        self.assertEqual(emparejar_por_prefijo(["cFecha"], ["dFecha", "nFecha"]), {})


class TablasTest(unittest.TestCase):
    def setUp(self):
        self.hallazgos = {h.regla: h for h in verificar_diccionario_tablas(TABLA, DICCIONARIO)}

    def test_prefijo_distinto_es_una_sola_observacion_critica(self):
        hallazgo = self.hallazgos["COLUMNA_NOMBRE_INCORRECTO"]
        self.assertEqual(hallazgo.severidad.value, "critico")
        self.assertEqual(
            hallazgo.mensaje,
            "Se identificó que en el diccionario se documenta la columna cFechaRegularizacion, que no existe en la "
            "tabla COLOCACIONES.ConstRegularizacionDeudaDet, pero parece referirse a dFechaRegularizacion. Corregir "
            "el nombre de la columna en el diccionario (ej.: @level2name = N'dFechaRegularizacion'), ya que SQL "
            "Server no encuentra la columna y el script del diccionario falla.",
        )

    def test_lo_demas_queda_separado_y_dice_de_que_tabla_es(self):
        # nConstRegularizacionDeudaId y nSolicitudEmisionDocumentoCredId no se parecen: no se emparejan.
        no_existe = self.hallazgos["COLUMNA_NO_EXISTE"]
        self.assertEqual(no_existe.severidad.value, "critico")
        self.assertIn("la columna nConstRegularizacionDeudaId está documentada, pero no existe en la tabla "
                      "COLOCACIONES.ConstRegularizacionDeudaDet.", no_existe.mensaje)
        self.assertNotIn("quiso decir", no_existe.mensaje)  # la ...DetId ya está documentada: no se propone
        faltante = self.hallazgos["COLUMNA_FALTANTE"]
        self.assertIn("La columna nSolicitudEmisionDocumentoCredId de la tabla COLOCACIONES.ConstRegularizacionDeudaDet "
                      "no se encuentra documentada", faltante.mensaje)
        self.assertNotIn("dFechaRegularizacion", faltante.mensaje)  # ya está en la observación de nombre incorrecto

    def test_otro_esquema_no_se_empareja(self):
        diccionario = DICCIONARIO.replace(
            _columna("cFechaRegularizacion", "Fecha en que se regulariza la deuda"),
            _columna("cFechaRegularizacion", "Fecha en que se regulariza la deuda", esquema="dbo"))
        reglas = {h.regla for h in verificar_diccionario_tablas(TABLA, diccionario)}
        self.assertNotIn("COLUMNA_NOMBRE_INCORRECTO", reglas)


class ProcedimientosTest(unittest.TestCase):
    def test_parametro_con_otro_prefijo(self):
        sql = "CREATE PROCEDURE Colocaciones.PA_Credito_Sel_Datos (@nCodAge INT, @cCtaCod VARCHAR(18))"

        def _exec(valor, parametro=None):
            nivel2 = f", @level2type=N'PARAMETER', @level2name=N'{parametro}'" if parametro else ""
            return (f"EXEC sys.sp_addextendedproperty @name=N'MS_Description', @value=N'{valor}', "
                    f"@level0type=N'SCHEMA', @level0name=N'Colocaciones', @level1type=N'PROCEDURE', "
                    f"@level1name=N'PA_Credito_Sel_Datos'{nivel2}\n")

        dic = (_exec("Procedimiento que obtiene los datos del credito")
               + _exec("Codigo de la agencia", "@cCodAge") + _exec("Codigo de la cuenta", "@cCtaCod"))
        hallazgos = {h.regla: h for h in verificar_diccionario(sql, dic)}
        hallazgo = hallazgos["PARAMETRO_NOMBRE_INCORRECTO"]
        self.assertEqual(hallazgo.severidad.value, "critico")
        self.assertIn("se documenta el parámetro @cCodAge, que no existe en el procedimiento "
                      "Colocaciones.PA_Credito_Sel_Datos, pero parece referirse a @nCodAge.", hallazgo.mensaje)
        self.assertNotIn("PARAMETRO_FALTANTE", hallazgos)
        self.assertNotIn("PARAMETRO_NO_EXISTE", hallazgos)


class TipoNivel2MalEscritoTest(unittest.TestCase):
    """@level2type con otro valor (el nombre copiado) en vez de COLUMN / PARAMETER: SQL Server lo rechaza."""

    def test_tabla_columna_que_existe(self):
        # La columna existe y está documentada, pero con el tipo mal escrito: se observa el tipo.
        diccionario = DICCIONARIO.replace(
            "@level2type=N'COLUMN', @level2name=N'nConstRegularizacionDeudaDetId'",
            "@level2type=N'nConstRegularizacionDeudaDetId', @level2name=N'nConstRegularizacionDeudaDetId'")
        hallazgos = verificar_diccionario_tablas(TABLA, diccionario)
        tipo = [h for h in hallazgos if h.regla == "TIPO_NIVEL_INCORRECTO"]
        self.assertEqual(len(tipo), 1)
        self.assertIn("indica 'nConstRegularizacionDeudaDetId' como tipo de la columna (@level2type), pero debe ser "
                      "'COLUMN'", tipo[0].mensaje)
        # Cuenta como documentada: no se repite como «no documentada».
        self.assertFalse(any("nConstRegularizacionDeudaDetId" in h.mensaje
                             for h in hallazgos if h.regla == "COLUMNA_FALTANTE"))

    def test_tabla_columna_que_no_existe_solo_dice_eso(self):
        # Pedido de la usuaria: si la columna no existe, basta con eso (no además el tipo).
        diccionario = DICCIONARIO.replace(
            "@level2type=N'COLUMN', @level2name=N'nConstRegularizacionDeudaId'",
            "@level2type=N'nConstRegularizacionDeudaId', @level2name=N'nConstRegularizacionDeudaId'")
        reglas = [h.regla for h in verificar_diccionario_tablas(TABLA, diccionario)]
        self.assertIn("COLUMNA_NO_EXISTE", reglas)
        self.assertNotIn("TIPO_NIVEL_INCORRECTO", reglas)

    def test_procedimiento_parametro_que_no_existe_solo_dice_eso(self):
        sql = "CREATE PROCEDURE Colocaciones.PA_Credito_Sel_Datos (@nCodAge INT)"
        base = ("EXEC sys.sp_addextendedproperty @name=N'MS_Description', @value=N'{}', @level0type=N'SCHEMA', "
                "@level0name=N'Colocaciones', @level1type=N'PROCEDURE', @level1name=N'PA_Credito_Sel_Datos'{}\n")
        dic = (base.format("Procedimiento que obtiene los datos del credito", "")
               + base.format("Codigo de la agencia", ", @level2type=N'@cCodAgencia', @level2name=N'@cCodAgencia'"))
        reglas = [h.regla for h in verificar_diccionario(sql, dic)]
        self.assertIn("PARAMETRO_NO_EXISTE", reglas)
        self.assertNotIn("TIPO_NIVEL_INCORRECTO", reglas)

    def test_procedimiento(self):
        sql = "CREATE PROCEDURE Colocaciones.PA_Credito_Sel_Datos (@nCodAge INT)"
        base = ("EXEC sys.sp_addextendedproperty @name=N'MS_Description', @value=N'{}', @level0type=N'SCHEMA', "
                "@level0name=N'Colocaciones', @level1type=N'PROCEDURE', @level1name=N'PA_Credito_Sel_Datos'{}\n")
        dic = (base.format("Procedimiento que obtiene los datos del credito", "")
               + base.format("Codigo de la agencia", ", @level2type=N'@nCodAge', @level2name=N'@nCodAge'"))
        hallazgos = verificar_diccionario(sql, dic)
        self.assertEqual([h.regla for h in hallazgos], ["TIPO_NIVEL_INCORRECTO"])
        self.assertIn("debe ser 'PARAMETER'", hallazgos[0].mensaje)


if __name__ == "__main__":
    unittest.main()
