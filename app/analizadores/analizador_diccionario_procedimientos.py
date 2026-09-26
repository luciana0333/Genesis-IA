# -*- coding: utf-8 -*-
"""
diccionario.py
----------------
Analizador especializado en el diccionario de datos
(sp_addextendedproperty) de un procedimiento almacenado.

Recibe DOS textos por separado, tal como se manejan en la revision real:
  - texto_procedimiento: el CREATE/ALTER PROCEDURE con sus parametros
  - texto_diccionario: el script de sp_addextendedproperty que lo documenta

Compara la "realidad" (procedimiento) contra la "documentacion"
(diccionario) y reporta discrepancias.
"""

import re
from typing import List, Set, Tuple, Dict, Optional

from app.analizadores.ortografia import palabras_mal_escritas
from app.analizadores.propiedades_extendidas import como_llamadas_crudas, leer_propiedades_extendidas
from app.modelos.hallazgo import Hallazgo, Severidad, OrigenAnalisis
from app.reglas.reglas_diccionario_procedimientos import REGLAS_DICCIONARIO_PROCEDIMIENTOS


# ---------------------------------------------------------------------------
# EXTRACCION - leer la "realidad" (el procedimiento)
# ---------------------------------------------------------------------------

def extraer_parametros(texto_procedimiento: str) -> Set[str]:
    """Extrae los parametros declarados en CREATE/ALTER PROCEDURE."""
    patron = re.compile(
        r"(?:CREATE|ALTER)\s+PROCEDURE\s+[\w\.]+\s*\(?(.*?)\)?\s*AS\b",
        re.IGNORECASE | re.DOTALL
    )
    coincidencia = patron.search(texto_procedimiento)
    if not coincidencia:
        coincidencia = re.search(
            r"(?:CREATE|ALTER)\s+PROCEDURE\s+[\w\.]+\s*\((.*?)\)\s*(?:;|\Z)",
            texto_procedimiento,
            re.IGNORECASE | re.DOTALL,
        )
    if not coincidencia:
        return set()
    bloque_parametros = coincidencia.group(1)
    return set(re.findall(r"@\w+", bloque_parametros))


def extraer_tipo_sentencia(texto_procedimiento: str) -> str:
    """Determina si el procedimiento es un CREATE o un ALTER."""
    if re.search(r"\bALTER\s+PROCEDURE\b", texto_procedimiento, re.IGNORECASE):
        return "ALTER"
    if re.search(r"\bCREATE\s+PROCEDURE\b", texto_procedimiento, re.IGNORECASE):
        return "CREATE"
    return "DESCONOCIDO"


def extraer_esquema_y_nombre(texto_procedimiento: str) -> Tuple[Optional[str], Optional[str]]:
    """Devuelve (esquema, nombre) del procedimiento, o (None, None)."""
    m = re.search(
        r"(?:CREATE|ALTER)\s+PROCEDURE\s+([\w]+)\.([\w]+)",
        texto_procedimiento, re.IGNORECASE
    )
    if m:
        return m.group(1), m.group(2)
    return None, None


# ---------------------------------------------------------------------------
# EXTRACCION - leer la "documentacion" (el script del diccionario)
# ---------------------------------------------------------------------------

def extraer_llamadas_extendedproperty(texto_diccionario: str) -> List[Tuple[int, Dict[str, str]]]:
    """
    Devuelve una lista de (posicion_en_texto, argumentos) por cada
    llamada a sp_addextendedproperty / sp_updateextendedproperty,
    leidas del SCRIPT DEL DICCIONARIO (no del procedimiento).
    """
    # El lector compartido reconoce cada sentencia aunque no haya GO ni ";",
    # y respeta cadenas y comentarios.
    return como_llamadas_crudas(leer_propiedades_extendidas(texto_diccionario))


def _limpiar_valor(valor: str) -> str:
    """Quita comillas y el prefijo N de un valor tipo N'texto' -> texto."""
    return valor.replace("N'", "").replace("'", "").strip()


def _es_sentencia_de_procedimiento(args: Dict[str, str]) -> bool:
    """La llamada documenta al procedimiento en sí (no a un PARAMETER)."""
    level1type = args.get("level1type", "").upper()
    level2type = args.get("level2type", "").upper()
    return "PROCEDURE" in level1type and "PARAMETER" not in level2type


