# -*- coding: utf-8 -*-
"""
analizador_diccionario_tablas.py
------------------------------
Analiza el diccionario de tablas (sp_addextendedproperty) y compara la
"realidad" (CREATE/ALTER TABLE) contra la "documentacion".

El script del diccionario se lee con propiedades_extendidas, por lo que las
sentencias pueden separarse con GO, con ";", con ambos o sin nada.
"""

import difflib
import re
import unicodedata
from typing import Dict, List, Optional, Set, Tuple

from app.analizadores.ortografia import palabras_mal_escritas
from app.analizadores.propiedades_extendidas import (
    LlamadaPropiedad,
    como_llamadas_crudas,
    leer_propiedades_extendidas,
)
from app.modelos.hallazgo import Hallazgo, Severidad, OrigenAnalisis
from app.reglas.reglas_diccionario_tablas import REGLAS_DICCIONARIO_TABLAS


_IDENTIFICADOR_SQL = r"(?:\[[^\]]+\]|[A-Za-z_][\w$#@]*)"


def _limpiar_identificador_sql(valor: str) -> str:
    """Quita los corchetes de un identificador SQL Server."""
    if valor.startswith("[") and valor.endswith("]"):
        return valor[1:-1]
    return valor


def _nombre_completo(esquema: Optional[str], nombre: str) -> str:
    """Devuelve 'esquema.nombre' si esquema existe, sino solo 'nombre'."""
    return f"{esquema}.{nombre}" if esquema else nombre


_COMENTARIOS_SQL = re.compile(r"--[^\r\n]*|/\*.*?\*/", re.DOTALL)
_PALABRAS_NO_COLUMNA = {
    "CONSTRAINT", "PRIMARY", "FOREIGN", "UNIQUE", "CHECK", "INDEX", "KEY",
    "ALTER", "ADD", "DROP", "PERIOD", "DEFAULT",
}


def _sin_comentarios(texto_sql: str) -> str:
    return _COMENTARIOS_SQL.sub(" ", texto_sql or "")


def _separar_por_comas(contenido: str) -> List[str]:
    """Divide por comas de primer nivel (respeta paréntesis y cadenas)."""
    segmentos, actual, profundidad, en_cadena = [], [], 0, False
    for ch in contenido:
        if ch == "'":
            en_cadena = not en_cadena
        elif not en_cadena:
            if ch == "(":
                profundidad += 1
            elif ch == ")":
                profundidad = max(profundidad - 1, 0)
            elif ch == "," and profundidad == 0:
                segmentos.append("".join(actual))
                actual = []
                continue
        actual.append(ch)
    if actual:
        segmentos.append("".join(actual))
    return segmentos


def _primera_columna(segmento: str) -> Optional[str]:
    """Nombre de columna al inicio de una definición, o None si es una restricción."""
    coincidencia = re.match(rf"\s*({_IDENTIFICADOR_SQL})", segmento)
    if not coincidencia:
        return None
    nombre = _limpiar_identificador_sql(coincidencia.group(1))
    return None if nombre.upper() in _PALABRAS_NO_COLUMNA else nombre


# ---------------------------------------------------------------------------
# EXTRACCION - leer la "realidad" (la tabla)
# ---------------------------------------------------------------------------

def extraer_tipo_sentencia(texto_sql: str) -> str:
    """
    CREATE si el script crea la tabla (aunque luego tenga ALTER TABLE para
    agregar restricciones); ALTER si solo la modifica.
    """
    texto = _sin_comentarios(texto_sql)
    if re.search(r"\bCREATE\s+TABLE\b", texto, re.IGNORECASE):
        return "CREATE"
    if re.search(r"\bALTER\s+TABLE\b", texto, re.IGNORECASE):
        return "ALTER"
    return "DESCONOCIDO"


def extraer_esquema_y_nombre(texto_sql: str) -> Tuple[Optional[str], Optional[str]]:
    """Devuelve (esquema, nombre) de la tabla (prioriza el CREATE), o (None, None)."""
    texto = _sin_comentarios(texto_sql)
    for verbo in ("CREATE", "ALTER"):
        m = re.search(
            rf"\b{verbo}\s+TABLE\s+({_IDENTIFICADOR_SQL})(?:\s*\.\s*({_IDENTIFICADOR_SQL}))?",
            texto,
            re.IGNORECASE,
        )
        if m:
            if m.group(2):
                return _limpiar_identificador_sql(m.group(1)), _limpiar_identificador_sql(m.group(2))
            return None, _limpiar_identificador_sql(m.group(1))
    return None, None


