"""ORDER BY al insertar en una temporal o variable de tabla con IDENTITY (usuaria, 22 nov.).

Caso real: FluGenSol_InsPropuesta_SP llena #ValoresVivienda (nId INT IDENTITY) con ORDER BY y luego hace
UPDATE ... WHERE nId IN (1, 5, 9, ...). Comprobado en SQL Server Express (22 nov.): en temporales y variables de
tabla con IDENTITY la numeración sigue el ORDER BY, así que recomendar retirarlo rompe la lógica.
"""
import unittest

from app.analizadores.scriptdom import validar_estructura

_INSERT = "INSERT INTO {t} (a) SELECT a FROM dbo.T WITH (NOLOCK) ORDER BY a"


def _orden(sql):
    return [h for h in validar_estructura(sql) if h.regla == "ORDER_BY_EN_INSERT"]


class OrderByConIdentity(unittest.TestCase):
    def test_con_identity_no_se_observa(self):
        casos = {
            "temporal": "CREATE TABLE #V (nId INT IDENTITY(1, 1) PRIMARY KEY, a INT)\n" + _INSERT.format(t="#V"),
            "variable de tabla": "DECLARE @V TABLE (nId INT IDENTITY(1,1), a INT)\n" + _INSERT.format(t="@V"),
            "SELECT IDENTITY INTO": "SELECT IDENTITY(INT,1,1) AS nId, a INTO #V FROM dbo.T WITH (NOLOCK) WHERE 1 = 0\n"
                                    + _INSERT.format(t="#V"),
            "ALTER TABLE ADD": "CREATE TABLE #V (a INT)\nALTER TABLE #V ADD nId INT IDENTITY(1,1)\n" + _INSERT.format(t="#V"),
            "minúsculas": "create table #V (nId int identity, a int)\n" + _INSERT.format(t="#v").lower(),
            "desde la misma temporal": "CREATE TABLE #V (nId INT IDENTITY, a INT)\n"
                                       "INSERT INTO #V (a) SELECT a FROM #V ORDER BY a",
        }
        for nombre, sql in casos.items():
            with self.subTest(nombre):
                self.assertEqual(_orden(sql), [])

    def test_sin_identity_se_sigue_observando(self):
        hallazgo = _orden("CREATE TABLE #V (a INT)\n" + _INSERT.format(t="#V"))[0]
        self.assertEqual(hallazgo.mensaje, "Se identificó un ORDER BY al insertar datos con SELECT en la tabla #V. Se "
                                           "recomienda retirar el ORDER BY, ya que la tabla no conserva ese orden al "
                                           "consultarla.")

    def test_identity_en_otra_temporal_no_cuenta(self):
        sql = "CREATE TABLE #A (nId INT IDENTITY, a INT)\nCREATE TABLE #B (a INT)\nINSERT INTO #B (a) SELECT a FROM #A ORDER BY a"
        self.assertEqual([h.mensaje.split(" Se recomienda")[0] for h in _orden(sql)],
                         ["Se identificó un ORDER BY al insertar datos con SELECT en la tabla #B."])

    def test_temporal_no_creada_en_el_procedimiento_pide_validar(self):
        hallazgo = _orden(_INSERT.format(t="#V"))[0]
        self.assertTrue(hallazgo.mensaje.endswith(
            "En el caso de la tabla #V, cuya definición no está en el procedimiento, validar previamente que no tenga "
            "una columna IDENTITY, ya que en ese caso el ORDER BY define la numeración de los registros."), hallazgo.mensaje)

    def test_fisica_igual_que_antes(self):
        hallazgo = _orden(_INSERT.format(t="dbo.X"))[0]
        self.assertTrue(hallazgo.mensaje.endswith(
            "En el caso de la tabla física, validar previamente que no tenga una columna IDENTITY, ya que en ese caso "
            "el ORDER BY define la numeración de los registros."), hallazgo.mensaje)

    def test_caso_real_valores_vivienda(self):
        sql = ("CREATE TABLE #ValoresVivienda (nId INT IDENTITY(1, 1) PRIMARY KEY, nDestino INT, nMontoInicial MONEY,\n"
               " nMontoFinal MONEY, nRango INT)\n"
               "INSERT INTO #ValoresVivienda (nDestino, nMontoInicial, nMontoFinal)\n"
               "SELECT Destino, MontoInicial, MontoFinal FROM DBO.ColocConfigBonoHipotecario WITH(NOLOCK)\n"
               "WHERE Estado = 1 AND SubProducto = 406 AND TIPOBONO = 2 ORDER BY Destino, MontoInicial ASC\n"
               "INSERT INTO #ValoresVivienda (nDestino, nMontoInicial, nMontoFinal)\n"
               "SELECT 28, nMontoInicial, nMontoFinal FROM #ValoresVivienda WHERE nDestino = 6 ORDER BY nMontoInicial\n"
               "UPDATE p SET nRango = 1 FROM #ValoresVivienda p WHERE nId IN (1, 5, 9, 13, 17, 21)")
        self.assertEqual(_orden(sql), [])


if __name__ == "__main__":
    unittest.main()
