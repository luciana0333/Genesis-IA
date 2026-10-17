# -*- coding: utf-8 -*-
"""
Genera el script del diccionario que falta («Generar diccionario faltante»).

Arma una sentencia sp_addextendedproperty por cada elemento obligatorio que no
está documentado: en un CREATE, la tabla o el procedimiento y todas sus
columnas o parámetros; en un ALTER TABLE, solo las columnas nuevas (ADD).
Cada descripción viene sugerida a partir del nombre (descripciones_sugeridas)
y marcada «Sugerida: revisar y mejorar»; si no se puede deducir, va vacía (N'')
con «Completar»: si se ejecuta así, la revisión la marca como descripción vacía.
"""

import re
from typing import List, Optional, Set

from app.analizadores import analizador_diccionario_procedimientos as procedimientos
from app.analizadores import analizador_diccionario_tablas as tablas
from app.analizadores import descripciones_sugeridas as sugeridas
from app.analizadores.propiedades_extendidas import descripcion_mal_escrita, leer_propiedades_extendidas

_SANGRIA = "    "


def _en_orden(nombres: Set[str], texto: str) -> List[str]:
    """Los nombres en el orden en que aparecen en el CREATE/ALTER."""
    def posicion(nombre: str) -> int:
        m = re.search(rf"(?<![\w@]){re.escape(nombre)}(?!\w)", texto, re.IGNORECASE)
        return m.start() if m else len(texto)
    return sorted(nombres, key=lambda nombre: (posicion(nombre), nombre.upper()))


_ID = tablas._IDENTIFICADOR_SQL
_NOMBRE_OBJETO = rf"{_ID}(?:\s*\.\s*{_ID}){{0,2}}"
_FIN_DEFAULT = r"(?=\s+(?:NOT\b|NULL\b|CONSTRAINT\b|PRIMARY\b|IDENTITY\b|COLLATE\b|CHECK\b|UNIQUE\b|REFERENCES\b)|\s*$)"


def _ultima_parte(nombre: str) -> str:
    """CLICKTOPAY.[Agencia] -> Agencia."""
    return tablas._limpiar_identificador_sql(re.findall(_ID, nombre)[-1])


def _limpiar_default(valor: str) -> str:
    """((1)) -> 1, (getdate()) -> GETDATE(), ('A') -> 'A'."""
    valor = valor.strip()
    while valor.startswith("(") and valor.endswith(")"):
        valor = valor[1:-1].strip()
    return valor.upper() if re.match(r"^[A-Za-z_]+\(\)$", valor) else valor


def _cuerpo_create(texto: str) -> str:
    m = re.search(rf"\bCREATE\s+TABLE\s+{_NOMBRE_OBJETO}\s*\(", texto, re.IGNORECASE)
    if not m:
        return ""
    profundidad = 0
    for i in range(m.end(), len(texto)):
        if texto[i] == "(":
            profundidad += 1
        elif texto[i] == ")":
            if profundidad == 0:
                return texto[m.end():i]
            profundidad -= 1
    return texto[m.end():]


