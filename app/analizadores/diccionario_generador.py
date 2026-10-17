# -*- coding: utf-8 -*-
"""
Genera el script del diccionario que falta («Generar diccionario faltante»).

Arma una sentencia sp_addextendedproperty por cada elemento obligatorio que no
está documentado: en un CREATE, la tabla o el procedimiento y todas sus
columnas o parámetros; en un ALTER TABLE, solo las columnas nuevas (ADD).
La descripción va vacía (N'') para que el desarrollador la complete: si se
ejecuta sin completarla, la revisión la marca como descripción vacía.
"""

import re
from typing import List, Optional, Set

from app.analizadores import analizador_diccionario_procedimientos as procedimientos
from app.analizadores import analizador_diccionario_tablas as tablas
from app.analizadores.propiedades_extendidas import descripcion_mal_escrita, leer_propiedades_extendidas

_SANGRIA = "    "


def _en_orden(nombres: Set[str], texto: str) -> List[str]:
    """Los nombres en el orden en que aparecen en el CREATE/ALTER."""
    def posicion(nombre: str) -> int:
        m = re.search(rf"(?<![\w@]){re.escape(nombre)}(?!\w)", texto, re.IGNORECASE)
        return m.start() if m else len(texto)
    return sorted(nombres, key=lambda nombre: (posicion(nombre), nombre.upper()))


def _sentencia(nota: str, esquema: str, tipo1: str, nombre1: str, tipo2: str = None, nombre2: str = None) -> str:
    lineas = [
        "EXEC sys.sp_addextendedproperty",
        f"{_SANGRIA}@name = N'MS_Description', @value = N'',  -- Completar: {nota}",
        f"{_SANGRIA}@level0type = N'SCHEMA', @level0name = N'{esquema}',",
        f"{_SANGRIA}@level1type = N'{tipo1}', @level1name = N'{nombre1}'" + ("," if tipo2 else ";"),
    ]
    if tipo2:
        lineas.append(f"{_SANGRIA}@level2type = N'{tipo2}', @level2name = N'{nombre2}';")
    return "\n".join(lineas) + "\nGO"


def _armar(titulo: str, sentencias: List[str], elementos: List[str]) -> Optional[dict]:
    if not sentencias:
        return None
    script = f"-- {titulo}\n\n" + "\n\n".join(sentencias) + "\n"
    return {"script": script, "elementos": elementos}


def diccionario_faltante_tabla(texto_tabla: str, texto_diccionario: str) -> Optional[dict]:
    esquema, nombre = tablas.extraer_esquema_y_nombre(texto_tabla)
    if nombre is None:
        return None
    es_create = tablas.extraer_tipo_sentencia(texto_tabla) == "CREATE"
    agregadas, _ = tablas.extraer_columnas_alter(texto_tabla)
    requeridas = tablas.extraer_columnas(texto_tabla) if es_create else agregadas
    llamadas = leer_propiedades_extendidas(texto_diccionario)

    # Una propiedad con el nombre mal escrito sí se escribió: no se vuelve a generar.
    def documenta(ll) -> bool:
        return tablas._es_descripcion(ll) or descripcion_mal_escrita(ll.texto("name"))

    documentadas = {ll.texto("level2name").upper() for ll in llamadas if tablas._es_de_columna(ll) and documenta(ll)}
    tabla_documentada = any(
        tablas._es_de_tabla(ll) and documenta(ll) and ll.texto("level1name").upper() in (nombre.upper(), "")
        for ll in llamadas
    )

    esquema_sql = esquema or "dbo"
    sentencias, elementos = [], []
    if es_create and not tabla_documentada:
        sentencias.append(_sentencia("finalidad de la tabla", esquema_sql, "TABLE", nombre))
        elementos.append(f"tabla {nombre}")
    unicas = {c.upper(): c for c in requeridas}
    faltantes = {c for clave, c in unicas.items() if clave not in documentadas}
    for columna in _en_orden(faltantes, texto_tabla):
        sentencias.append(_sentencia("dato que almacena la columna", esquema_sql, "TABLE", nombre, "COLUMN", columna))
        elementos.append(columna)
    return _armar(f"Diccionario faltante de la tabla {esquema_sql}.{nombre}", sentencias, elementos)


def diccionario_faltante_procedimiento(texto_procedimiento: str, texto_diccionario: str) -> Optional[dict]:
    esquema, nombre = procedimientos.extraer_esquema_y_nombre(texto_procedimiento)
    if nombre is None or procedimientos.extraer_tipo_sentencia(texto_procedimiento) != "CREATE":
        # En un ALTER PROCEDURE no se sabe qué ya estaba documentado: solo se pide validar.
        return None
    llamadas = leer_propiedades_extendidas(texto_diccionario)
    documentados = {
        ll.texto("level2name").upper() for ll in llamadas if "PARAMETER" in ll.texto("level2type").upper()
    }
    procedimiento_documentado = any(
        "PROCEDURE" in ll.texto("level1type").upper() and "PARAMETER" not in ll.texto("level2type").upper()
        for ll in llamadas
    )

    esquema_sql = esquema or "dbo"
    sentencias, elementos = [], []
    if not procedimiento_documentado:
        sentencias.append(_sentencia("finalidad del procedimiento", esquema_sql, "PROCEDURE", nombre))
        elementos.append(f"procedimiento {nombre}")
    faltantes = {p for p in procedimientos.extraer_parametros(texto_procedimiento) if p.upper() not in documentados}
    for parametro in _en_orden(faltantes, texto_procedimiento):
        sentencias.append(_sentencia("para qué se usa el parámetro", esquema_sql, "PROCEDURE", nombre, "PARAMETER", parametro))
        elementos.append(parametro)
    return _armar(f"Diccionario faltante del procedimiento {esquema_sql}.{nombre}", sentencias, elementos)
