"""Script con varias tablas: más de 3 casos de una regla de columnas se muestran en tabla (usuaria, 25 nov.).

Caso real: el script de Conciliación con 11 tablas («Columna sin NOT NULL ni DEFAULT» con 57 columnas, «Columna no
documentada» con 128 y «Tabla no documentada» 11 veces) salía en párrafos larguísimos.
"""
import unittest

from app.analizadores.analizador_diccionario_tablas import verificar_diccionario_tablas
from app.analizadores.analizador_tablas import verificar_tabla


def _tabla(nombre: str) -> str:
    return (f"CREATE TABLE Conciliacion.{nombre}\n(\n\tn{nombre}Id INT IDENTITY(1,1) NOT NULL,\n"
            f"\tnMonto MONEY,\n\tcCodigo VARCHAR(6) COLLATE SQL_Latin1_General_CP1_CI_AS,\n"
            f"\tCONSTRAINT PK_{nombre} PRIMARY KEY CLUSTERED (n{nombre}Id)\n);\n")


def _script(cantidad: int) -> str:
    return "".join(_tabla(nombre) for nombre in ["Pagos", "Saldos", "Tramas", "Cuentas", "Cargos"][:cantidad])


def _regla(hallazgos, regla):
    return next(h for h in hallazgos if h.regla == regla)


class VariasTablasEnTabla(unittest.TestCase):
    def test_mas_de_tres_casos_van_en_tabla_por_tabla(self):
        nulos = _regla(verificar_tabla(_script(4)), "COLUMNA_SIN_NOT_NULL_NI_DEFAULT")
        self.assertEqual([g["nombre"] for g in nulos.grupos],
                         ["Conciliacion.Pagos", "Conciliacion.Saldos", "Conciliacion.Tramas", "Conciliacion.Cuentas"])
        self.assertEqual(nulos.grupos[0]["etiquetas"], ["nMonto", "cCodigo"])
        self.assertTrue(nulos.grupos[0]["enCajitas"])
        self.assertEqual(nulos.grupos[0]["tituloDetalle"], "Columnas")
        # El texto copiado sigue siendo la lista.
        self.assertTrue(nulos.mensaje.startswith("Se identificaron ocho columnas que aceptan valores nulos: "))

    def test_hasta_tres_casos_sigue_como_texto(self):
        script = _tabla("Pagos").replace("\tcCodigo VARCHAR(6) COLLATE SQL_Latin1_General_CP1_CI_AS,\n", "") \
            + _tabla("Saldos").replace("\tcCodigo VARCHAR(6) COLLATE SQL_Latin1_General_CP1_CI_AS,\n", "")
        nulos = _regla(verificar_tabla(script), "COLUMNA_SIN_NOT_NULL_NI_DEFAULT")
        self.assertIsNone(getattr(nulos, "grupos", None))

    def test_diccionario_columnas_y_tablas_sin_documentar(self):
        hallazgos = verificar_diccionario_tablas(_script(5), "")
        faltantes = _regla(hallazgos, "COLUMNA_FALTANTE")
        self.assertEqual(len(faltantes.grupos), 5)
        self.assertTrue(all(g["enCajitas"] for g in faltantes.grupos))
        tablas = [h for h in hallazgos if h.regla == "TABLA_SIN_DESCRIPCION"]
        self.assertEqual(len(tablas), 1)  # una sola observación, sin repetir la frase en cada tabla
        self.assertTrue(tablas[0].mensaje.startswith(
            "Se identificaron 5 tablas que no se encuentran documentadas: Conciliacion.Pagos; Conciliacion.Saldos; "))
        self.assertNotIn("observaciones de este tipo", tablas[0].mensaje)


if __name__ == "__main__":
    unittest.main()


class NombreDeColumnaMalEscrito(unittest.TestCase):
    """dFechaResgistro y cTipoModena del script de Conciliación (usuaria, 25 nov.)."""

    def _mal_escritas(self, columnas: str):
        script = (f"CREATE TABLE Conciliacion.Pagos\n(\n\tnPagosId INT IDENTITY(1,1) NOT NULL,\n{columnas}"
                  f"\tCONSTRAINT PK_Pagos PRIMARY KEY CLUSTERED (nPagosId)\n);\n")
        return [h for h in verificar_tabla(script) if h.regla == "COLUMNA_NOMBRE_MAL_ESCRITO"]

    def test_casos_reales(self):
        hallazgos = self._mal_escritas("\tdFechaResgistro DATETIME NOT NULL,\n\tcTipoModena VARCHAR(1) COLLATE "
                                       "SQL_Latin1_General_CP1_CI_AS NOT NULL,\n")
        self.assertEqual(len(hallazgos), 1)
        self.assertIn("dFechaResgistro → dFechaRegistro", hallazgos[0].mensaje)
        self.assertIn("cTipoModena → cTipoMoneda", hallazgos[0].mensaje)  # dos letras cambiadas, no «Moderna»

    def test_abreviaturas_y_terminos_de_la_caja_no_se_marcan(self):
        self.assertEqual(self._mal_escritas(
            "\tcCtaContCod VARCHAR(26) COLLATE SQL_Latin1_General_CP1_CI_AS NOT NULL,\n"
            "\tnCuentasAperturadas INT NOT NULL,\n\tnPercapita MONEY NOT NULL,\n"
            "\tnIntentosReproceso INT NOT NULL,\n"), [])


class FechaComoTexto(unittest.TestCase):
    """cFechaProceso VARCHAR(8) de PagosSeguros (usuaria, 25 nov.); el periodo como texto no cuenta."""

    def _fechas(self, columnas: str):
        script = (f"CREATE TABLE Conciliacion.Pagos\n(\n\tnPagosId INT IDENTITY(1,1) NOT NULL,\n{columnas}"
                  f"\tCONSTRAINT PK_Pagos PRIMARY KEY CLUSTERED (nPagosId)\n);\n")
        return [h for h in verificar_tabla(script) if h.regla == "COLUMNA_FECHA_COMO_TEXTO"]

    def test_caso_real(self):
        hallazgos = self._fechas("\tcFechaProceso VARCHAR(8) COLLATE SQL_Latin1_General_CP1_CI_AS NOT NULL,\n")
        self.assertEqual(len(hallazgos), 1)
        self.assertEqual(hallazgos[0].severidad.value.lower(), "bajo")
        self.assertEqual(hallazgos[0].mensaje, "Se identificó que la columna cFechaProceso almacena fechas, pero "
                                               "está definida como VARCHAR(8). Se recomienda evaluar su cambio a DATE.")

    def test_no_se_marca(self):
        self.assertEqual(self._fechas(
            "\tcPeriodo VARCHAR(6) COLLATE SQL_Latin1_General_CP1_CI_AS NOT NULL,\n\tdFechaPago DATE NOT NULL,\n"
            "\tdFechaRegistro DATETIME NOT NULL,\n"), [])
