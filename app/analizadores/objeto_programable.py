"""Procedimiento o función: lo que cambia entre sus diccionarios (usuaria, 11 nov.: «funciona igual que un diccionario
de procedimientos, aplícale todas las validaciones»).

El diccionario de procedimientos revisa los dos objetos con las mismas reglas; aquí está lo único distinto: cómo se
escribe su encabezado, dónde terminan sus parámetros, el tipo en @level1type y los textos (con su género:
«el procedimiento … documentado» / «la función … documentada»). Para sumar otro objeto (vista, trigger) basta con
otra entrada aquí.

El objeto en revisión se guarda en un ContextVar: cada petición del servidor corre en su propio hilo, así que dos
revisiones al mismo tiempo no se mezclan.
"""

import re
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Optional, Pattern


@dataclass(frozen=True)
class ObjetoProgramable:
    clave: str                    # «procedimiento» / «funcion» (tipoRevision y objetos_repetidos)
    tipo_sql: str                 # PROCEDURE / FUNCTION, como va en @level1type
    encabezado: Pattern           # CREATE / ALTER / CREATE OR ALTER + nombre (grupo 1: la acción)
    fin_parametros: Pattern       # dónde terminan los parámetros: AS (procedimiento) o RETURNS (función)
    nombre: str                   # procedimiento / función
    plural: str                   # procedimientos / funciones
    el: str                       # el procedimiento / la función
    del_: str                     # del procedimiento / de la función
    al: str                       # al procedimiento / a la función
    ese: str                      # ese procedimiento / esa función
    documentado: str              # documentado / documentada
    un_nuevo: str                 # un procedimiento nuevo / una función nueva
    todo_nuevo: str               # todo procedimiento nuevo / toda función nueva
    alter: str                    # ALTER PROCEDURE / ALTER FUNCTION
    create: str                   # CREATE PROCEDURE / CREATE FUNCTION
    ejemplo_nombre: str           # para «@level1name=N'…'» cuando falta el nombre
    revisa_nomenclatura: bool     # el estándar PA_Tabla_Acción_Finalidad solo es de procedimientos

    @property
    def El(self) -> str:  # noqa: N802 — «El procedimiento» / «La función» al inicio de una oración
        return self.el[:1].upper() + self.el[1:]


_NOMBRE = r"(?:\[[^\]]+\]|[\w$#]+)(?:\s*\.\s*(?:\[[^\]]+\]|[\w$#]+)){0,2}"

PROCEDIMIENTO = ObjetoProgramable(
    clave="procedimiento", tipo_sql="PROCEDURE",
    encabezado=re.compile(rf"\b(CREATE(?:\s+OR\s+ALTER)?|ALTER)\s+PROC(?:EDURE)?\s+{_NOMBRE}", re.IGNORECASE),
    fin_parametros=re.compile(r"\bAS\b", re.IGNORECASE),
    nombre="procedimiento", plural="procedimientos", el="el procedimiento", del_="del procedimiento",
    al="al procedimiento", ese="ese procedimiento", documentado="documentado",
    un_nuevo="un procedimiento nuevo", todo_nuevo="todo procedimiento nuevo",
    alter="ALTER PROCEDURE", create="CREATE PROCEDURE", ejemplo_nombre="PA_Tabla_Sel_Finalidad",
    revisa_nomenclatura=True,
)

FUNCION = ObjetoProgramable(
    clave="funcion", tipo_sql="FUNCTION",
    encabezado=re.compile(rf"\b(CREATE(?:\s+OR\s+ALTER)?|ALTER)\s+FUNCTION\s+{_NOMBRE}", re.IGNORECASE),
    # Los parámetros van entre el nombre y RETURNS; lo que sigue (RETURNS @Resultado TABLE …) no son parámetros.
    fin_parametros=re.compile(r"\bRETURNS\b", re.IGNORECASE),
    nombre="función", plural="funciones", el="la función", del_="de la función",
    al="a la función", ese="esa función", documentado="documentada",
    un_nuevo="una función nueva", todo_nuevo="toda función nueva",
    alter="ALTER FUNCTION", create="CREATE FUNCTION", ejemplo_nombre="FN_Nombre",
    revisa_nomenclatura=False,
)

POR_CLAVE = {objeto.clave: objeto for objeto in (PROCEDIMIENTO, FUNCION)}

_ACTUAL: ContextVar[ObjetoProgramable] = ContextVar("objeto_programable", default=PROCEDIMIENTO)


def actual() -> ObjetoProgramable:
    """El objeto que se está revisando (procedimiento si no se indicó otro)."""
    return _ACTUAL.get()


def usar(objeto: Optional[ObjetoProgramable]):
    """Fija el objeto en revisión; devuelve el token para restaurar el anterior (_ACTUAL.reset)."""
    return _ACTUAL.set(objeto or PROCEDIMIENTO)


def restaurar(token) -> None:
    _ACTUAL.reset(token)