def definiciones_columnas(texto_tabla: str) -> dict:
    """
    Lo que el CREATE/ALTER dice de cada columna (clave en mayúsculas):
    {'pk': bool, 'identity': bool, 'referencia': 'Agencia', 'default': '1'}.
    """
    texto = tablas._sin_comentarios(texto_tabla)
    segmentos = tablas._separar_por_comas(_cuerpo_create(texto))
    for sentencia in re.finditer(r"\bALTER\s+TABLE\b(.*?)(?=;|\bGO\b|\bALTER\s+TABLE\b|\bCREATE\b|\Z)", texto, re.IGNORECASE | re.DOTALL):
        m_add = re.search(r"\bADD\b(?:\s+COLUMN\b)?", sentencia.group(1), re.IGNORECASE)
        if m_add:
            segmentos += tablas._separar_por_comas(sentencia.group(1)[m_add.end():])

    info: dict = {}
    for segmento in segmentos:
        columna = tablas._primera_columna(segmento)
        if not columna:
            continue
        datos = info.setdefault(columna.upper(), {})
        if re.search(r"\bIDENTITY\b", segmento, re.IGNORECASE):
            datos["identity"] = True
        if re.search(r"\bPRIMARY\s+KEY\b(?!\s*(?:(?:NON)?CLUSTERED\s*)?\()", segmento, re.IGNORECASE):
            datos["pk"] = True
        referencia = re.search(rf"\bREFERENCES\s+({_NOMBRE_OBJETO})", segmento, re.IGNORECASE)
        if referencia:
            datos["referencia"] = _ultima_parte(referencia.group(1))
        defecto = re.search(rf"\bDEFAULT\s+(.+?){_FIN_DEFAULT}", segmento, re.IGNORECASE | re.DOTALL)
        if defecto:
            datos["default"] = _limpiar_default(defecto.group(1))

    # Restricciones aparte: PRIMARY KEY (col), FOREIGN KEY (col) REFERENCES T, DEFAULT x FOR col.
    for m in re.finditer(r"\bPRIMARY\s+KEY\s*(?:(?:NON)?CLUSTERED\s*)?\(([^)]*)\)", texto, re.IGNORECASE):
        for columna in re.findall(_ID, m.group(1)):
            info.setdefault(tablas._limpiar_identificador_sql(columna).upper(), {})["pk"] = True
    for m in re.finditer(rf"\bFOREIGN\s+KEY\s*\(([^)]*)\)\s*REFERENCES\s+({_NOMBRE_OBJETO})", texto, re.IGNORECASE):
        for columna in re.findall(_ID, m.group(1)):
            info.setdefault(tablas._limpiar_identificador_sql(columna).upper(), {})["referencia"] = _ultima_parte(m.group(2))
    for m in re.finditer(rf"\bDEFAULT\s*(\(.*?\)|'[^']*'|\S+)\s+FOR\s+({_ID})", texto, re.IGNORECASE):
        info.setdefault(tablas._limpiar_identificador_sql(m.group(2)).upper(), {})["default"] = _limpiar_default(m.group(1))
    return info


def _sentencia(
    nota: str, sugerida: Optional[str], esquema: str, tipo1: str, nombre1: str, tipo2: str = None, nombre2: str = None
) -> str:
    if sugerida:
        valor = f"N'{sugerida.replace(chr(39), chr(39) * 2)}',  -- Sugerida: revisar y mejorar"
    else:
        valor = f"N'',  -- Completar: {nota}"
    lineas = [
        "EXEC sys.sp_addextendedproperty",
        f"{_SANGRIA}@name = N'MS_Description', @value = {valor}",
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
        sentencias.append(_sentencia("finalidad de la tabla", sugeridas.sugerir_tabla(nombre), esquema_sql, "TABLE", nombre))
        elementos.append(f"tabla {nombre}")
    unicas = {c.upper(): c for c in requeridas}
    faltantes = {c for clave, c in unicas.items() if clave not in documentadas}
    info = definiciones_columnas(texto_tabla)
    for columna in _en_orden(faltantes, texto_tabla):
        sentencias.append(_sentencia(
            "dato que almacena la columna", sugeridas.sugerir_columna(columna, nombre, info=info.get(columna.upper())),
            esquema_sql, "TABLE", nombre, "COLUMN", columna,
        ))
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
    # Los parámetros se describen respecto de la tabla del nombre (PA_Cliente_Sel_PorId -> Cliente).
    partes = [parte for parte in nombre.split("_") if parte]
    entidad = partes[1] if len(partes) > 1 and partes[0].upper() == "PA" else nombre
    accion = sugeridas.accion_procedimiento(nombre)
    sentencias, elementos = [], []
    if not procedimiento_documentado:
        sentencias.append(_sentencia(
            "finalidad del procedimiento", sugeridas.sugerir_procedimiento(nombre), esquema_sql, "PROCEDURE", nombre,
        ))
        elementos.append(f"procedimiento {nombre}")
    faltantes = {p for p in procedimientos.extraer_parametros(texto_procedimiento) if p.upper() not in documentados}
    for parametro in _en_orden(faltantes, texto_procedimiento):
        sentencias.append(_sentencia(
            "para qué se usa el parámetro", sugeridas.sugerir_columna(parametro, entidad, es_parametro=True, accion=accion),
            esquema_sql, "PROCEDURE", nombre, "PARAMETER", parametro,
        ))
        elementos.append(parametro)
    return _armar(f"Diccionario faltante del procedimiento {esquema_sql}.{nombre}", sentencias, elementos)
