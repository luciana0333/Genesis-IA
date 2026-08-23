# -*- coding: utf-8 -*-
"""
analizador_diccionario_tablas.py
------------------------------
Analiza el diccionario de tablas (sp_addextendedproperty) y compara la
"realidad" (CREATE/ALTER TABLE) contra la "documentacion".
"""

import re
from typing import List, Set, Tuple, Dict, Optional

from app.modelos.hallazgo import Hallazgo, Severidad, OrigenAnalisis


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
                name = _limpiar_identificador_sql(mcol.group(1)).upper()
                if name not in {"CONSTRAINT", "PRIMARY", "FOREIGN", "UNIQUE", "CHECK", "INDEX", "KEY", "ALTER", "ADD", "DROP"}:
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
                columnas.add(_limpiar_identificador_sql(item).upper())

    return columnas


# ---------------------------------------------------------------------------
# EXTRACCION - leer la "documentacion" (diccionario)
# ---------------------------------------------------------------------------

def extraer_llamadas_extendedproperty(texto_diccionario: str) -> List[Tuple[int, Dict[str, str]]]:
    """Extrae llamadas a sp_addextendedproperty para tablas/columnas."""
    llamadas = []
    patron = re.compile(
        r"EXEC(?:UTE)?\s+sys\.sp_(?:add|update)extendedproperty\s*(.*?)(?=\bGO\b|\Z)",
        re.IGNORECASE | re.DOTALL
    )
    for m in patron.finditer(texto_diccionario):
        cuerpo = m.group(1)
        args = {}
        for arg_m in re.finditer(r"@(\w+)\s*=\s*(N?'[^']*'|[\w@]+)", cuerpo):
            args[arg_m.group(1).lower()] = arg_m.group(2)
        llamadas.append((m.start(), args))
    return llamadas


def _limpiar_valor(valor: str) -> str:
    """Quita comillas y el prefijo N de un valor tipo N'texto'."""
    if not isinstance(valor, str):
        return ""
    valor = valor.strip()
    if valor.startswith("N'") and valor.endswith("'"):
        return valor[2:-1]
    if valor.startswith("'") and valor.endswith("'"):
        return valor[1:-1]
    return valor


def _numero_linea(texto: str, posicion: int) -> int:
    return texto.count("\n", 0, posicion) + 1


# ---------------------------------------------------------------------------
# VALIDACIONES
# ---------------------------------------------------------------------------

def _validar_tabla_documentada(
    llamadas: List[Tuple[int, Dict[str, str]]],
    esquema: str,
    nombre_tabla: str
) -> List[Hallazgo]:
    """Debe existir una descripcion valida a nivel TABLE."""
    tabla_doc = []
    for _, args in llamadas:
        level1type = _limpiar_valor(args.get("level1type", "")).upper()
        level2type = _limpiar_valor(args.get("level2type", "")).upper()
        if level1type.strip() == "TABLE" and not level2type:
            nombre_doc = _limpiar_valor(args.get("level1name", "")).upper()
            if nombre_doc == nombre_tabla.upper():
                valor = _limpiar_valor(args.get("value", ""))
                if valor != "":
                    tabla_doc.append(args)
    if not tabla_doc:
        full = _nombre_completo(esquema, nombre_tabla)
        return [Hallazgo(
            linea=1,
            origen=OrigenAnalisis.DICCIONARIO,
            severidad=Severidad.MEDIO,
            regla="TABLA_SIN_DESCRIPCION",
            mensaje=f"La tabla {full} no tiene una descripcion valida a nivel TABLE en el diccionario."
        )]
    return []


def _validar_esquema(
    llamadas: List[Tuple[int, Dict[str, str]]],
    esquema_real: str,
    texto_diccionario: str
) -> List[Hallazgo]:
    hallazgos = []
    # Si no conocemos el esquema real (tabla sin esquema en SQL), no validar esquema
    if not esquema_real:
        return hallazgos
    for pos, args in llamadas:
        if "level0name" in args:
            valor = _limpiar_valor(args["level0name"])
            if valor and valor.lower() != esquema_real.lower():
                hallazgos.append(Hallazgo(
                    linea=_numero_linea(texto_diccionario, pos),
                    origen=OrigenAnalisis.DICCIONARIO,
                    severidad=Severidad.ALTO,
                    regla="ESQUEMA_NO_COINCIDE",
                    mensaje=f"El esquema documentado (@level0name='{valor}') no coincide con "
                            f"el esquema real de la tabla ('{esquema_real}')."
                ))
    return hallazgos


def _validar_nombre_tabla(
    llamadas: List[Tuple[int, Dict[str, str]]],
    nombre_tabla: str,
    texto_diccionario: str
) -> List[Hallazgo]:
    hallazgos = []
    for pos, args in llamadas:
        level1type = args.get("level1type", "").upper()
        if "TABLE" in level1type and "level1name" in args:
            valor = _limpiar_valor(args["level1name"]).upper()
            if valor != nombre_tabla.upper():
                hallazgos.append(Hallazgo(
                    linea=_numero_linea(texto_diccionario, pos),
                    origen=OrigenAnalisis.DICCIONARIO,
                    severidad=Severidad.ALTO,
                    regla="NOMBRE_TABLA_NO_COINCIDE",
                    mensaje=f"@level1name='{valor}' no coincide con el nombre real de la tabla "
                            f"({nombre_tabla})."
                ))
    return hallazgos


