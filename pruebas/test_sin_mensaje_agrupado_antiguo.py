"""Ninguna regla muestra el mensaje agrupado antiguo (usuaria, 22 nov.: «que ni una regla muestre el mismo mensaje
antiguo»).

Barrido: se toman todos los SQL de las pruebas, y para cada regla se juntan dos casos distintos que la disparan. El
mensaje agrupado no puede ser «Se encontraron N observaciones de este tipo: …» (la frase repetida en cada caso).
Si una regla nueva cae en ese texto, esta prueba falla: hay que darle su texto agrupado (Plantilla).
"""

import ast
import itertools
import re
import unittest
from collections import defaultdict
from pathlib import Path

from app.analizadores.analizador_procedimientos_normales import verificar_procedimiento_normal
from app.analizadores.analizador_reportes import verificar_reporte

_SQL = re.compile(r"\b(SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|DECLARE|EXEC|MERGE|WHILE|GOTO|WAITFOR|RAISERROR)\b", re.I)
_ANTIGUO = re.compile(r"Se encontraron \d+ observaciones de este tipo")
_CASOS_POR_REGLA = 4


def _fragmentos():
    encontrados = set()
    for archivo in Path(__file__).parent.rglob("*.py"):
        try:
            arbol = ast.parse(archivo.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str) and len(nodo.value) > 15 \
                    and _SQL.search(nodo.value):
                encontrados.add(nodo.value)
    return sorted(encontrados)


