# -*- coding: utf-8 -*-
"""
Valida la estructura de CREATE TABLE y ALTER TABLE según el manual de
nomenclatura de base de datos de CAJA ICA.

CREATE TABLE (tabla nueva): esquema, nombre en PascalCase sin palabras de
enlace, clave primaria (índice clúster identidad nNombreTablaId) y todas las
columnas (prefijo del tipo + PascalCase, COLLATE, NOT NULL o DEFAULT).

ALTER TABLE: solo las columnas nuevas (ADD): prefijo, nombre y COLLATE; si
aceptan NULL se pide evaluar un valor por defecto, porque la tabla ya tiene
registros y no se puede exigir NOT NULL.

La severidad de cada regla sale del catálogo app/reglas/reglas_tablas.py.
"""

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from app.modelos.hallazgo import Hallazgo, OrigenAnalisis, Severidad
from app.analizadores.diccionario_agrupar import agrupar, con_elemento
from app.analizadores.ortografia import separar_palabras
from app.reglas.reglas_tablas import REGLAS_TABLAS


_IDENTIFICADOR = r"(?:\[[^\]]+\]|[A-Za-z_][\w$#@]*)"
_COMENTARIOS = re.compile(r"--[^\r\n]*|/\*.*?\*/", re.DOTALL)
_PALABRAS_NO_COLUMNA = {"CONSTRAINT", "PRIMARY", "FOREIGN", "UNIQUE", "CHECK", "INDEX", "KEY", "PERIOD"}
_PREFIJOS_TIPO = (
    ("c", r"(?:N?VARCHAR|N?CHAR|N?TEXT)\b"),
    ("n", r"(?:BIGINT|SMALLINT|TINYINT|INT|MONEY|SMALLMONEY|DECIMAL|NUMERIC|FLOAT|REAL)\b"),
    ("b", r"BIT\b"),
    # Todo lo de fecha u hora lleva «d».
    ("d", r"(?:DATETIME2|DATETIMEOFFSET|DATETIME|SMALLDATETIME|DATE|TIME)\b"),
)
_TIPOS_NUMERICOS = r"(?:BIGINT|SMALLINT|TINYINT|INT|DECIMAL|NUMERIC)\b"
_PALABRAS_OMITIBLES_TABLA = {"de", "del", "la", "el", "los", "las", "mi", "mis", "su", "sus"}

# Manual: cada palabra con mayúscula inicial y el resto en minúscula.
_PASCAL_CASE = re.compile(r"^(?:[A-Z][a-z0-9]+)+$")
# Columnas: prefijo del tipo en minúscula + PascalCase (cPersonaNombre).
_NOMBRE_COLUMNA = re.compile(r"^[a-z](?:[A-Z][a-z0-9]+)+$")
# Posible sigla: dos o más mayúsculas seguidas (MetaTPPP, nSaldoTCF, nSaldoRenovacionPFId).
_SIGLA = re.compile(r"[A-Z]{2,}(?=[A-Z][a-z]|[0-9]|$)")
# Ejemplo de nombre descriptivo en lugar de la sigla (propuesto por la usuaria).
_EJEMPLO_SIN_SIGLA = {"tabla": "MetaTasaPromPonderada", "columna": "nMetaTasaPromPonderada"}


def _siglas_del_nombre(nombre: str, patron: re.Pattern) -> List[str]:
    """
    Siglas del nombre, solo si es lo único que lo saca del estándar: con cada sigla escrita en
    PascalCase (TPPP -> Tppp) el nombre cumpliría. Si tiene otros errores (guion bajo, TB_...), vacío.
    """
    siglas = _SIGLA.findall(nombre)
    # Un nombre todo en mayúsculas (PERSONA, cPERSONA) no es una sigla: está fuera del estándar.
    if not siglas or not re.search(r"[A-Z][a-z]", nombre):
        return []
    normal = _SIGLA.sub(lambda m: m.group(0)[0] + m.group(0)[1:].lower(), nombre)
    return list(dict.fromkeys(siglas)) if patron.match(normal) else []


def _texto_siglas(siglas: List[str], articulo: bool = True) -> str:
    """«la sigla TPPP» / «las siglas TCF y TPPP» (sin artículo: «sigla TPPP»)."""
    if len(siglas) == 1:
        return f"{'la ' if articulo else ''}sigla {siglas[0]}"
    lista = ", ".join(siglas[:-1]) + f" y {siglas[-1]}"
    return f"{'las ' if articulo else ''}siglas {lista}"


def _mensaje_sigla(objeto: str, siglas: List[str], tipo: str) -> str:
    """Nombre con sigla por validar (severidad media): no es un error seguro, se pide validarlo."""
    una = len(siglas) == 1
    return (
        f"Se identificó que el nombre de {objeto} contiene {_texto_siglas(siglas)}. Se recomienda validar "
        f"{'su significado' if una else 'el significado de cada sigla'} y, de ser posible, "
        f"{'reemplazarla' if una else 'reemplazarlas'} por palabras descriptivas (ej.: {_EJEMPLO_SIN_SIGLA[tipo]}), "
        f"ya que las siglas dificultan identificar qué información almacena la {tipo}."
    )


@dataclass
class ColumnaNueva:
    nombre: str
    definicion: str
    posicion: int


# ---------------------------------------------------------------------------
# UTILIDADES
# ---------------------------------------------------------------------------

def _limpiar_identificador(valor: str) -> str:
    return valor[1:-1] if valor.startswith("[") and valor.endswith("]") else valor


def _sin_comentarios(texto: str) -> str:
    """Reemplaza comentarios por espacios conservando posiciones y saltos de línea."""
    return _COMENTARIOS.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), texto or "")


def _numero_linea(texto: str, posicion: int) -> int:
    return texto.count("\n", 0, posicion) + 1


def _posicion_tabla(texto: str) -> int:
    """Posición del nombre en el CREATE/ALTER TABLE; ahí van los hallazgos de toda la tabla."""
    coincidencia = re.search(r"\b(?:CREATE|ALTER)\s+TABLE\s+(\S)", texto, re.IGNORECASE)
    return coincidencia.start(1) if coincidencia else 0


def _hallazgo(texto: str, posicion: int, regla: str, mensaje: str) -> Hallazgo:
    """Hallazgo con la severidad definida en el catálogo de reglas."""
    return Hallazgo(
        linea=_numero_linea(texto, posicion if posicion >= 0 else _posicion_tabla(texto)),
        origen=OrigenAnalisis.REGLAS_ESTATICAS,
        severidad=Severidad(REGLAS_TABLAS[regla].severidad),
        regla=regla,
        mensaje=mensaje,
    )