def _validar_columnas_faltantes(
    columnas_reales: Set[str],
    llamadas: List[Tuple[int, Dict[str, str]]],
    tipo_sentencia: str,
    esquema: str,
    nombre_tabla: str
) -> List[Hallazgo]:
    """
    Compara columnas reales vs documentadas. Para ALTER, solo alerta si una
    columna nueva no tiene documentacion.
    """
    hallazgos = []
    columnas_documentadas = set()
    for _, args in llamadas:
        if "level2type" in args and "COLUMN" in args.get("level2type", "").upper():
            nombre_col = _limpiar_valor(args.get("level2name", "")).upper()
            if nombre_col:
                columnas_documentadas.add(nombre_col)

    faltantes = {c.upper() for c in columnas_reales} - columnas_documentadas
    for col in sorted(faltantes):
        full = _nombre_completo(esquema, nombre_tabla)
        if tipo_sentencia == "ALTER":
            mensaje = (
                f"La columna {col} fue agregada en el ALTER TABLE de {full} "
                f"pero no existe descripcion en el diccionario. Validar si realmente debe documentarse."
            )
        else:
            mensaje = (
                f"La columna {col} no tiene documentacion en el diccionario de la tabla {full}."
            )
        hallazgos.append(Hallazgo(
            linea=1,
            origen=OrigenAnalisis.DICCIONARIO,
            severidad=Severidad.MEDIO,
            regla="COLUMNA_SIN_DESCRIPCION",
            mensaje=mensaje
        ))
    return hallazgos


def _validar_descripciones_vacias(
    llamadas: List[Tuple[int, Dict[str, str]]],
    texto_diccionario: str
) -> List[Hallazgo]:
    hallazgos = []
    for pos, args in llamadas:
        if "COLUMN" in args.get("level2type", "").upper() and "value" in args:
            valor = _limpiar_valor(args["value"])
            nombre_col = _limpiar_valor(args.get("level2name", "?"))
            if valor == "":
                hallazgos.append(Hallazgo(
                    linea=_numero_linea(texto_diccionario, pos),
                    origen=OrigenAnalisis.DICCIONARIO,
                    severidad=Severidad.MEDIO,
                    regla="DESCRIPCION_COLUMNA_VACIA",
                    mensaje=f"La columna {nombre_col} tiene descripcion vacia en el diccionario."
                ))
    return hallazgos


def _validar_valores_sin_comillas(
    llamadas: List[Tuple[int, Dict[str, str]]],
    texto_diccionario: str
) -> List[Hallazgo]:
    hallazgos = []
    for pos, args in llamadas:
        for clave in ("level0name", "level1name", "level2name"):
            if clave in args:
                valor = args[clave]
                if not (valor.startswith("N'") or valor.startswith("'")):
                    hallazgos.append(Hallazgo(
                        linea=_numero_linea(texto_diccionario, pos),
                        origen=OrigenAnalisis.DICCIONARIO,
                        severidad=Severidad.CRITICO,
                        regla="VALOR_SIN_COMILLAS",
                        mensaje=f"@{clave}={valor} no esta entre comillas (N'...')."
                    ))
    return hallazgos


def _validar_alter_sin_diccionario(
    tipo_sentencia: str,
    llamadas: List[Tuple[int, Dict[str, str]]],
    esquema: str,
    nombre_tabla: str
) -> List[Hallazgo]:
    if tipo_sentencia == "ALTER" and not llamadas:
        full = _nombre_completo(esquema, nombre_tabla)
        return [Hallazgo(
            linea=1,
            origen=OrigenAnalisis.DICCIONARIO,
            severidad=Severidad.BAJO,
            regla="ALTER_SIN_DICCIONARIO",
            mensaje=f"Este ALTER TABLE ({full}) no tiene diccionario asociado. Verifique si la nueva columna ya estaba documentada previamente o si falta documentarla."
        )]
    return []


# ---------------------------------------------------------------------------
# ORQUESTADOR
# ---------------------------------------------------------------------------

def verificar_diccionario_tablas(
    texto_tabla: str,
    texto_diccionario: str
) -> List[Hallazgo]:
    """Compara CREATE/ALTER TABLE con el diccionario de datos."""
    hallazgos: List[Hallazgo] = []

    esquema, nombre_tabla = extraer_esquema_y_nombre(texto_tabla)
    if nombre_tabla is None:
        return hallazgos

    tipo_sentencia = extraer_tipo_sentencia(texto_tabla)
    columnas_reales = extraer_columnas(texto_tabla)
    llamadas = extraer_llamadas_extendedproperty(texto_diccionario)

    hallazgos += _validar_alter_sin_diccionario(tipo_sentencia, llamadas, esquema, nombre_tabla)

    hallazgos += _validar_tabla_documentada(llamadas, esquema, nombre_tabla)
    hallazgos += _validar_columnas_faltantes(columnas_reales, llamadas, tipo_sentencia, esquema, nombre_tabla)
    hallazgos += _validar_esquema(llamadas, esquema, texto_diccionario)
    hallazgos += _validar_nombre_tabla(llamadas, nombre_tabla, texto_diccionario)
    hallazgos += _validar_descripciones_vacias(llamadas, texto_diccionario)
    hallazgos += _validar_valores_sin_comillas(llamadas, texto_diccionario)

    return hallazgos