def _columnas_create(texto: str) -> Set[str]:
    """Columnas definidas entre los paréntesis del CREATE TABLE."""
    m = re.search(
        rf"\bCREATE\s+TABLE\s+{_IDENTIFICADOR_SQL}(?:\s*\.\s*{_IDENTIFICADOR_SQL})?\s*\(",
        texto,
        re.IGNORECASE,
    )
    if not m:
        return set()
    inicio, profundidad, fin = m.end(), 0, len(texto)
    for i in range(inicio, len(texto)):
        if texto[i] == "(":
            profundidad += 1
        elif texto[i] == ")":
            if profundidad == 0:
                fin = i
                break
            profundidad -= 1
    columnas = (_primera_columna(s) for s in _separar_por_comas(texto[inicio:fin]))
    return {c for c in columnas if c}


def extraer_columnas_alter(texto_sql: str) -> Tuple[Set[str], Set[str]]:
    """
    Columnas de los ALTER TABLE del script: (agregadas con ADD, modificadas
    con ALTER COLUMN). ADD admite varias columnas separadas por comas y
    descarta ADD CONSTRAINT / PRIMARY KEY / etc.
    """
    texto = _sin_comentarios(texto_sql)
    agregadas: Set[str] = set()
    modificadas: Set[str] = set()
    sentencias = re.finditer(
        r"\bALTER\s+TABLE\b(.*?)(?=;|\bGO\b|\bALTER\s+TABLE\b|\bCREATE\b|\Z)",
        texto,
        re.IGNORECASE | re.DOTALL,
    )
    for sentencia in sentencias:
        cuerpo = sentencia.group(1)
        m_alter = re.search(rf"\bALTER\s+COLUMN\s+({_IDENTIFICADOR_SQL})", cuerpo, re.IGNORECASE)
        if m_alter:
            modificadas.add(_limpiar_identificador_sql(m_alter.group(1)))
            continue
        m_add = re.search(r"\bADD\b(?:\s+COLUMN\b)?", cuerpo, re.IGNORECASE)
        if m_add:
            for segmento in _separar_por_comas(cuerpo[m_add.end():]):
                columna = _primera_columna(segmento)
                if columna:
                    agregadas.add(columna)
    return agregadas, modificadas


def extraer_columnas(texto_sql: str) -> Set[str]:
    """
    Columnas que el script crea o modifica: las del CREATE TABLE más las
    agregadas o modificadas en ALTER TABLE.
    """
    texto = _sin_comentarios(texto_sql)
    agregadas, modificadas = extraer_columnas_alter(texto)
    return _columnas_create(texto) | agregadas | modificadas


# ---------------------------------------------------------------------------
# EXTRACCION - leer la "documentacion" (diccionario)
# ---------------------------------------------------------------------------

_PARAMETROS_OBLIGATORIOS = ("name", "value", "level0type", "level0name", "level1type", "level1name")
_PARAMETROS_DE_NOMBRE = ("level0name", "level1name", "level2name")


def extraer_llamadas_extendedproperty(texto_diccionario: str) -> List[Tuple[int, Dict[str, str]]]:
    """Compatibilidad: llamadas como [(posicion, {parametro: valor_crudo})]."""
    return como_llamadas_crudas(leer_propiedades_extendidas(texto_diccionario))


def _es_descripcion(llamada: LlamadaPropiedad) -> bool:
    """Solo las propiedades MS_Description son descripciones del diccionario."""
    nombre = llamada.texto("name")
    return nombre == "" or nombre.upper() == "MS_DESCRIPTION"


def _es_de_tabla(llamada: LlamadaPropiedad) -> bool:
    return llamada.texto("level1type").upper() == "TABLE" and not llamada.tiene("level2type")


def _es_de_columna(llamada: LlamadaPropiedad) -> bool:
    return llamada.texto("level2type").upper() == "COLUMN" and bool(llamada.texto("level2name"))


def _normalizar_texto(texto: str) -> str:
    """Minúsculas, sin tildes ni espacios repetidos: para comparar descripciones."""
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )
    return " ".join(sin_tildes.lower().split())