def _palabras_nombre_tabla(nombre: str) -> List[str]:
    """Separa nombres PascalCase para revisar palabras omitibles."""
    return [parte.lower() for parte in re.findall(r"[A-Z]+(?=[A-Z][a-z]|$)|[A-Z]?[a-z]+|\d+", nombre)]


def _a_pascal_case(nombre: str) -> Optional[str]:
    """
    Propone el nombre en PascalCase: quita guiones bajos, espacios y el prefijo TB_.
    Las partes todo en minúsculas o mayúsculas se separan en palabras con el diccionario
    (esquematotalizadoejecutivos -> EsquemaTotalizadoEjecutivos). Si una parte sin guiones no
    se puede separar con certeza, no se propone nada (None) en lugar de un nombre equivocado.
    """
    partes = [p for p in re.split(r"[_\s]+", nombre) if p]
    if len(partes) > 1 and partes[0].upper() in {"TB", "TBL"}:
        partes = partes[1:]
    resultado = []
    for parte in partes:
        if not (parte.isupper() or parte.islower()):
            # Mayúsculas y minúsculas mezcladas: cada tramo se separa por su cuenta
            # (esquematotalizadoSupervisores -> Esquema + Totalizado + Supervisores).
            tramos = re.findall(r"[A-Z]+(?=[A-Z][a-z]|\d|$)|[A-Z]?[a-z]+|\d+", parte)
            arreglado = ""
            for tramo in tramos:
                # Solo el tramo todo en minúsculas: si el autor ya puso la mayúscula (Supervisores), se respeta.
                palabras = separar_palabras(tramo) if tramo.islower() else None
                if palabras and len(palabras) > 1:
                    arreglado += "".join(p.capitalize() for p in palabras)
                else:
                    arreglado += tramo[0].upper() + tramo[1:]
            resultado.append(arreglado)
            continue
        palabras = separar_palabras(parte)
        if palabras:
            resultado.append("".join(p.capitalize() for p in palabras))
        elif len(partes) > 1:
            resultado.append(parte.capitalize())  # los guiones bajos ya separaban las palabras
        else:
            return None
    return "".join(resultado)


def _sugerencia_tabla(tabla: str) -> Optional[str]:
    sugerido = _a_pascal_case(tabla)
    return sugerido if sugerido and sugerido != tabla and _PASCAL_CASE.match(sugerido) else None


def _sugerencia_columna(nombre: str, prefijo: Optional[str]) -> Optional[str]:
    """Propone el nombre corregido de la columna (prefijo correcto + PascalCase)."""
    tiene_prefijo = bool(re.match(r"^[a-z][A-Z_]", nombre))
    if prefijo is None and not tiene_prefijo:
        # Tipo sin prefijo en el manual (UNIQUEIDENTIFIER, XML...): no se inventa uno
        # con la primera letra del nombre (Datos XML -> «dDatos» sería fecha).
        return None
    # Si ya trae un prefijo de otro tipo (nPersonaNombre en un VARCHAR), se reemplaza.
    resto = nombre[1:] if tiene_prefijo else nombre
    if "_" not in resto and " " not in resto and resto.islower() and len(resto) > 1:
        return None  # 'cpersonanombre': no se pueden separar las palabras con certeza.
    resto_pascal = _a_pascal_case(resto.lstrip("_"))
    if resto_pascal is None:
        return None
    sugerido = (prefijo or nombre[:1].lower()) + resto_pascal
    return sugerido if sugerido != nombre and _NOMBRE_COLUMNA.match(sugerido) else None


def _prefijo_esperado(definicion: str) -> Optional[str]:
    for prefijo, patron_tipo in _PREFIJOS_TIPO:
        if re.search(rf"^\s*{patron_tipo}", definicion, re.IGNORECASE):
            return prefijo
    return None


def _tipo_de_dato(definicion: str) -> str:
    coincidencia = re.match(r"\s*([A-Za-z0-9_]+)", definicion)
    return coincidencia.group(1).upper() if coincidencia else "?"


_DESCRIPCION_PREFIJO = {"c": "texto", "n": "número", "b": "bit", "d": "fecha u hora"}
# Valor por defecto de ejemplo según el tipo, para la columna NOT NULL agregada en un ALTER.
_DEFAULT_POR_PREFIJO = {"c": "''", "n": "0", "b": "0", "d": "GETDATE()"}

# Tipos legacy (obsoletos) y su reemplazo actual.
_REEMPLAZO_LEGACY = {"TEXT": "VARCHAR(MAX)", "NTEXT": "NVARCHAR(MAX)", "REAL": "DECIMAL(p, s)"}


def _tipo_completo(definicion: str) -> str:
    """Tipo con su longitud, tal como se escribió (ej.: VARCHAR(100))."""
    coincidencia = re.match(r"\s*([A-Za-z0-9_]+\s*(?:\([^)]*\))?)", definicion)
    return coincidencia.group(1).upper().replace(" ", "") if coincidencia else "VARCHAR"


def _es_tipo_texto(definicion: str) -> bool:
    return bool(re.search(r"^\s*(?:N?VARCHAR|N?CHAR|N?TEXT)\b", definicion, re.IGNORECASE))


def _separar_por_comas(contenido: str) -> List[Tuple[str, int]]:
    """Divide por comas de primer nivel (respeta paréntesis y cadenas)."""
    segmentos, inicio, profundidad, en_cadena = [], 0, 0, False
    for indice, caracter in enumerate(contenido):
        if caracter == "'":
            en_cadena = not en_cadena
        elif not en_cadena:
            if caracter == "(":
                profundidad += 1
            elif caracter == ")":
                profundidad = max(0, profundidad - 1)
            elif caracter == "," and profundidad == 0:
                segmentos.append((contenido[inicio:indice], inicio))
                inicio = indice + 1
    segmentos.append((contenido[inicio:], inicio))
    return segmentos


def _columna_desde_segmento(segmento: str, posicion: int) -> Optional[ColumnaNueva]:
    coincidencia = re.match(rf"\s*({_IDENTIFICADOR})(.*)", segmento, re.DOTALL)
    if not coincidencia:
        return None
    nombre = _limpiar_identificador(coincidencia.group(1))
    if nombre.upper() in _PALABRAS_NO_COLUMNA:
        return None
    return ColumnaNueva(nombre, coincidencia.group(2), posicion + coincidencia.start(1))


# ---------------------------------------------------------------------------
# EXTRACCIÓN
# ---------------------------------------------------------------------------