def _es_descripcion_procedimiento_valida(args: Dict[str, str]) -> bool:
    """Indica si la llamada documenta la descripcion del procedimiento,
    excluyendo las entradas de PARAMETER.
    """
    level1type = args.get("level1type", "").upper()
    level2type = args.get("level2type", "").upper()
    if "PROCEDURE" not in level1type:
        return False
    if "PARAMETER" in level2type:
        return False
    return _limpiar_valor(args.get("value", "")) != ""


def _numero_linea(texto: str, posicion: int) -> int:
    return texto.count("\n", 0, posicion) + 1


# ---------------------------------------------------------------------------
# VALIDACIONES INDIVIDUALES
# ---------------------------------------------------------------------------

def _validar_esquema(
    llamadas: List[Tuple[int, Dict[str, str]]],
    esquema_real: str,
    texto_diccionario: str
) -> List[Hallazgo]:
    """El @level0name del diccionario debe coincidir con el esquema real
    del procedimiento (ej. Dbo, CCE, RRHH)."""
    hallazgos = []
    for pos, args in llamadas:
        if "level0name" in args:
            valor = _limpiar_valor(args["level0name"])
            if valor and valor.lower() != esquema_real.lower():
                hallazgos.append(Hallazgo(
                    linea=_numero_linea(texto_diccionario, pos),
                    origen=OrigenAnalisis.DICCIONARIO,
                    severidad=Severidad.ALTO,
                    regla="ESQUEMA_NO_COINCIDE",
                    mensaje=f"El esquema no coincide: el diccionario dice '{valor}', pero el "
                            f"procedimiento está en '{esquema_real}'. Corrija @level0name."
                ))
    return hallazgos


def _validar_descripciones_vacias(
    llamadas: List[Tuple[int, Dict[str, str]]],
    texto_diccionario: str,
) -> List[Hallazgo]:
    """Un parametro puede estar 'documentado' pero con @value vacio ('') -
    eso no cuenta como documentacion real."""
    hallazgos = []
    for pos, args in llamadas:
        es_parametro = "PARAMETER" in args.get("level2type", "").upper()
        if es_parametro and "value" in args:
            valor_desc = _limpiar_valor(args["value"])
            nombre_param = _limpiar_valor(args.get("level2name", "?"))
            if valor_desc == "":
                hallazgos.append(Hallazgo(
                    linea=_numero_linea(texto_diccionario, pos),
                    origen=OrigenAnalisis.DICCIONARIO,
                    severidad=Severidad.MEDIO,
                    regla="DESCRIPCION_VACIA",
                    mensaje=f"El parámetro {nombre_param} no tiene una descripción: está "
                            f"documentado, pero @value está vacío. Escriba para qué se usa."
                ))
    return hallazgos


def _validar_parametros_faltantes(
    parametros_reales: Set[str],
    llamadas: List[Tuple[int, Dict[str, str]]],
    tipo_sentencia: str,
    esquema: str,
    nombre_proc: str
) -> List[Hallazgo]:
    """
    Compara parametros reales vs documentados. El mensaje cambia segun
    si es CREATE o ALTER, y segun si el diccionario tiene o no llamadas.
    """
    hallazgos = []

    # SQL Server no distingue mayúsculas en los nombres: @nClienteId = @NCLIENTEID.
    parametros_documentados = set()
    for _, args in llamadas:
        if "level2name" in args and "PARAMETER" in args.get("level2type", "").upper():
            parametros_documentados.add(_limpiar_valor(args["level2name"]).upper())

    faltantes = [p for p in parametros_reales if p.upper() not in parametros_documentados]

    for p in sorted(faltantes, key=str.upper):
        if tipo_sentencia == "ALTER":
            # El procedimiento ya existía: el parámetro puede estar documentado
            # de antes. No es error; se pide validar.
            hallazgos.append(Hallazgo(
                linea=1,
                origen=OrigenAnalisis.DICCIONARIO,
                severidad=Severidad.BAJO,
                regla="VALIDAR_DOCUMENTACION_ALTER",
                mensaje=(
                    f"Es un ALTER PROCEDURE y el parámetro {p} no está en el diccionario. "
                    f"Valide si ya estaba documentado; si es nuevo, agréguelo con su descripción."
                ),
            ))
            continue

        # En un CREATE el procedimiento es nuevo: todo debe documentarse.
        hallazgos.append(Hallazgo(
            linea=1,
            origen=OrigenAnalisis.DICCIONARIO,
            severidad=Severidad.ALTO,
            regla="PARAMETRO_FALTANTE",
            mensaje=(
                f"El parámetro {p} no se encuentra documentado. Agréguelo al "
                f"diccionario con su descripción."
            ),
        ))

    return hallazgos