def _hallazgo(linea: int, regla: str, mensaje: str) -> Hallazgo:
    """Crea el hallazgo con la severidad definida en el catálogo de reglas."""
    return Hallazgo(
        linea=linea,
        origen=OrigenAnalisis.DICCIONARIO,
        severidad=Severidad(REGLAS_DICCIONARIO_TABLAS[regla].severidad),
        regla=regla,
        mensaje=mensaje,
    )


# ---------------------------------------------------------------------------
# VALIDACIONES
# ---------------------------------------------------------------------------

def _validar_sintaxis(llamadas: List[LlamadaPropiedad]) -> List[Hallazgo]:
    """Errores de escritura del script: SQL Server no lo podría ejecutar."""
    return [
        _hallazgo(linea, "SINTAXIS_DICCIONARIO", mensaje)
        for llamada in llamadas
        for linea, mensaje in llamada.errores
    ]


def _validar_parametros(llamadas: List[LlamadaPropiedad]) -> List[Hallazgo]:
    """Cada sentencia debe traer los parámetros obligatorios y niveles válidos."""
    hallazgos = []
    for llamada in llamadas:
        faltantes = [f"@{p}" for p in _PARAMETROS_OBLIGATORIOS if not llamada.tiene(p)]
        if llamada.tiene("level2type") != llamada.tiene("level2name"):
            faltantes.append("@level2name" if llamada.tiene("level2type") else "@level2type")
        if faltantes:
            hallazgos.append(_hallazgo(
                llamada.linea, "PARAMETROS_INCOMPLETOS",
                f"A esta sentencia le faltan datos obligatorios: {', '.join(faltantes)}. Complétela para que se pueda ejecutar.",
            ))

        tipo0 = llamada.texto("level0type").upper()
        tipo1 = llamada.texto("level1type").upper()
        if tipo0 and tipo0 != "SCHEMA":
            hallazgos.append(_hallazgo(
                llamada.linea, "TIPO_NIVEL_INCORRECTO",
                f"El nivel 0 dice '{llamada.texto('level0type')}', pero debe ser 'SCHEMA' (@level0type = N'SCHEMA').",
            ))
        if tipo1 and tipo1 != "TABLE":
            hallazgos.append(_hallazgo(
                llamada.linea, "TIPO_NIVEL_INCORRECTO",
                f"El nivel 1 dice '{llamada.texto('level1type')}', pero para documentar una tabla debe ser 'TABLE' (@level1type = N'TABLE').",
            ))
    return hallazgos


def _validar_tabla_documentada(
    llamadas: List[LlamadaPropiedad], esquema: Optional[str], nombre_tabla: str
) -> List[Hallazgo]:
    """La propia tabla debe tener su descripción (sentencia sin @level2type) y no vacía."""
    sentencias_tabla = [
        ll for ll in llamadas
        if _es_de_tabla(ll) and _es_descripcion(ll)
        and ll.texto("level1name").upper() == nombre_tabla.upper()
    ]
    if any(ll.texto("value") for ll in sentencias_tabla):
        return []
    full = _nombre_completo(esquema, nombre_tabla)
    if sentencias_tabla:
        return [_hallazgo(
            sentencias_tabla[0].linea, "TABLA_SIN_DESCRIPCION",
            f"La tabla {full} está en el diccionario, pero su descripción está vacía. Escriba para qué sirve la tabla.",
        )]
    return [_hallazgo(
        1, "TABLA_SIN_DESCRIPCION",
        f"La tabla {full} no se encuentra documentada. Agréguela al diccionario con su descripción.",
    )]


def _validar_esquema(llamadas: List[LlamadaPropiedad], esquema_real: Optional[str]) -> List[Hallazgo]:
    # Si la tabla no declara esquema en el SQL, no hay contra qué comparar.
    if not esquema_real:
        return []
    return [
        _hallazgo(
            ll.linea, "ESQUEMA_NO_COINCIDE",
            f"El esquema no coincide: el diccionario dice '{ll.texto('level0name')}', pero la tabla "
            f"está en '{esquema_real}'. Corrija @level0name.",
        )
        for ll in llamadas
        if ll.texto("level0name") and ll.texto("level0name").lower() != esquema_real.lower()
    ]


def _validar_nombre_tabla(llamadas: List[LlamadaPropiedad], nombre_tabla: str) -> List[Hallazgo]:
    return [
        _hallazgo(
            ll.linea, "NOMBRE_TABLA_NO_COINCIDE",
            f"El nombre de la tabla no coincide: el diccionario dice '{ll.texto('level1name')}', "
            f"pero la tabla se llama '{nombre_tabla}'. Corrija @level1name.",
        )
        for ll in llamadas
        if ll.texto("level1type").upper() == "TABLE"
        and ll.texto("level1name")
        and ll.texto("level1name").upper() != nombre_tabla.upper()
    ]


