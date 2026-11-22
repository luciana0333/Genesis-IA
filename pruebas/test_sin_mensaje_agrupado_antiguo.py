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
            for fragmento in fragmentos:
                try:
                    for hallazgo in verificar(fragmento):
                        por_regla[hallazgo.regla].append(fragmento)
                except Exception:
                    continue
            antiguos = {}
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


if __name__ == "__main__":
    unittest.main()