def _validar_alter_sin_diccionario(
    tipo_sentencia: str,
    llamadas: List[Tuple[int, Dict[str, str]]],
    esquema: str,
    nombre_proc: str
) -> List[Hallazgo]:
    """
    Caso especial: es un ALTER y el script de diccionario esta vacio
    (no se proporciono, o no tiene ninguna llamada a sp_addextendedproperty).
    No asumimos error - pedimos validacion manual.
    """
    if tipo_sentencia == "ALTER" and not llamadas:
        return [Hallazgo(
            linea=1,
            origen=OrigenAnalisis.DICCIONARIO,
            severidad=Severidad.BAJO,
            regla="ALTER_SIN_DICCIONARIO",
            mensaje=(
                f"Se modifica el procedimiento {esquema}.{nombre_proc} (ALTER), pero no "
                f"se pegó ningún diccionario. Si agrega o cambia parámetros, "
                f"documéntelos."
            )
        )]
    return []


def _validar_nombre_procedimiento(
    llamadas: List[Tuple[int, Dict[str, str]]],
    nombre_proc: str,
    texto_diccionario: str
) -> List[Hallazgo]:
    """El @level1name debe coincidir exactamente con el nombre real."""
    hallazgos = []
    for pos, args in llamadas:
        if "level1name" in args and "PROCEDURE" in args.get("level1type", "").upper():
            valor = _limpiar_valor(args["level1name"])
            if valor.lower() != nombre_proc.lower():
                hallazgos.append(Hallazgo(
                    linea=_numero_linea(texto_diccionario, pos),
                    origen=OrigenAnalisis.DICCIONARIO,
                    severidad=Severidad.ALTO,
                    regla="NOMBRE_NO_COINCIDE",
                    mensaje=f"El nombre del procedimiento no coincide: el diccionario dice "
                            f"'{valor}', pero el procedimiento se llama '{nombre_proc}'. "
                            f"Corrija @level1name."
                ))
    return hallazgos


def _validar_valores_sin_comillas(
    llamadas: List[Tuple[int, Dict[str, str]]],
    texto_diccionario: str
) -> List[Hallazgo]:
    """Los valores de nombre deben ir entre comillas N'...'."""
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
                        mensaje=f"El nombre @{clave}={valor} no está entre comillas. "
                                f"Escríbalo como N'...'."
                    ))
    return hallazgos


def _validar_procedimiento_documentado(
    llamadas: List[Tuple[int, Dict[str, str]]],
    esquema: str,
    nombre_proc: str,
    tipo_sentencia: str,
) -> List[Hallazgo]:
    """Debe existir al menos una descripcion valida a nivel PROCEDURE,
    no solo descripciones de PARAMETER. Es alto en un CREATE.
    """
    if any(_es_descripcion_procedimiento_valida(a) for _, a in llamadas):
        return []

    # La sentencia existe pero con @value vacío: está documentado, sin descripción.
    if any(_es_sentencia_de_procedimiento(a) for _, a in llamadas):
        return [Hallazgo(
            linea=1,
            origen=OrigenAnalisis.DICCIONARIO,
            severidad=Severidad.MEDIO,
            regla="DESCRIPCION_PROCEDIMIENTO_VACIA",
            mensaje=f"El procedimiento {esquema}.{nombre_proc} está documentado, pero no "
                    f"tiene una descripción (@value está vacío). Escriba para qué sirve "
                    f"el procedimiento."
        )]

    if tipo_sentencia == "ALTER":
        return [Hallazgo(
            linea=1,
            origen=OrigenAnalisis.DICCIONARIO,
            severidad=Severidad.BAJO,
            regla="VALIDAR_DOCUMENTACION_ALTER",
            mensaje=f"Es un ALTER PROCEDURE y el diccionario no incluye la descripción del "
                    f"procedimiento {esquema}.{nombre_proc}. Valide que ya esté documentado; "
                    f"si no lo está, agréguelo."
        )]

    return [Hallazgo(
        linea=1,
        origen=OrigenAnalisis.DICCIONARIO,
        severidad=Severidad.ALTO,
        regla="PROCEDIMIENTO_SIN_DESCRIPCION",
        mensaje=f"El procedimiento {esquema}.{nombre_proc} no se encuentra "
                f"documentado. Agréguelo al diccionario con su descripción."
    )]