def _columnas_documentadas(llamadas: List[LlamadaPropiedad]) -> Set[str]:
    return {
        ll.texto("level2name").upper()
        for ll in llamadas
        if _es_de_columna(ll) and _es_descripcion(ll)
    }


def _validar_columnas_faltantes(
    columnas_reales: Set[str],
    llamadas: List[LlamadaPropiedad],
    tipo_sentencia: str,
    esquema: Optional[str],
    nombre_tabla: str,
) -> List[Hallazgo]:
    """
    Recibe las columnas que deben documentarse: en un CREATE, todas; en un
    ALTER, solo las nuevas (ADD).
    """
    documentadas = _columnas_documentadas(llamadas)
    # Una sola entrada por columna (sin distinguir mayúsculas), con su nombre original.
    reales = {c.upper(): c for c in sorted(columnas_reales)}
    hallazgos = []
    for clave in sorted(set(reales) - documentadas):
        columna = reales[clave]
        if tipo_sentencia == "ALTER":
            mensaje = (
                f"La columna {columna} se agrega en el ALTER TABLE, pero no se encuentra documentada. "
                f"Agréguela al diccionario con su descripción."
            )
        else:
            mensaje = f"La columna {columna} no se encuentra documentada. Agréguela al diccionario con su descripción."
        hallazgos.append(_hallazgo(1, "COLUMNA_FALTANTE", mensaje))
    return hallazgos


def _validar_documentacion_existente_en_alter(
    llamadas: List[LlamadaPropiedad],
    tipo_sentencia: str,
    esquema: Optional[str],
    nombre_tabla: str,
    columnas_agregadas: Set[str],
) -> List[Hallazgo]:
    """
    En un ALTER la tabla (y sus columnas previas) ya existen y seguramente ya
    están documentadas. Agregarles de nuevo la descripción no es un error del
    diccionario, pero sp_addextendedproperty fallaría si ya la tienen: se
    pide validar.
    """
    if tipo_sentencia != "ALTER":
        return []
    nuevas = {c.upper() for c in columnas_agregadas}
    full = _nombre_completo(esquema, nombre_tabla)
    hallazgos = []
    for ll in llamadas:
        if ll.operacion != "add" or not _es_descripcion(ll):
            continue
        if _es_de_tabla(ll):
            hallazgos.append(_hallazgo(
                ll.linea, "DOCUMENTACION_EXISTENTE_EN_ALTER",
                f"Se agrega la descripción de la tabla {full}, pero es un ALTER TABLE: la tabla ya existe. "
                f"Valide que no esté documentada; si ya tiene descripción, quite esta sentencia o use "
                f"sp_updateextendedproperty.",
            ))
        elif _es_de_columna(ll) and ll.texto("level2name").upper() not in nuevas:
            hallazgos.append(_hallazgo(
                ll.linea, "DOCUMENTACION_EXISTENTE_EN_ALTER",
                f"Se agrega la descripción de la columna {ll.texto('level2name')}, que no es nueva en este "
                f"ALTER TABLE. Valide que no esté documentada; si ya lo está, quite esta sentencia o use "
                f"sp_updateextendedproperty.",
            ))
    return hallazgos


def _sugerencia_columna(nombre: str, columnas_reales: Set[str]) -> str:
    """' ¿Quiso decir bActivo?' si hay una columna real con nombre parecido."""
    por_clave = {c.upper(): c for c in columnas_reales}
    parecidas = difflib.get_close_matches(nombre.upper(), list(por_clave), n=1, cutoff=0.75)
    if parecidas:
        return f" ¿Quiso decir '{por_clave[parecidas[0]]}'?"
    return " Revise si el nombre está mal escrito."


def _validar_columnas_inexistentes(
    columnas_reales: Set[str], llamadas: List[LlamadaPropiedad], tipo_sentencia: str, nombre_tabla: str
) -> List[Hallazgo]:
    """
    En un CREATE, documentar una columna que no existe suele ser un error de
    tipeo. En un ALTER no se valida: la tabla tiene columnas previas que el
    script no muestra.
    """
    if tipo_sentencia != "CREATE":
        return []
    reales = {c.upper() for c in columnas_reales}
    return [
        _hallazgo(
            ll.linea, "COLUMNA_NO_EXISTE",
            f"Se documenta la columna '{ll.texto('level2name')}', pero no existe en la tabla "
            f"{nombre_tabla}.{_sugerencia_columna(ll.texto('level2name'), columnas_reales)}",
        )
        for ll in llamadas
        if _es_de_columna(ll) and ll.texto("level2name").upper() not in reales
    ]