class SinMensajeAgrupadoAntiguoTest(unittest.TestCase):
    def test_ninguna_regla_repite_la_frase(self):
        fragmentos = _fragmentos()
        for verificar in (verificar_procedimiento_normal, verificar_reporte):
            por_regla = defaultdict(list)
            antiguos = {}
            for fragmento in fragmentos:
                try:
                    for hallazgo in verificar(fragmento):
                        por_regla[hallazgo.regla].append(fragmento)
                        # Un ejemplo que ya trae dos casos (dos GOTO) también cuenta (22 nov.).
                        if _ANTIGUO.search(hallazgo.mensaje):
                            antiguos.setdefault(hallazgo.regla, hallazgo.mensaje[:200])
                except Exception:
                    continue
            for regla, lista in por_regla.items():
                for a, b in itertools.combinations(list(dict.fromkeys(lista))[:_CASOS_POR_REGLA], 2):
                    for hallazgo in verificar(a + "\n" + b):
                        if hallazgo.regla == regla and _ANTIGUO.search(hallazgo.mensaje):
                            antiguos.setdefault(regla, hallazgo.mensaje[:200])
            with self.subTest(modulo=verificar.__name__):
                self.assertEqual(antiguos, {})

    def test_validador_sql_no_repite_la_frase(self):
        # Validación SQL Server (ScriptDom): su último recurso era «Se identificaron N casos: La división …; La
        # división …» (la frase en cada caso). Ningún tipo debe caer ahí (usuaria, 22 nov.).
        from app.analizadores.scriptdom import validar_estructura
        if validar_estructura("SELECT 1") is None:
            self.skipTest("ScriptDom no está en esta PC (viene con SSMS)")
        por_tipo = defaultdict(list)
        for fragmento in _fragmentos():
            try:
                for hallazgo in validar_estructura(fragmento) or []:
                    if hallazgo.regla != "ERROR_SINTAXIS":
                        por_tipo[hallazgo.regla].append(fragmento)
            except Exception:
                continue
        repetidos = {}
        for tipo, lista in por_tipo.items():
            for a, b in itertools.combinations(list(dict.fromkeys(lista))[:_CASOS_POR_REGLA], 2):
                for hallazgo in validar_estructura(a + "\n" + b) or []:
                    if hallazgo.regla == tipo and (_ANTIGUO.search(hallazgo.mensaje)
                                                   or re.search(r"Se identificaron \d+ casos: ", hallazgo.mensaje)):
                        repetidos.setdefault(tipo, hallazgo.mensaje[:200])
        self.assertEqual(repetidos, {})



    def test_validador_sql_todos_los_tipos_simulados(self):
        """22 nov. (usuaria): «Bloque repetido» seguía con el formato antiguo porque ningún ejemplo de las pruebas lo
        disparaba dos veces. Aquí se simulan TODOS los tipos con mensaje, con 2 y 3 casos de valores distintos, por el
        mismo camino que la pantalla (mensaje_del_tipo). Un tipo nuevo que caiga en «N casos: …; …» hace fallar esto."""
        from app.analizadores.scriptdom import mensaje_del_tipo
        from app.analizadores.scriptdom_mensajes import MENSAJES

        class Hecho(dict):
            """Cualquier dato que el mensaje pida existe y cambia en cada caso; los números, como números."""
            NUMERICOS = ("largo", "estilo", "cantidad", "columnas", "valores", "niveles", "limite", "linea",
                         "primera", "segunda", "lineas", "consulta")

            def __init__(self, tipo, n):
                super().__init__(tipo=tipo, linea=n)
                self.n = n

            def __missing__(self, clave):
                if clave == "lineas":
                    return [self.n, self.n + 10]
                if clave == "estilo":  # formatos de fecha reales de CONVERT
                    return (103, 112, 108)[self.n % 3]
                if clave.lower().startswith(self.NUMERICOS) or clave in ("columnas", "valores"):
                    return 30 + self.n
                return f"{clave}{self.n}"

            def get(self, clave, defecto=None):
                return self[clave]

        antiguos, sin_simular = {}, []
        for tipo in MENSAJES:
            for cantidad in (2, 3):
                try:
                    mensaje = mensaje_del_tipo(tipo, [Hecho(tipo, n) for n in range(1, cantidad + 1)])
                except Exception as error:  # el tipo necesita datos con otra forma: se informa, no se oculta
                    sin_simular.append(f"{tipo}: {error!r}"[:120])
                    break
                if mensaje and (_ANTIGUO.search(mensaje) or re.search(r"Se identificaron \d+ casos: ", mensaje)):
                    antiguos.setdefault(tipo, mensaje[:200])
        self.assertEqual(antiguos, {})
        self.assertEqual(sin_simular, [], "tipos que la simulación no pudo armar: revisar a mano")

    def test_toda_regla_se_prueba_con_dos_casos(self):
        """22 nov.: el GOTO de Reportes salía con el texto antiguo porque ningún ejemplo lo disparaba. Toda regla debe
        dispararse en algún ejemplo de las pruebas (así entra en el barrido de arriba), salvo las que por cómo
        funcionan salen una sola vez por procedimiento (nombre, encabezado, una sola observación con todo)."""
        import re as _re
        una_vez = {  # una observación por procedimiento por construcción: no pueden juntarse dos casos
            "NOMBRE_ENCABEZADO_DISTINTO", "PROCEDIMIENTO_ACCION_SIN_SEPARAR", "PROCEDIMIENTO_SIN_ACCION",
            "PROCEDIMIENTO_SIN_PREFIJO_PA", "TEMPORAL_EXTERNA",
        }
        raiz = Path(__file__).resolve().parent.parent / "app" / "reglas"
        fragmentos = _fragmentos()
        for verificar, archivo in ((verificar_procedimiento_normal, "reglas_procedimientos_normales.py"),
                                   (verificar_reporte, "reglas_reportes.py")):
            ids = set(_re.findall(r'^\s{4}"([A-Z_0-9]+)":', (raiz / archivo).read_text(encoding="utf-8"), _re.M))
            vistas = set()
            for fragmento in fragmentos:
                try:
                    vistas.update(h.regla for h in verificar(fragmento))
                except Exception:
                    continue
            with self.subTest(modulo=verificar.__name__):
                self.assertEqual(sorted(ids - vistas - una_vez), [])


if __name__ == "__main__":
    unittest.main()
