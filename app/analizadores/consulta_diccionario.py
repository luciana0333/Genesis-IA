# -*- coding: utf-8 -*-
"""«Copiar consulta de validación» en las observaciones que piden verificar el diccionario (usuaria, 23 nov.).

Cuando un objeto se modifica (ALTER), Genesis pide verificar qué descripciones ya están registradas: si ya existen,
sp_addextendedproperty falla y corresponde sp_updateextendedproperty. Esta consulta lo muestra en una sola vista:
el objeto y cada parámetro (o columna), con su descripción o «(sin descripción)».

Decisiones (probadas en SQL Server, 23 nov.):
- Se filtra por esquema y nombre: un mismo nombre en dos esquemas no se mezcla (el objeto es esquema + nombre).
- Se parte de los parámetros/columnas reales, así también sale lo que falta documentar.
- Las descripciones de parámetros se unen con class = 2: en una función escalar el parámetro 0 es el valor de
  retorno y, sin ese filtro, se cruzaba con la descripción de la función.
"""

from typing import Iterable, List, Optional, Sequence, Tuple

from app.modelos.hallazgo import Hallazgo

Objeto = Tuple[Optional[str], str]  # (esquema o None, nombre)

_TIPOS = {
    "procedimiento": ("('P', 'PC')", "Descripción del procedimiento"),
    "funcion": ("('FN', 'IF', 'TF', 'FS', 'FT')", "Descripción de la función"),
    "tabla": ("('U')", "Descripción de la tabla"),
}

_ENCABEZADO = (
    "-- Genesis · Descripciones registradas en el diccionario\n"
    "-- Con descripción: ya existe; usar sp_updateextendedproperty.\n"
    "-- (sin descripción): se puede agregar con sp_addextendedproperty.\n"
    "-- Sin filas: el objeto no existe con ese esquema y nombre en esta base.\n"
)


def _texto(valor: str) -> str:
    return "N'" + valor.replace("'", "''") + "'"


def _filtro(objetos: Sequence[Objeto], tipos: str) -> str:
    condiciones = []
    for esquema, nombre in objetos:
        if esquema:
            condiciones.append(f"(s.name = {_texto(esquema)} AND o.name = {_texto(nombre)})")
        else:
            condiciones.append(f"o.name = {_texto(nombre)}")
    unidas = condiciones[0] if len(condiciones) == 1 else "(" + "\n       OR ".join(condiciones) + ")"
    return f"o.type IN {tipos}\n      AND {unidas}"


def consulta_descripciones(tipo: str, objetos: Iterable[Objeto]) -> Optional[str]:
    """La consulta para los objetos dados ('procedimiento', 'funcion' o 'tabla'); None si no hay objetos."""
    objetos = list(dict.fromkeys((e, n) for e, n in objetos if n))
    if not objetos or tipo not in _TIPOS:
        return None
    tipos, del_objeto = _TIPOS[tipo]
    filtro = _filtro(objetos, tipos)
    if tipo == "tabla":
        detalle = (
            "    SELECT s.name, o.name, c.column_id, c.name,\n"
            "           ISNULL(CONVERT(NVARCHAR(4000), ep.value), N'(sin descripción)')\n"
            "    FROM sys.objects AS o\n"
            "    INNER JOIN sys.schemas AS s ON s.schema_id = o.schema_id\n"
            "    INNER JOIN sys.columns AS c ON c.object_id = o.object_id\n"
            "    LEFT JOIN sys.extended_properties AS ep\n"
            "        ON ep.class = 1 AND ep.major_id = c.object_id AND ep.minor_id = c.column_id\n"
            "       AND ep.name = N'MS_Description'\n"
        )
        columna = "Columna"
    else:
        detalle = (
            "    SELECT s.name, o.name, pr.parameter_id, pr.name,\n"
            "           ISNULL(CONVERT(NVARCHAR(4000), ep.value), N'(sin descripción)')\n"
            "    FROM sys.objects AS o\n"
            "    INNER JOIN sys.schemas AS s ON s.schema_id = o.schema_id\n"
            "    INNER JOIN sys.parameters AS pr ON pr.object_id = o.object_id AND pr.parameter_id > 0\n"
            "    LEFT JOIN sys.extended_properties AS ep\n"
            "        ON ep.class = 2 AND ep.major_id = pr.object_id AND ep.minor_id = pr.parameter_id\n"
            "       AND ep.name = N'MS_Description'\n"
        )
        columna = "Parametro"
    return (
        f"{_ENCABEZADO}"
        f"SELECT d.Esquema, d.Objeto, d.Elemento AS {columna}, d.Descripcion\n"
        "FROM (\n"
        f"    SELECT s.name AS Esquema, o.name AS Objeto, 0 AS Orden, N'{del_objeto}' AS Elemento,\n"
        "           ISNULL(CONVERT(NVARCHAR(4000), ep.value), N'(sin descripción)') AS Descripcion\n"
        "    FROM sys.objects AS o\n"
        "    INNER JOIN sys.schemas AS s ON s.schema_id = o.schema_id\n"
        "    LEFT JOIN sys.extended_properties AS ep\n"
        "        ON ep.class = 1 AND ep.major_id = o.object_id AND ep.minor_id = 0\n"
        "       AND ep.name = N'MS_Description'\n"
        f"    WHERE {filtro}\n"
        "    UNION ALL\n"
        f"{detalle}"
        f"    WHERE {filtro}\n"
        ") AS d\n"
        "ORDER BY d.Esquema, d.Objeto, d.Orden;"
    )


def adjuntar_consulta(hallazgos: List[Hallazgo], reglas: Iterable[str], tipo: str,
                      objetos: Iterable[Objeto]) -> List[Hallazgo]:
    """Pone la consulta (botón «Copiar consulta de validación») en las observaciones de esas reglas."""
    reglas = set(reglas)
    if not any(h.regla in reglas for h in hallazgos):
        return hallazgos
    consulta = consulta_descripciones(tipo, objetos)
    if consulta:
        for hallazgo in hallazgos:
            if hallazgo.regla in reglas:
                hallazgo.consulta = consulta
    return hallazgos