def _validar_duplicados(llamadas: List[LlamadaPropiedad]) -> List[Hallazgo]:
    """
    Agregar dos veces la misma descripción falla en SQL Server ("property
    already exists"). Solo aplica a sp_addextendedproperty.
    """
    vistos: Dict[Tuple[str, str], int] = {}
    hallazgos = []
    for ll in llamadas:
        if ll.operacion != "add" or not _es_descripcion(ll):
            continue
        if _es_de_columna(ll):
            clave = ("columna", ll.texto("level2name").upper())
            objeto = f"la columna {ll.texto('level2name')}"
        elif _es_de_tabla(ll):
            clave = ("tabla", ll.texto("level1name").upper())
            objeto = f"la tabla {ll.texto('level1name')}"
        else:
            continue
        if clave in vistos:
            hallazgos.append(_hallazgo(
                ll.linea, "DOCUMENTACION_DUPLICADA",
                f"{objeto[0].upper()}{objeto[1:]} está documentada dos veces (la primera en la línea "
                f"{vistos[clave]}). Elimine una: SQL Server rechaza la repetida.",
            ))
        else:
            vistos[clave] = ll.linea
    return hallazgos


def _validar_descripcion_tabla(llamadas: List[LlamadaPropiedad]) -> List[Hallazgo]:
    """
    La descripción de la tabla debe explicar su propósito. Se marca cuando es
    idéntica a la de una columna (copiar y pegar) o cuando describe un
    identificador en lugar de la tabla.
    """
    descripciones_columnas = {
        _normalizar_texto(ll.texto("value")): ll.texto("level2name")
        for ll in llamadas
        if _es_de_columna(ll) and _es_descripcion(ll) and ll.texto("value")
    }
    hallazgos = []
    for ll in llamadas:
        if not (_es_de_tabla(ll) and _es_descripcion(ll) and ll.texto("value")):
            continue
        descripcion = _normalizar_texto(ll.texto("value"))
        if descripcion in descripciones_columnas:
            hallazgos.append(_hallazgo(
                ll.linea, "DESCRIPCION_TABLA_INADECUADA",
                f"La descripción de la tabla es la misma que la de la columna "
                f"{descripciones_columnas[descripcion]}. Escriba una descripción que explique para qué "
                f"sirve la tabla.",
            ))
        elif descripcion.startswith("identificador"):
            hallazgos.append(_hallazgo(
                ll.linea, "DESCRIPCION_TABLA_INADECUADA",
                "La descripción de la tabla parece de una columna (empieza con 'Identificador'). Escriba para qué sirve la tabla.",
            ))
    return hallazgos


def _validar_ortografia(
    llamadas: List[LlamadaPropiedad],
    esquema: Optional[str],
    nombre_tabla: str,
    columnas_reales: Set[str],
) -> List[Hallazgo]:
    """Palabras mal escritas en las descripciones (sin exigir tildes)."""
    nombres_objeto = {esquema or "", nombre_tabla, *columnas_reales}
    hallazgos = []
    for ll in llamadas:
        if not (_es_descripcion(ll) and ll.texto("value")):
            continue
        if _es_de_columna(ll):
            objeto = f"de la columna {ll.texto('level2name')}"
        elif _es_de_tabla(ll):
            objeto = f"de la tabla {_nombre_completo(esquema, nombre_tabla)}"
        else:
            continue
        errores = palabras_mal_escritas(ll.texto("value"), nombres_objeto | {ll.texto("level2name")})
        if not errores:
            continue
        detalle = ", ".join(
            f"'{palabra}' (¿quiso decir '{opciones[0]}'?)" if opciones else f"'{palabra}'"
            for palabra, opciones in errores
        )
        texto = "una palabra mal escrita" if len(errores) == 1 else "palabras mal escritas"
        hallazgos.append(_hallazgo(
            ll.linea, "ERROR_ORTOGRAFICO",
            f"La descripción {objeto} tiene {texto}: {detalle}. Corríjala.",
        ))
    return hallazgos