def _texto_de_valor(crudo: str) -> str:
    """N'texto con l''apostrofe' -> texto con l'apostrofe."""
    valor = crudo.strip()
    if valor[:2].upper() == "N'":
        valor = valor[1:]
    if len(valor) >= 2 and valor.startswith("'") and valor.endswith("'"):
        valor = valor[1:-1]
    return valor.replace("''", "'")


def _validar_ortografia(
    llamadas: List[Tuple[int, Dict[str, str]]],
    texto_diccionario: str,
    esquema: str,
    nombre_proc: str,
    parametros_reales: Set[str],
) -> List[Hallazgo]:
    """Palabras mal escritas en las descripciones (sin exigir tildes)."""
    nombres_objeto = {esquema or "", nombre_proc, *parametros_reales}
    hallazgos = []
    for pos, args in llamadas:
        if "PROCEDURE" not in args.get("level1type", "").upper() or "value" not in args:
            continue
        descripcion = _texto_de_valor(args["value"])
        if not descripcion.strip():
            continue
        if "PARAMETER" in args.get("level2type", "").upper():
            objeto = f"del parámetro {_limpiar_valor(args.get('level2name', '?'))}"
        else:
            objeto = f"del procedimiento {esquema}.{nombre_proc}"
        errores = palabras_mal_escritas(descripcion, nombres_objeto)
        if not errores:
            continue
        detalle = ", ".join(
            f"'{palabra}' (¿quiso decir '{opciones[0]}'?)" if opciones else f"'{palabra}'"
            for palabra, opciones in errores
        )
        texto = "una palabra mal escrita" if len(errores) == 1 else "palabras mal escritas"
        hallazgos.append(Hallazgo(
            linea=_numero_linea(texto_diccionario, pos),
            origen=OrigenAnalisis.DICCIONARIO,
            severidad=Severidad.MEDIO,
            regla="ERROR_ORTOGRAFICO",
            mensaje=f"La descripción {objeto} tiene {texto}: {detalle}. Corríjala.",
        ))
    return hallazgos


# ---------------------------------------------------------------------------
# ORQUESTADOR PRINCIPAL
# ---------------------------------------------------------------------------

def verificar_diccionario(
    texto_procedimiento: str,
    texto_diccionario: str
) -> List[Hallazgo]:
    """
    Funcion principal: compara el procedimiento (realidad) contra el
    script del diccionario (documentacion) y devuelve los hallazgos.
    """
    hallazgos: List[Hallazgo] = []

    esquema, nombre_proc = extraer_esquema_y_nombre(texto_procedimiento)
    if nombre_proc is None:
        return hallazgos

    tipo_sentencia = extraer_tipo_sentencia(texto_procedimiento)
    parametros_reales = extraer_parametros(texto_procedimiento)
    llamadas = extraer_llamadas_extendedproperty(texto_diccionario)

    # Caso especial ALTER sin ningun rastro de diccionario: se corta aqui,
    # no tiene sentido seguir comparando parametro por parametro si no
    # hay nada con que comparar.
    hallazgos += _validar_alter_sin_diccionario(
        tipo_sentencia, llamadas, esquema, nombre_proc
    )
    if tipo_sentencia == "ALTER" and not llamadas:
        return hallazgos

    hallazgos += _validar_procedimiento_documentado(llamadas, esquema, nombre_proc, tipo_sentencia)
    hallazgos += _validar_parametros_faltantes(
        parametros_reales, llamadas, tipo_sentencia, esquema, nombre_proc
    )
    hallazgos += _validar_nombre_procedimiento(llamadas, nombre_proc, texto_diccionario)
    hallazgos += _validar_esquema(llamadas, esquema, texto_diccionario)
    hallazgos += _validar_descripciones_vacias(llamadas, texto_diccionario)
    hallazgos += _validar_ortografia(llamadas, texto_diccionario, esquema, nombre_proc, parametros_reales)
    if REGLAS_DICCIONARIO_PROCEDIMIENTOS["VALOR_SIN_COMILLAS"].activo:
        hallazgos += _validar_valores_sin_comillas(llamadas, texto_diccionario)

    return hallazgos