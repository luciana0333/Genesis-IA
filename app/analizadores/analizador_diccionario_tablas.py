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


# ---------------------------------------------------------------------------
# EXTRACCION - leer la "realidad" (la tabla)
# ---------------------------------------------------------------------------

def extraer_tipo_sentencia(texto_sql: str) -> str:
    """Determina si la sentencia es CREATE TABLE o ALTER TABLE."""
    if re.search(r"\bALTER\s+TABLE\b", texto_sql, re.IGNORECASE):
        return "ALTER"
    if re.search(r"\bCREATE\s+TABLE\b", texto_sql, re.IGNORECASE):
        return "CREATE"
    return "DESCONOCIDO"


def extraer_esquema_y_nombre(texto_sql: str) -> Tuple[Optional[str], Optional[str]]:
    """Devuelve (esquema, nombre) de la tabla, o (None, None)."""
    # Intenta schema.nombre primero
    m = re.search(
        rf"(?:CREATE|ALTER)\s+TABLE\s+({_IDENTIFICADOR_SQL})\.({_IDENTIFICADOR_SQL})",
        texto_sql,
        re.IGNORECASE,
    )
    if m:
        return _limpiar_identificador_sql(m.group(1)), _limpiar_identificador_sql(m.group(2))

    # Si no tiene esquema, acepta solo el nombre de la tabla
    m2 = re.search(rf"(?:CREATE|ALTER)\s+TABLE\s+({_IDENTIFICADOR_SQL})", texto_sql, re.IGNORECASE)
    if m2:
        return None, _limpiar_identificador_sql(m2.group(1))
    return None, None


def extraer_columnas(texto_sql: str) -> Set[str]:
    """
    Extrae columnas reales declaradas en CREATE TABLE o ALTER TABLE.
    En alter, captura columnas nuevas o columnas afectadas por ALTER COLUMN.
    """
    texto = texto_sql.strip()
    if not texto:
        return set()

    columnas: Set[str] = set()

    # CREATE TABLE ... ( ... )
    # Captura el contenido entre los paréntesis externos del CREATE/ALTER TABLE
    m_name = re.search(
        rf"(?:CREATE|ALTER)\s+TABLE\s+{_IDENTIFICADOR_SQL}(?:\.{_IDENTIFICADOR_SQL})?\s*\(",
        texto,
        re.IGNORECASE,
    )
    if m_name:
        start_idx = m_name.end() - 1  # posición del primer '('
        depth = 0
        end_idx = None
        for i in range(start_idx + 1, len(texto)):
            ch = texto[i]
            if ch == '(':
                depth += 1
            elif ch == ')':
                if depth == 0:
                    end_idx = i
                    break
                depth -= 1
        if end_idx is not None:
            contenido = texto[start_idx + 1:end_idx]
        else:
            contenido = texto[start_idx + 1:]
        # Separar por comas respetando paréntesis y tomar el primer token de cada segmento
        segmentos = []
        buf = []
        depth = 0
        for ch in contenido:
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth = max(depth - 1, 0)
            if ch == ',' and depth == 0:
                segmentos.append(''.join(buf))
                buf = []
            else:
                buf.append(ch)
        if buf:
            segmentos.append(''.join(buf))

        for seg in segmentos:
            mcol = re.match(rf"\s*({_IDENTIFICADOR_SQL})", seg)
            if mcol:
                # Se conserva el nombre tal cual se escribió para mostrarlo en los mensajes.
                name = _limpiar_identificador_sql(mcol.group(1))
                if name.upper() not in {"CONSTRAINT", "PRIMARY", "FOREIGN", "UNIQUE", "CHECK", "INDEX", "KEY", "ALTER", "ADD", "DROP"}:
                    columnas.add(name)

    # ALTER TABLE ... ADD cNombre ...
    # ALTER TABLE ... ALTER COLUMN cNombre ...
    matches_alter = re.findall(
        rf"(?:ADD|ALTER)\s+COLUMN\s+({_IDENTIFICADOR_SQL})|ADD\s+({_IDENTIFICADOR_SQL})\s+",
        texto,
        re.IGNORECASE
    )
    for grupo in matches_alter:
        for item in grupo:
            if item:
                columnas.add(_limpiar_identificador_sql(item))

    return columnas


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
    En un CREATE todas las columnas deben estar documentadas. En un ALTER solo
    se exige documentar las columnas agregadas o modificadas.
    """
    documentadas = _columnas_documentadas(llamadas)
    full = _nombre_completo(esquema, nombre_tabla)
    # Una sola entrada por columna (sin distinguir mayúsculas), con su nombre original.
    reales = {c.upper(): c for c in sorted(columnas_reales)}
    hallazgos = []
    for clave in sorted(set(reales) - documentadas):
        columna = reales[clave]
        if tipo_sentencia == "ALTER":
            mensaje = (
                f"La columna {columna} agregada en el ALTER TABLE de {full} no se encuentra documentada. "
                f"Valide si debe agregarse al diccionario."
            )
        else:
            mensaje = f"La columna {columna} no se encuentra documentada. Agréguela al diccionario con su descripción."
        hallazgos.append(_hallazgo(1, "COLUMNA_FALTANTE", mensaje))
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
    llamadas = leer_propiedades_extendidas(texto_diccionario)

    hallazgos: List[Hallazgo] = []
    hallazgos += _validar_sintaxis(llamadas)
    hallazgos += _validar_parametros(llamadas)
    hallazgos += _validar_alter_sin_diccionario(tipo_sentencia, llamadas, esquema, nombre_tabla)
    hallazgos += _validar_tabla_documentada(llamadas, esquema, nombre_tabla)
    hallazgos += _validar_descripcion_tabla(llamadas)
    hallazgos += _validar_columnas_faltantes(columnas_reales, llamadas, tipo_sentencia, esquema, nombre_tabla)
    hallazgos += _validar_columnas_inexistentes(columnas_reales, llamadas, tipo_sentencia, nombre_tabla)
    hallazgos += _validar_duplicados(llamadas)
    hallazgos += _validar_esquema(llamadas, esquema)
    hallazgos += _validar_nombre_tabla(llamadas, nombre_tabla)
    hallazgos += _validar_descripciones_vacias(llamadas)
    hallazgos += _validar_valores_sin_comillas(llamadas)

    # Las reglas desactivadas en el catálogo no se reportan.
    return [h for h in hallazgos if REGLAS_DICCIONARIO_TABLAS[h.regla].activo]