def _validar_descripciones_vacias(llamadas: List[LlamadaPropiedad]) -> List[Hallazgo]:
    return [
        _hallazgo(
            ll.linea, "DESCRIPCION_COLUMNA_VACIA",
            f"La columna {ll.texto('level2name')} está en el diccionario, pero su descripción está vacía. Escriba qué información guarda.",
        )
        for ll in llamadas
        if _es_de_columna(ll) and _es_descripcion(ll) and ll.tiene("value") and ll.texto("value") == ""
    ]


def _validar_valores_sin_comillas(llamadas: List[LlamadaPropiedad]) -> List[Hallazgo]:
    """Estándar del equipo: los nombres van como N'...'. Un hallazgo por sentencia."""
    hallazgos = []
    for ll in llamadas:
        sin_comillas = [
            f"@{p}={ll.argumentos[p].crudo}"
            for p in _PARAMETROS_DE_NOMBRE
            if ll.tiene(p) and not ll.argumentos[p].entre_comillas
        ]
        if sin_comillas:
            hallazgos.append(_hallazgo(
                ll.linea, "VALOR_SIN_COMILLAS",
                f"Los nombres {', '.join(sin_comillas)} no están entre comillas. Escríbalos como N'...'.",
            ))
    return hallazgos


def _validar_alter_sin_diccionario(
    tipo_sentencia: str, llamadas: List[LlamadaPropiedad], esquema: Optional[str], nombre_tabla: str
) -> List[Hallazgo]:
    if tipo_sentencia == "ALTER" and not llamadas:
        full = _nombre_completo(esquema, nombre_tabla)
        return [_hallazgo(
            1, "ALTER_SIN_DICCIONARIO",
            f"Se modifica la tabla {full} (ALTER TABLE), pero no se pegó ningún diccionario. "
            f"Si agrega o cambia columnas, documéntelas.",
        )]
    return []


# ---------------------------------------------------------------------------
# ORQUESTADOR
# ---------------------------------------------------------------------------

def verificar_diccionario_tablas(texto_tabla: str, texto_diccionario: str) -> List[Hallazgo]:
    """Compara CREATE/ALTER TABLE con el diccionario de datos."""
    esquema, nombre_tabla = extraer_esquema_y_nombre(texto_tabla)
    if nombre_tabla is None:
        return []

    tipo_sentencia = extraer_tipo_sentencia(texto_tabla)
    columnas_reales = extraer_columnas(texto_tabla)
    columnas_agregadas, _ = extraer_columnas_alter(texto_tabla)
    llamadas = leer_propiedades_extendidas(texto_diccionario)

    # CREATE: la tabla es nueva y todo debe documentarse.
    # ALTER: la tabla ya existe; solo se exigen las columnas nuevas (ADD).
    es_create = tipo_sentencia == "CREATE"
    columnas_requeridas = columnas_reales if es_create else columnas_agregadas

    hallazgos: List[Hallazgo] = []
    hallazgos += _validar_sintaxis(llamadas)
    hallazgos += _validar_parametros(llamadas)
    hallazgos += _validar_alter_sin_diccionario(tipo_sentencia, llamadas, esquema, nombre_tabla)
    if es_create:
        hallazgos += _validar_tabla_documentada(llamadas, esquema, nombre_tabla)
    hallazgos += _validar_descripcion_tabla(llamadas)
    hallazgos += _validar_columnas_faltantes(columnas_requeridas, llamadas, tipo_sentencia, esquema, nombre_tabla)
    hallazgos += _validar_columnas_inexistentes(columnas_reales, llamadas, tipo_sentencia, nombre_tabla)
    hallazgos += _validar_documentacion_existente_en_alter(
        llamadas, tipo_sentencia, esquema, nombre_tabla, columnas_agregadas
    )
    hallazgos += _validar_duplicados(llamadas)
    hallazgos += _validar_esquema(llamadas, esquema)
    hallazgos += _validar_nombre_tabla(llamadas, nombre_tabla)
    hallazgos += _validar_descripciones_vacias(llamadas)
    hallazgos += _validar_ortografia(llamadas, esquema, nombre_tabla, columnas_reales)
    hallazgos += _validar_valores_sin_comillas(llamadas)

    # Las reglas desactivadas en el catálogo no se reportan.
    return [h for h in hallazgos if REGLAS_DICCIONARIO_TABLAS[h.regla].activo]