def extraer_objeto_tabla(texto_sql: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Devuelve (base_de_datos, esquema, tabla); prioriza el CREATE TABLE."""
    texto = _sin_comentarios(texto_sql)
    for verbo in ("CREATE", "ALTER"):
        coincidencia = re.search(
            rf"\b{verbo}\s+TABLE\s+((?:{_IDENTIFICADOR}\s*\.\s*){{0,2}}{_IDENTIFICADOR})",
            texto,
            re.IGNORECASE,
        )
        if coincidencia:
            partes = [_limpiar_identificador(p.strip()) for p in coincidencia.group(1).split(".")]
            if len(partes) == 3:
                return partes[0], partes[1], partes[2]
            if len(partes) == 2:
                return None, partes[0], partes[1]
            return None, None, partes[0]
    return None, None, None


def extraer_tipo_sentencia(texto_sql: str) -> str:
    """CREATE si el script crea la tabla (aunque luego tenga ALTER TABLE)."""
    texto = _sin_comentarios(texto_sql)
    if re.search(r"\bCREATE\s+TABLE\b", texto, re.IGNORECASE):
        return "CREATE"
    if re.search(r"\bALTER\s+TABLE\b", texto, re.IGNORECASE):
        return "ALTER"
    return "DESCONOCIDO"


def _create_sin_parentesis(texto: str) -> Optional[int]:
    """Posición donde empiezan las columnas si el CREATE TABLE no las encierra entre paréntesis."""
    m = re.search(
        rf"\bCREATE\s+TABLE\s+(?:{_IDENTIFICADOR}\s*\.\s*){{0,2}}{_IDENTIFICADOR}",
        texto,
        re.IGNORECASE,
    )
    if not m or texto[m.end():].lstrip().startswith("("):
        return None
    return m.end()


def _segmentos_create(texto: str) -> List[Tuple[str, int]]:
    """Definiciones (columnas y restricciones) entre los paréntesis del CREATE TABLE."""
    inicio = re.search(
        rf"\bCREATE\s+TABLE\s+(?:{_IDENTIFICADOR}\s*\.\s*){{0,2}}{_IDENTIFICADOR}\s*\(",
        texto,
        re.IGNORECASE,
    )
    if not inicio:
        # Sin paréntesis (error de sintaxis): las columnas se leen igual, hasta el ";" o GO,
        # para revisar también su nomenclatura.
        sin_parentesis = _create_sin_parentesis(texto)
        if not sin_parentesis:
            return []
        fin = re.search(r";|\bGO\b", texto[sin_parentesis:], re.IGNORECASE)
        cuerpo = texto[sin_parentesis:sin_parentesis + fin.start()] if fin else texto[sin_parentesis:]
        return [(segmento, sin_parentesis + posicion) for segmento, posicion in _separar_por_comas(cuerpo)]
    apertura = inicio.end()
    profundidad, cierre = 0, len(texto)
    for indice in range(apertura, len(texto)):
        if texto[indice] == "(":
            profundidad += 1
        elif texto[indice] == ")":
            if profundidad == 0:
                cierre = indice
                break
            profundidad -= 1
    return [(segmento, apertura + posicion) for segmento, posicion in _separar_por_comas(texto[apertura:cierre])]


def _columnas_create(texto: str) -> List[ColumnaNueva]:
    columnas = (_columna_desde_segmento(s, p) for s, p in _segmentos_create(texto))
    return [c for c in columnas if c]


def _columnas_alter(texto: str) -> List[ColumnaNueva]:
    """Columnas agregadas con ADD en cada ALTER TABLE (admite varias por ADD)."""
    columnas = []
    sentencias = re.finditer(
        r"\bALTER\s+TABLE\b(.*?)(?=;|\bGO\b|\bALTER\s+TABLE\b|\bCREATE\b|\Z)",
        texto,
        re.IGNORECASE | re.DOTALL,
    )
    for sentencia in sentencias:
        cuerpo, base = sentencia.group(1), sentencia.start(1)
        if re.search(r"\bALTER\s+COLUMN\b", cuerpo, re.IGNORECASE):
            continue
        agregar = re.search(r"\bADD\b(?:\s+COLUMN\b)?", cuerpo, re.IGNORECASE)
        if not agregar:
            continue
        resto = cuerpo[agregar.end():]
        desplazamiento = base + agregar.end()
        # ALTER TABLE t ADD ( ... ) con paréntesis envolvente.
        recortado = resto.lstrip()
        if recortado.startswith("(") and recortado.rstrip().endswith(")"):
            desplazamiento += len(resto) - len(recortado) + 1
            resto = recortado.rstrip()[1:-1]
        for segmento, posicion in _separar_por_comas(resto):
            columna = _columna_desde_segmento(segmento, desplazamiento + posicion)
            if columna:
                columnas.append(columna)
    return columnas


def extraer_columnas_nuevas(texto_sql: str) -> List[ColumnaNueva]:
    """Columnas del CREATE TABLE o, en un ALTER, las columnas agregadas."""
    texto = _sin_comentarios(texto_sql)
    return _columnas_create(texto) if extraer_tipo_sentencia(texto) == "CREATE" else _columnas_alter(texto)


def _clave_primaria(texto: str, columnas: List[ColumnaNueva]) -> Tuple[List[str], bool, int]:
    """
    Devuelve (columnas de la PK, es_cluster, posición). Reconoce la PK en la
    columna (nId INT PRIMARY KEY), como restricción del CREATE o agregada
    con ALTER TABLE ... ADD CONSTRAINT ... PRIMARY KEY en el mismo script.
    """
    for columna in columnas:
        if re.search(r"\bPRIMARY\s+KEY\b", columna.definicion, re.IGNORECASE):
            no_cluster = re.search(r"\bPRIMARY\s+KEY\s+NONCLUSTERED\b", columna.definicion, re.IGNORECASE)
            return [columna.nombre], not no_cluster, columna.posicion
    restriccion = re.search(
        r"\bPRIMARY\s+KEY\s*(CLUSTERED|NONCLUSTERED)?\s*\(([^)]*)\)",
        texto,
        re.IGNORECASE,
    )
    if restriccion:
        nombres = [
            _limpiar_identificador(re.sub(r"\s+(?:ASC|DESC)\s*$", "", n.strip(), flags=re.IGNORECASE))
            for n in restriccion.group(2).split(",") if n.strip()
        ]
        es_cluster = (restriccion.group(1) or "CLUSTERED").upper() == "CLUSTERED"
        return nombres, es_cluster, restriccion.start()
    return [], False, -1


# ---------------------------------------------------------------------------
# VALIDACIONES
# ---------------------------------------------------------------------------

def _validar_tabla(texto: str, esquema: Optional[str], tabla: str, referencia: str) -> List[Hallazgo]:
    hallazgos = []
    if not esquema:
        hallazgos.append(_hallazgo(
            texto, -1, "TABLA_SIN_ESQUEMA",
            f"Se identificó que la tabla {tabla} no tiene declarado un esquema. Se recomienda añadir el "
            f"esquema; si es dbo, definirlo explícitamente.",
        ))
    siglas = [] if _PASCAL_CASE.match(tabla) else _siglas_del_nombre(tabla, _PASCAL_CASE)
    if siglas:
        hallazgos.append(con_elemento(_hallazgo(
            texto, -1, "TABLA_NOMBRE_CON_SIGLA", _mensaje_sigla(f"la tabla {referencia}", siglas, "tabla"),
        ), f"{referencia} ({', '.join(siglas)})"))
    elif not _PASCAL_CASE.match(tabla):
        sugerido = _sugerencia_tabla(tabla)
        # Texto de la usuaria: no enumera causas que quizá no tiene (guiones bajos, TB_...).
        accion = (
            f"Se sugiere ajustar el nombre de la tabla a {sugerido}, conforme a la nomenclatura PascalCase."
            if sugerido
            else "Ajustar el nombre de la tabla a la nomenclatura PascalCase: cada palabra con mayúscula "
                 "inicial (ej.: CuentasPorPagar)."
        )
        observacion = con_elemento(_hallazgo(
            texto, -1, "TABLA_NOMBRE_NO_PASCALCASE",
            f"Se identificó que la tabla {tabla} no cumple con el estándar de nomenclatura PascalCase "
            f"establecido en el manual. {accion}",
        ), f"{referencia} → {sugerido}" if sugerido else referencia)
        observacion.sugerido = sugerido
        hallazgos.append(observacion)
    omitibles = sorted(set(_palabras_nombre_tabla(tabla)) & _PALABRAS_OMITIBLES_TABLA)
    if omitibles:
        hallazgos.append(_hallazgo(
            texto, -1, "TABLA_CON_PALABRA_OMITIBLE",
            f"El nombre de la tabla {tabla} incluye la palabra de enlace '{omitibles[0]}'. Quítela "
            f"del nombre: la nomenclatura no usa palabras como de, del, mi o su.",
        ))
    return hallazgos


def _validar_clave_primaria(
    texto: str, tabla: str, referencia: str, columnas: List[ColumnaNueva]
) -> List[Hallazgo]:
    nombre_esperado = f"n{tabla}Id"
    pk, es_cluster, posicion = _clave_primaria(texto, columnas)
    if not pk:
        existe = any(c.nombre == nombre_esperado for c in columnas)
        accion = (
            f"Defina la columna {nombre_esperado} como PRIMARY KEY CLUSTERED." if existe
            else f"Agregue la columna {nombre_esperado} INT IDENTITY(1,1) y defínala como PRIMARY KEY CLUSTERED."
        )
        return [_hallazgo(texto, -1, "PK_FALTANTE", f"La tabla {referencia} no tiene clave primaria. {accion}")]

    hallazgos = []
    if len(pk) > 1:
        hallazgos.append(_hallazgo(
            texto, posicion, "PK_COMPUESTA",
            f"La clave primaria de {referencia} combina varias columnas ({', '.join(pk)}). Use una "
            f"sola columna identidad, {nombre_esperado}; si necesita que la combinación no se repita, "
            f"cree un índice UNIQUE aparte.",
        ))
    if not es_cluster:
        hallazgos.append(_hallazgo(
            texto, posicion, "PK_NO_CLUSTER",
            f"La clave primaria de {referencia} está definida como NONCLUSTERED. Cámbiela a "
            f"PRIMARY KEY CLUSTERED: debe ser el índice clúster de la tabla.",
        ))
    if len(pk) > 1:
        return hallazgos

    nombre_pk = pk[0]
    # Si el nombre de la tabla no sigue el estándar, ese error ya se reporta y
    # el nombre esperado de la PK no tendría sentido (nTB_EstadoId).
    if _PASCAL_CASE.match(tabla) and nombre_pk != nombre_esperado:
        hallazgos.append(con_elemento(_hallazgo(
            texto, posicion, "PK_NOMBRE_INVALIDO",
            f"La clave primaria se llama {nombre_pk}, pero debe llamarse n + nombre de la tabla + Id. "
            f"Renómbrela como {nombre_esperado}.",
        ), f"{nombre_pk} → {nombre_esperado}"))
    columna_pk = next((c for c in columnas if c.nombre.upper() == nombre_pk.upper()), None)
    if columna_pk:
        if not re.search(r"\bIDENTITY\b", columna_pk.definicion, re.IGNORECASE):
            hallazgos.append(con_elemento(_hallazgo(
                texto, columna_pk.posicion, "PK_SIN_IDENTITY",
                f"La clave primaria {nombre_pk} no es autoincremental. Defínala como identidad: "
                f"{nombre_pk} INT IDENTITY(1,1) NOT NULL.",
            ), nombre_pk))
        if not re.search(rf"^\s*{_TIPOS_NUMERICOS}", columna_pk.definicion, re.IGNORECASE):
            hallazgos.append(con_elemento(_hallazgo(
                texto, columna_pk.posicion, "PK_NO_NUMERICA",
                f"La clave primaria {nombre_pk} es de tipo {_tipo_de_dato(columna_pk.definicion)}. "
                f"De preferencia use un tipo numérico (INT o BIGINT): ocupa menos y se busca más rápido.",
            ), nombre_pk))
    return hallazgos


def _validar_columna(
    texto: str, columna: ColumnaNueva, referencia: str, es_dbcmaica: bool
) -> List[Hallazgo]:
    hallazgos = []
    definicion = columna.definicion
    prefijo = _prefijo_esperado(definicion)
    elementos = {}  # regla -> cómo se lista la columna si se agrupa

    sugerido = _sugerencia_columna(columna.nombre, prefijo)
    if prefijo and not columna.nombre.startswith(prefijo):
        accion = f"Renómbrela como {sugerido}." if sugerido else f"Agregue la '{prefijo}' al inicio del nombre."
        elementos["COLUMNA_PREFIJO_TIPO_INVALIDO"] = f"{columna.nombre} → {sugerido}" if sugerido else columna.nombre
        observacion = _hallazgo(
            texto, columna.posicion, "COLUMNA_PREFIJO_TIPO_INVALIDO",
            f"La columna {columna.nombre} es de tipo {_tipo_de_dato(definicion)}, así que su nombre "
            f"debe iniciar con '{prefijo}' ({_DESCRIPCION_PREFIJO[prefijo]}). {accion}",
        )
        observacion.cambio = (columna.nombre, sugerido, columna.nombre[:1], prefijo)
        hallazgos.append(observacion)
    elif not _NOMBRE_COLUMNA.match(columna.nombre) and _siglas_del_nombre(columna.nombre, _NOMBRE_COLUMNA):
        siglas = _siglas_del_nombre(columna.nombre, _NOMBRE_COLUMNA)
        elementos["COLUMNA_NOMBRE_CON_SIGLA"] = f"{columna.nombre} ({_texto_siglas(siglas, articulo=False)})"
        hallazgos.append(_hallazgo(
            texto, columna.posicion, "COLUMNA_NOMBRE_CON_SIGLA",
            _mensaje_sigla(f"la columna {columna.nombre} de la tabla {referencia}", siglas, "columna"),
        ))
    elif not _NOMBRE_COLUMNA.match(columna.nombre):
        accion = (
            # Texto de la usuaria.
            f"Renómbrela como {sugerido}, siguiendo PascalCase, que consiste en escribir cada palabra con "
            f"mayúscula inicial y sin guiones bajos." if sugerido
            else "Escriba cada palabra con mayúscula inicial (ej.: cPersonaNombre)."
        )
        elementos["COLUMNA_NOMBRE_NO_PASCALCASE"] = f"{columna.nombre} → {sugerido}" if sugerido else columna.nombre
        hallazgos.append(_hallazgo(
            texto, columna.posicion, "COLUMNA_NOMBRE_NO_PASCALCASE",
            f"El nombre de la columna {columna.nombre} no cumple la nomenclatura: después del prefijo, "
            f"cada palabra va con mayúscula inicial y sin guiones bajos. {accion}",
        ))

    numeros = re.findall(r"\d+", columna.nombre)
    if numeros:
        # Texto de la usuaria.
        cuantos = "un número" if len(numeros) == 1 else "números"
        hallazgos.append(_hallazgo(
            texto, columna.posicion, "COLUMNA_NOMBRE_CON_NUMERO",
            f"Se identificó que la columna {columna.nombre} de la tabla {referencia} contiene {cuantos} en "
            f"su nombre, lo cual no cumple con las buenas prácticas de nomenclatura. Renombrar la columna, "
            f"evitando el uso de números y utilizando un nombre descriptivo que permita identificar "
            f"claramente su finalidad.",
        ))

    binario = re.match(r"\s*(VARBINARY|IMAGE)\b", definicion, re.IGNORECASE)
    if binario:
        elementos["COLUMNA_VARBINARY_PROHIBIDA"] = f"{columna.nombre} ({binario.group(1).upper()})"
        hallazgos.append(_hallazgo(
            texto, columna.posicion, "COLUMNA_VARBINARY_PROHIBIDA",
            f"La columna {columna.nombre} es de tipo {binario.group(1).upper()}, que no está permitido: "
            f"almacenaría documentos en la base de datos. Guardar el documento en una solución externa "
            f"(servidor de archivos o repositorio documental) y registrar solo su ruta (ej.: cRutaArchivo "
            f"VARCHAR), ya que la base de datos es solo para datos transaccionales.",
        ))

    legacy = re.match(r"\s*(NTEXT|TEXT|REAL)\b", definicion, re.IGNORECASE)
    if legacy:
        tipo = legacy.group(1).upper()
        elementos["COLUMNA_TIPO_LEGACY"] = f"{columna.nombre} ({tipo} → {_REEMPLAZO_LEGACY[tipo]})"
        hallazgos.append(_hallazgo(
            texto, columna.posicion, "COLUMNA_TIPO_LEGACY",
            f"La columna {columna.nombre} es de tipo {tipo}, una sintaxis legacy (obsoleta) que no está "
            f"permitida. Usar {_REEMPLAZO_LEGACY[tipo]} en su lugar, ya que los tipos legacy dejarán de "
            f"estar soportados en SQL Server.",
        ))

    if re.match(r"\s*FLOAT\b", definicion, re.IGNORECASE):
        elementos["COLUMNA_TIPO_APROXIMADO"] = f"{columna.nombre} (FLOAT → DECIMAL)"
        hallazgos.append(_hallazgo(
            texto, columna.posicion, "COLUMNA_TIPO_APROXIMADO",
            f"La columna {columna.nombre} es de tipo FLOAT, que guarda valores aproximados (por ejemplo, "
            f"0.1 + 0.2 no da exactamente 0.3). Emplear DECIMAL(p, s) en su lugar, ya que montos, tasas y "
            f"cantidades deben guardarse con valores exactos.",
        ))

    tiene_collate = re.search(r"\bCOLLATE\s+\w+", definicion, re.IGNORECASE)
    if _es_tipo_texto(definicion) and not es_dbcmaica and not tiene_collate:
        hallazgos.append(_hallazgo(
            texto, columna.posicion, "COLUMNA_SIN_COLLATE",
            f"La columna de texto {columna.nombre} no define COLLATE. Agréguelo después del tipo "
            f"(ej.: {_tipo_completo(definicion)} COLLATE SQL_Latin1_General_CP1_CI_AS); solo las tablas de "
            f"DBCMAICA pueden omitirlo.",
        ))
    if not _es_tipo_texto(definicion) and tiene_collate:
        hallazgos.append(_hallazgo(
            texto, columna.posicion, "COLLATE_EN_TIPO_NO_TEXTO",
            f"La columna {columna.nombre} es de tipo {_tipo_de_dato(definicion)} y tiene COLLATE, que "
            f"solo aplica a columnas de texto (CHAR o VARCHAR). Quite el COLLATE de esta columna.",
        ))
    for hallazgo in hallazgos:
        con_elemento(hallazgo, elementos.get(hallazgo.regla, columna.nombre))
    return hallazgos


def _tiene_not_null_o_default(definicion: str) -> bool:
    return bool(re.search(r"\bNOT\s+NULL\b|\bDEFAULT\b", definicion, re.IGNORECASE))


# ---------------------------------------------------------------------------
# ORQUESTADOR
# ---------------------------------------------------------------------------

# Reglas de columna que, repetidas, se reportan una vez con la lista de columnas y su línea.
_PLANTILLAS_AGRUPADAS = {
    # --- De la tabla (cuando el script trae varias tablas) ---------------------
    "CREATE_SIN_PARENTESIS": (
        "CREATE TABLE sin paréntesis en sus columnas",
        "Encerrar las columnas de cada tabla entre paréntesis, ya que sin ellos SQL Server no puede crear "
        "las tablas.",
    ),
    "TABLA_SIN_ESQUEMA": (
        "tablas sin esquema declarado",
        "Se recomienda añadir el esquema a cada tabla; si es dbo, definirlo explícitamente.",
    ),
    "TABLA_NOMBRE_NO_PASCALCASE": (
        "tablas con nombre fuera del estándar",
        "Renombrar cada tabla en PascalCase (como se sugiere, cuando hay sugerencia): cada palabra con "
        "mayúscula inicial, sin guiones bajos, espacios ni prefijos como TB_, ya que es la nomenclatura "
        "del manual.",
    ),
    "TABLA_CON_PALABRA_OMITIBLE": (
        "tablas con palabras de enlace en el nombre",
        "Quitar las palabras de enlace (de, del, mi, su) del nombre de cada tabla, ya que la nomenclatura "
        "no las usa.",
    ),
    "TABLA_NOMBRE_CON_SIGLA": (
        # Texto de la usuaria.
        "tablas cuyos nombres contienen siglas",
        "Validar que las siglas sean comprensibles y estén estandarizadas. De ser necesario, reemplazarlas por "
        "términos descriptivos que faciliten la comprensión del nombre de la tabla.",
    ),
    "PK_FALTANTE": (
        "tablas sin clave primaria",
        "Definir en cada una la columna n + nombre de la tabla + Id (INT IDENTITY(1,1)) como PRIMARY KEY "
        "CLUSTERED, ya que toda tabla debe tener su clave primaria.",
    ),
    "PK_COMPUESTA": (
        "tablas con clave primaria de varias columnas",
        "Usar en cada una una sola columna identidad (n + nombre de la tabla + Id) y, si la combinación "
        "no debe repetirse, crear un índice UNIQUE aparte.",
    ),
    "PK_NO_CLUSTER": (
        "tablas con clave primaria NONCLUSTERED",
        "Cambiarlas a PRIMARY KEY CLUSTERED, ya que la clave primaria debe ser el índice clúster de la tabla.",
    ),
    "PK_NOMBRE_INVALIDO": (
        "claves primarias con nombre fuera del estándar",
        "Renombrar cada una como n + nombre de la tabla + Id, como se sugiere.",
    ),
    "PK_SIN_IDENTITY": (
        "claves primarias que no son autoincrementales",
        "Definir cada una como identidad (INT IDENTITY(1,1) NOT NULL).",
    ),
    "PK_NO_NUMERICA": (
        "claves primarias que no son numéricas",
        "De preferencia usar un tipo numérico (INT o BIGINT) en cada una, ya que ocupa menos y se busca "
        "más rápido.",
    ),
    # --- De las columnas -------------------------------------------------------
    "COLUMNA_PREFIJO_TIPO_INVALIDO": (
        "columnas con un prefijo que no corresponde a su tipo de dato",
        "Renombrar cada columna con el prefijo de su tipo, como se sugiere en cada una, ya que el "
        "prefijo indica qué dato guarda la columna.",
    ),
    "COLUMNA_NOMBRE_NO_PASCALCASE": (
        "columnas con nombre fuera del estándar",
        "Renombrar cada columna según la nomenclatura (como se sugiere, cuando hay sugerencia): prefijo del "
        "tipo en minúscula y cada palabra con mayúscula inicial, sin guiones bajos, ya que es la "
        "nomenclatura del manual.",
    ),
    "COLUMNA_NOMBRE_CON_SIGLA": (
        "columnas cuyo nombre contiene siglas",
        "Se recomienda validar el significado de cada sigla y, de ser posible, reemplazarla por palabras "
        "descriptivas (ej.: nMetaTasaPromPonderada), ya que las siglas dificultan identificar qué información "
        "almacena cada columna.",
    ),
    "COLUMNA_NOMBRE_CON_NUMERO": (
        "columnas con números en el nombre",
        "Renombrar cada columna, evitando el uso de números y utilizando un nombre descriptivo que permita "
        "identificar claramente su finalidad.",
    ),
    "COLUMNA_VARBINARY_PROHIBIDA": (
        "columnas que almacenarían documentos (VARBINARY o IMAGE)",
        "Guardar los documentos en una solución externa (servidor de archivos o repositorio documental) "
        "y registrar solo su ruta (ej.: cRutaArchivo VARCHAR), ya que la base de datos es solo para "
        "datos transaccionales.",
    ),
    "COLUMNA_TIPO_LEGACY": (
        "columnas con tipos de dato legacy",
        "Reemplazar cada tipo por su equivalente actual (TEXT → VARCHAR(MAX), NTEXT → NVARCHAR(MAX), "
        "REAL → DECIMAL), ya que los tipos legacy dejarán de estar soportados en SQL Server.",
    ),
    "COLUMNA_TIPO_APROXIMADO": (
        "columnas de tipo FLOAT",
        "Emplear DECIMAL(p, s) en cada una, ya que FLOAT guarda valores aproximados y montos, tasas y "
        "cantidades deben guardarse con valores exactos.",
    ),
    "COLUMNA_SIN_COLLATE": (
        "columnas de texto sin COLLATE",
        "Añadir COLLATE SQL_Latin1_General_CP1_CI_AS después del tipo de cada una, ya que solo las "
        "tablas de DBCMAICA pueden omitirlo.",
    ),
    "COLLATE_EN_TIPO_NO_TEXTO": (
        "columnas que no son de texto con COLLATE",
        "Retirar el COLLATE de esas columnas, ya que solo aplica a columnas de texto (CHAR o VARCHAR).",
    ),
    "COLUMNA_SIN_NOT_NULL_NI_DEFAULT": (
        "columnas que aceptan valores nulos",
        "Definir cada columna como NOT NULL o asignarle un valor por defecto (DEFAULT), ya que una "
        "tabla nueva no debe almacenar valores nulos.",
    ),
    "COLUMNA_NOT_NULL_SIN_DEFAULT_EN_ALTER": (
        "columnas nuevas NOT NULL sin valor por defecto",
        "Agregue un DEFAULT a cada una o defínalas como NULL, ya que el ALTER TABLE fallará si la tabla ya "
        "tiene registros: SQL Server necesita un valor para las filas existentes.",
    ),
    "COLUMNA_NULL_EN_ALTER": (
        "columnas nuevas que aceptan valores nulos",
        "Se recomienda evaluar un valor por defecto (DEFAULT) para cada una; no es obligatorio, ya que "
        "la tabla ya tiene registros.",
    ),
}


def _sentencias_de_tabla(texto: str) -> List[str]:
    """
    Cada CREATE/ALTER TABLE del script por separado. Lo demás se reemplaza por
    espacios para conservar las posiciones (y así las líneas de los hallazgos).
    Un ALTER TABLE de la misma tabla que se acaba de crear va junto a su CREATE.
    """
    inicios = list(re.finditer(rf"\b(CREATE|ALTER)\s+TABLE\s+((?:{_IDENTIFICADOR}\s*\.\s*){{0,2}}{_IDENTIFICADOR})", texto, re.IGNORECASE))
    if len(inicios) <= 1:
        return [texto]
    grupos: List[List[Tuple[int, int]]] = []
    nombre_anterior = None
    for indice, inicio in enumerate(inicios):
        fin = inicios[indice + 1].start() if indice + 1 < len(inicios) else len(texto)
        nombre = inicio.group(2).split(".")[-1].strip("[] ").upper()
        if inicio.group(1).upper() == "ALTER" and grupos and nombre == nombre_anterior:
            grupos[-1].append((inicio.start(), fin))
            continue
        grupos.append([(inicio.start(), fin)])
        nombre_anterior = nombre
    sentencias = []
    for tramos in grupos:
        visible = [False] * len(texto)
        for ini, fin in tramos:
            visible[ini:fin] = [True] * (fin - ini)
        sentencias.append("".join(c if visible[i] or c == "\n" else " " for i, c in enumerate(texto)))
    return sentencias


def verificar_tabla(texto_sql: str, es_dbcmaica: bool = False) -> List[Hallazgo]:
    """
    Valida cada CREATE TABLE o ALTER TABLE del script según el manual de nomenclatura.
    Con una sola tabla, las reglas repetidas se juntan como siempre. Con varias, cada regla se
    reporta una sola vez para todo el script, indicando la tabla de cada caso.
    """
    sentencias = _sentencias_de_tabla(_sin_comentarios(texto_sql))
    hallazgos: List[Hallazgo] = []
    for sentencia in sentencias:
        hallazgos += _verificar_una_tabla(sentencia, es_dbcmaica)
    if len(sentencias) > 1:
        return _agrupar_entre_tablas(hallazgos)
    return agrupar(hallazgos, _PLANTILLAS_AGRUPADAS)


# Reglas de la tabla (no de una columna): su elemento ya nombra la tabla.
_REGLAS_DE_TABLA = {
    "CREATE_SIN_PARENTESIS", "TABLA_SIN_ESQUEMA", "TABLA_NOMBRE_NO_PASCALCASE", "TABLA_CON_PALABRA_OMITIBLE",
    "TABLA_NOMBRE_CON_SIGLA",
    "PK_FALTANTE", "PK_COMPUESTA", "PK_NO_CLUSTER",
}


_NUMEROS_EN_LETRAS = {
    2: "dos", 3: "tres", 4: "cuatro", 5: "cinco", 6: "seis", 7: "siete", 8: "ocho", 9: "nueve", 10: "diez",
}
# Para «…datos de tipo texto y no numéricos».
_DATO_EN_PLURAL = {"c": "de texto", "n": "numéricos", "b": "de tipo bit", "d": "de fecha u hora"}
_DATO_EN_SINGULAR = {"c": "texto", "n": "numérico", "b": "bit", "d": "fecha u hora"}


def _mensaje_prefijo_entre_tablas(grupo: List[Hallazgo]) -> Optional[str]:
    """
    Prefijo de columna inválido en varias tablas (redacción de la usuaria):
    «Se identificaron dos columnas cuyo prefijo no corresponde al tipo de dato definido:
    Tabla : Cambiar x por y; … Corregir los nombres de ambas columnas, utilizando
    el prefijo c en lugar de n, ya que corresponden a datos de tipo texto y no numéricos.»
    """
    cambios = [getattr(h, "cambio", None) for h in grupo]
    if not all(cambio and cambio[1] for cambio in cambios):
        return None
    total = len(grupo)
    cantidad = _NUMEROS_EN_LETRAS.get(total, str(total))
    casos = [f"{h.tabla} : Cambiar {h.cambio[0]} por {h.cambio[1]}" for h in grupo]
    cuales = "ambas columnas" if total == 2 else f"las {cantidad} columnas"
    pares = {(c[2], c[3]) for c in cambios}
    if len(pares) == 1:
        actual, nuevo = pares.pop()
        motivo = f"ya que corresponden a datos de tipo {_DATO_EN_SINGULAR[nuevo]}"
        if actual in _DATO_EN_PLURAL:
            motivo += f" y no {_DATO_EN_PLURAL[actual]}"
        recomendacion = (f"Corregir los nombres de {cuales}, utilizando el prefijo {nuevo} "
                         f"en lugar de {actual}, {motivo}.")
    else:
        recomendacion = (f"Corregir los nombres de {cuales}, utilizando el prefijo de su tipo de "
                         f"dato como se indica en cada una, ya que el prefijo indica qué dato guarda la columna.")
    return (f"Se identificaron {cantidad} columnas cuyo prefijo no corresponde al tipo de dato definido: "
            f"{'; '.join(casos)}. {recomendacion}")


def _mensaje_pascal_case_entre_tablas(grupo: List[Hallazgo]) -> str:
    """
    Tablas fuera de PascalCase en varias tablas, en el estilo del texto de la usuaria:
    «Se identificaron dos tablas que no cumplen con el estándar de nomenclatura PascalCase establecido
    en el manual: Tabla : Ajustar el nombre a X; … Ajustar el nombre de ambas tablas conforme a la
    nomenclatura PascalCase, como se sugiere en cada una.»
    """
    total = len(grupo)
    cantidad = _NUMEROS_EN_LETRAS.get(total, str(total))
    casos = [
        f"{h.tabla} : Ajustar el nombre a {h.sugerido}" if getattr(h, "sugerido", None)
        else f"{h.tabla} : Ajustar el nombre a PascalCase (cada palabra con mayúscula inicial)"
        for h in grupo
    ]
    cuales = "ambas tablas" if total == 2 else f"las {cantidad} tablas"
    return (f"Se identificaron {cantidad} tablas que no cumplen con el estándar de nomenclatura PascalCase "
            f"establecido en el manual: {'; '.join(casos)}. Ajustar el nombre de {cuales} conforme a la "
            f"nomenclatura PascalCase, como se sugiere en cada una.")


def _agrupar_entre_tablas(hallazgos: List[Hallazgo]) -> List[Hallazgo]:
    """
    Script con varias tablas: una observación por regla. Si la regla aparece varias veces se listan
    todos los casos con su tabla y línea, y el «qué hacer» va en plural; si aparece una sola vez,
    el mensaje dice de qué tabla es.
    """
    grupos = {}
    for hallazgo in hallazgos:
        grupos.setdefault(hallazgo.regla, []).append(hallazgo)

    resultado: List[Hallazgo] = []
    for regla, grupo in grupos.items():
        if len(grupo) == 1:
            hallazgo = grupo[0]
            tabla = getattr(hallazgo, "tabla", "")
            nombre_corto = tabla.split(".")[-1]
            if tabla and nombre_corto not in hallazgo.mensaje:
                hallazgo.mensaje = f"En la tabla {tabla}, {hallazgo.mensaje[0].lower()}{hallazgo.mensaje[1:]}"
            resultado.append(hallazgo)
            continue

        grupo = sorted(grupo, key=lambda h: h.linea)
        numeros = sorted({h.linea for h in grupo})
        # Las líneas van en el encabezado de la observación: los casos solo dicen su tabla.
        mensaje = (
            _mensaje_prefijo_entre_tablas(grupo) if regla == "COLUMNA_PREFIJO_TIPO_INVALIDO"
            else _mensaje_pascal_case_entre_tablas(grupo) if regla == "TABLA_NOMBRE_NO_PASCALCASE"
            else None
        )
        if mensaje is None:
            if regla in _REGLAS_DE_TABLA:
                casos = [h.elemento for h in grupo]
            elif regla == "COLUMNA_NOMBRE_CON_SIGLA":
                casos = [f"{h.tabla} : {h.elemento}" for h in grupo]
            else:
                casos = [f"{h.elemento} ({h.tabla})" for h in grupo]
            sustantivo, accion = _PLANTILLAS_AGRUPADAS[regla]
            cantidad = _NUMEROS_EN_LETRAS.get(len(grupo), str(len(grupo)))
            mensaje = f"Se identificaron {cantidad} {sustantivo}: {'; '.join(casos)}. {accion}"
        resumido = Hallazgo(
            linea=numeros[0],
            origen=grupo[0].origen,
            severidad=grupo[0].severidad,
            regla=regla,
            mensaje=mensaje,
        )
        resumido.lineas = numeros
        resultado.append(resumido)
    return resultado


def _verificar_una_tabla(texto_sql: str, es_dbcmaica: bool) -> List[Hallazgo]:
    """Valida un CREATE TABLE o ALTER TABLE según el manual de nomenclatura."""
    texto = _sin_comentarios(texto_sql)
    base, esquema, tabla = extraer_objeto_tabla(texto)
    tipo = extraer_tipo_sentencia(texto)
    if tabla is None or tipo == "DESCONOCIDO":
        return []

    referencia = f"{esquema}.{tabla}" if esquema else tabla
    pertenece_a_dbcmaica = es_dbcmaica or (base or "").upper() == "DBCMAICA"
    hallazgos: List[Hallazgo] = []

    if tipo == "CREATE":
        columnas = _columnas_create(texto)
        sin_parentesis = _create_sin_parentesis(texto)
        if sin_parentesis is not None:
            hallazgos.append(_hallazgo(
                texto, sin_parentesis, "CREATE_SIN_PARENTESIS",
                f"El CREATE TABLE de la tabla {referencia} no encierra sus columnas entre paréntesis. "
                f"Encerrar las columnas entre paréntesis, ya que sin ellos SQL Server no puede crear la "
                f"tabla (ej.: CREATE TABLE {referencia} ( ... );).",
            ))
        hallazgos += _validar_tabla(texto, esquema, tabla, referencia)
        hallazgos += _validar_clave_primaria(texto, tabla, referencia, columnas)
        for columna in columnas:
            hallazgos += _validar_columna(texto, columna, referencia, pertenece_a_dbcmaica)
            # La PK y las columnas IDENTITY ya son NOT NULL implícitamente.
            implicita = re.search(r"\bPRIMARY\s+KEY\b|\bIDENTITY\b|^\s*AS\b", columna.definicion, re.IGNORECASE)
            if not implicita and not _tiene_not_null_o_default(columna.definicion):
                hallazgos.append(con_elemento(_hallazgo(
                    texto, columna.posicion, "COLUMNA_SIN_NOT_NULL_NI_DEFAULT",
                    f"La columna {columna.nombre} acepta valores nulos. Defínala como NOT NULL o "
                    f"asígnele un valor por defecto (DEFAULT).",
                ), columna.nombre))
    else:
        if not esquema:
            hallazgos.append(_hallazgo(
                texto, -1, "TABLA_SIN_ESQUEMA",
                f"Se identificó que la tabla {tabla} no tiene declarado un esquema. Se recomienda añadir el "
                f"esquema; si es dbo, definirlo explícitamente.",
            ))
        for columna in _columnas_alter(texto):
            hallazgos += _validar_columna(texto, columna, referencia, pertenece_a_dbcmaica)
            definicion = columna.definicion
            # SQL Server permite NOT NULL sin DEFAULT en IDENTITY, TIMESTAMP/ROWVERSION y columnas calculadas.
            sin_default = not re.search(
                r"\bDEFAULT\b|\bIDENTITY\b|^\s*(?:AS|TIMESTAMP|ROWVERSION)\b", definicion, re.IGNORECASE
            )
            if re.search(r"\bNOT\s+NULL\b", definicion, re.IGNORECASE) and sin_default:
                # SQL Server no puede llenar la columna en las filas que ya existen: el ALTER falla.
                ejemplo = (
                    f"{columna.nombre} {_tipo_completo(definicion)} NOT NULL CONSTRAINT DF_{tabla}_{columna.nombre} "
                    f"DEFAULT ({_DEFAULT_POR_PREFIJO.get(_prefijo_esperado(definicion), '...')})"
                )
                hallazgos.append(con_elemento(_hallazgo(
                    texto, columna.posicion, "COLUMNA_NOT_NULL_SIN_DEFAULT_EN_ALTER",
                    f"La columna nueva {columna.nombre} se agrega como NOT NULL sin un valor por defecto, por lo "
                    f"que el ALTER TABLE fallará si la tabla ya tiene registros. Agregue un DEFAULT (ej.: "
                    f"{ejemplo}) o defínala como NULL, ya que SQL Server necesita un valor para las filas existentes.",
                ), columna.nombre))
            elif not _tiene_not_null_o_default(definicion):
                hallazgos.append(con_elemento(_hallazgo(
                    texto, columna.posicion, "COLUMNA_NULL_EN_ALTER",
                    f"La columna nueva {columna.nombre} acepta valores nulos. ¿Evaluó definir un valor por "
                    f"defecto (DEFAULT)? No es obligatorio: como la tabla ya tiene registros, no se exige "
                    f"NOT NULL.",
                ), columna.nombre))

    # Las reglas desactivadas en el catálogo no se reportan. Cada observación recuerda su tabla y,
    # si no nombra una columna, a la tabla como elemento (para juntarlas entre tablas).
    activos = [h for h in hallazgos if REGLAS_TABLAS[h.regla].activo]
    for hallazgo in activos:
        hallazgo.tabla = referencia
        if not getattr(hallazgo, "elemento", None):
            hallazgo.elemento = referencia
    return activos
