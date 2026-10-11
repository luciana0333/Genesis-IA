# -*- coding: utf-8 -*-
"""
Reglas para el bloque de índices que acompaña al script de una tabla
(segunda cajita de la pestaña Tablas), según el manual de CAJA ICA:

    PK    Llave primaria
    FK    Llave foránea
    IX    Índice clúster
    IXN   Índice nonclustered
    IXU   Unique índice clúster
    IXUN  Unique índice nonclustered

    Nombre: <Prefijo>_<Tabla>_<Campos indexados...>_INC<nn>, donde nn es el
    número de columnas incluidas con dos dígitos (INC02), solo si hay INCLUDE.
    Ej.: IXN_PERSONA_CPERSCOD_NPERSCLASIFICACION_CPERSESTADO_INC02.
    Los corchetes y ASC/DESC son opcionales; los paréntesis, obligatorios.

Si los índices son de la tabla que se crea en el mismo script, se cruzan con
ella: columnas que existen, tipos que se pueden indexar y clave primaria.
Las líneas de los hallazgos son las de la cajita de índices.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from app.modelos.hallazgo import Hallazgo, OrigenAnalisis, Severidad
from app.reglas.reglas_tablas import REGLAS_TABLAS

_IDENTIFICADOR = r"(?:\[[^\]]+\]|[#@]?[A-Za-z_][\w$#]*)"
_REFERENCIA = rf"{_IDENTIFICADOR}(?:\s*\.\s*{_IDENTIFICADOR}){{0,2}}"
_TIPOS_NO_INDEXABLES = re.compile(r"^(?:N?VARCHAR|VARBINARY)\s*\(\s*MAX\s*\)$|^(?:N?TEXT|IMAGE|XML)$", re.IGNORECASE)
# Columnas de texto descriptivo: no sirven para buscar ni filtrar y vuelven pesado el
# índice. Se reconocen por una parte de su nombre (cDescripcion, CPERSDIRECCION...).
_COLUMNAS_DESCRIPTIVAS = {
    "descripcion": "descripción", "direccion": "dirección", "observacion": "observación",
    "comentario": "comentario", "detalle": "detalle", "glosa": "glosa", "mensaje": "mensaje",
    "referencia": "referencia", "motivo": "motivo",
}


def _texto_descriptivo(columna: str) -> str:
    """Qué texto descriptivo guarda la columna según su nombre ('' si no lo es)."""
    nombre = columna.lower()
    return next((descripcion for palabra, descripcion in _COLUMNAS_DESCRIPTIVAS.items() if palabra in nombre), "")


@dataclass
class _Tabla:
    nombre: str  # sin esquema
    columnas: Dict[str, str] = field(default_factory=dict)  # nombre en minúscula → tipo
    nombres: Dict[str, str] = field(default_factory=dict)  # nombre en minúscula → como se escribió
    pk: List[str] = field(default_factory=list)
    pk_clustered: bool = False
    pk_nombre: str = ""


@dataclass
class _Indice:
    posicion: int
    nombre: str
    unico: bool
    clustered: bool
    tabla: str  # como se escribió (con esquema si lo trae)
    claves: List[str]
    incluidas: List[str]
    posicion_tabla: int


def _limpiar(nombre: str) -> str:
    return re.sub(r"\s*\.\s*", ".", nombre.strip()).replace("[", "").replace("]", "")


def _sin_comentarios(texto: str) -> str:
    texto = re.sub(r"/\*.*?\*/", lambda m: re.sub(r"[^\n]", " ", m.group(0)), texto, flags=re.DOTALL)
    return re.sub(r"--[^\n]*", lambda m: " " * len(m.group(0)), texto)


def _linea(texto: str, posicion: int) -> int:
    return texto.count("\n", 0, posicion) + 1


def _hallazgo(texto: str, posicion: int, regla: str, mensaje: str) -> Hallazgo:
    hallazgo = Hallazgo(
        linea=_linea(texto, posicion),
        origen=OrigenAnalisis.REGLAS_ESTATICAS,
        severidad=Severidad(REGLAS_TABLAS[regla].severidad),
        regla=regla,
        mensaje=mensaje,
    )
    hallazgo.seccion = "indices"  # la línea es de la cajita de índices
    return hallazgo


def _contenido_parentesis(texto: str, apertura: int) -> Tuple[str, int]:
    """Contenido entre el paréntesis que abre en `apertura` y su cierre; -1 si no cierra."""
    profundidad = 0
    for indice in range(apertura, len(texto)):
        if texto[indice] == "(":
            profundidad += 1
        elif texto[indice] == ")":
            profundidad -= 1
            if profundidad == 0:
                return texto[apertura + 1:indice], indice
    return texto[apertura + 1:], -1


def _separar(contenido: str) -> List[str]:
    partes, profundidad, actual = [], 0, ""
    for caracter in contenido:
        if caracter == "(":
            profundidad += 1
        elif caracter == ")":
            profundidad -= 1
        if caracter == "," and profundidad == 0:
            partes.append(actual)
            actual = ""
        else:
            actual += caracter
    partes.append(actual)
    return [parte.strip() for parte in partes if parte.strip()]


def _tabla_del_script(texto_tabla: str) -> Optional[_Tabla]:
    """Columnas, tipos y clave primaria del CREATE TABLE del script de la tabla."""
    limpio = _sin_comentarios(texto_tabla or "")
    creacion = re.search(rf"\bCREATE\s+TABLE\s+({_REFERENCIA})\s*\(", limpio, re.IGNORECASE)
    if not creacion:
        return None
    tabla = _Tabla(nombre=_limpiar(creacion.group(1)).split(".")[-1])
    contenido, _ = _contenido_parentesis(limpio, creacion.end() - 1)
    for definicion in _separar(contenido):
        restriccion = re.match(
            r"(?:CONSTRAINT\s+(\S+)\s+)?PRIMARY\s+KEY\s*(NONCLUSTERED|CLUSTERED)?\s*\(([^)]*)\)",
            definicion, re.IGNORECASE,
        )
        if restriccion:
            tabla.pk_nombre = _limpiar(restriccion.group(1) or "")
            tabla.pk = [_limpiar(c.split()[0]) for c in restriccion.group(3).split(",") if c.strip()]
            tabla.pk_clustered = (restriccion.group(2) or "CLUSTERED").upper() == "CLUSTERED"
            continue
        if re.match(r"(?:CONSTRAINT|PRIMARY|FOREIGN|UNIQUE|CHECK|INDEX)\b", definicion, re.IGNORECASE):
            continue
        columna = re.match(rf"({_IDENTIFICADOR})\s+([A-Za-z]+\s*(?:\([^)]*\))?)", definicion)
        if not columna:
            continue
        nombre = _limpiar(columna.group(1))
        tabla.columnas[nombre.lower()] = re.sub(r"\s+", "", columna.group(2)).upper()
        tabla.nombres[nombre.lower()] = nombre
        en_linea = re.search(r"\bPRIMARY\s+KEY\s*(NONCLUSTERED|CLUSTERED)?", definicion, re.IGNORECASE)
        if en_linea:
            tabla.pk = [nombre]
            tabla.pk_clustered = (en_linea.group(1) or "CLUSTERED").upper() == "CLUSTERED"
    return tabla


def _prefijo(unico: bool, clustered: bool) -> str:
    return {(False, True): "IX", (False, False): "IXN", (True, True): "IXU", (True, False): "IXUN"}[(unico, clustered)]


def _tipo(unico: bool, clustered: bool) -> str:
    return f"{'UNIQUE ' if unico else ''}{'CLUSTERED' if clustered else 'NONCLUSTERED'}"


def _nombre_esperado(indice: _Indice) -> str:
    tabla = _limpiar(indice.tabla).split(".")[-1]
    partes = [_prefijo(indice.unico, indice.clustered), tabla] + indice.claves
    if indice.incluidas:
        partes.append(f"INC{len(indice.incluidas):02d}")
    return "_".join(partes)


_SENTENCIA = re.compile(r"\bCREATE\s+(?:UNIQUE\s+)?(?:CLUSTERED\s+|NONCLUSTERED\s+)?INDEX\b", re.IGNORECASE)


def verificar_indices(texto_indices: str, texto_tabla: str = "") -> List[Hallazgo]:
    """Valida la sintaxis, el nombre y la estructura de cada CREATE INDEX."""
    texto = texto_indices or ""
    limpio = _sin_comentarios(texto)
    tabla_script = _tabla_del_script(texto_tabla)
    hallazgos: List[Hallazgo] = []
    indices: List[_Indice] = []

    inicios = [m.start() for m in _SENTENCIA.finditer(limpio)]
    for numero, inicio in enumerate(inicios):
        fin = inicios[numero + 1] if numero + 1 < len(inicios) else len(limpio)
        sentencia = re.split(r";|\bGO\b", limpio[inicio:fin], maxsplit=1, flags=re.IGNORECASE)[0]
        indice = _leer_indice(texto, inicio, sentencia, hallazgos)
        if indice:
            indices.append(indice)

    for indice in indices:
        hallazgos.extend(_validar_indice(texto, indice, tabla_script))
    hallazgos.extend(_validar_duplicados(texto, indices, tabla_script))
    return sorted(hallazgos, key=lambda h: h.linea)


def _leer_indice(texto: str, inicio: int, sentencia: str, hallazgos: List[Hallazgo]) -> Optional[_Indice]:
    """Lee un CREATE INDEX; si su sintaxis no es válida, registra el hallazgo y devuelve None."""
    cabecera = re.match(
        rf"CREATE\s+(UNIQUE\s+)?(CLUSTERED\s+|NONCLUSTERED\s+)?INDEX\s+({_IDENTIFICADOR})?\s*"
        rf"(?:ON\s+({_REFERENCIA})\s*)?(\()?",
        sentencia, re.IGNORECASE,
    )
    nombre = _limpiar(cabecera.group(3)) if cabecera.group(3) else ""
    if nombre.upper() == "ON":  # CREATE INDEX ON ...: la palabra ON no es el nombre
        nombre = ""
    falta = None
    if not nombre:
        falta = "falta el nombre del índice"
    elif not cabecera.group(4):
        falta = "falta la tabla (ON Esquema.Tabla)"
    elif not cabecera.group(5):
        falta = "faltan las columnas entre paréntesis"
    else:
        claves_texto, cierre = _contenido_parentesis(sentencia, cabecera.end(5) - 1)
        if cierre < 0:
            falta = "falta el paréntesis que cierra la lista de columnas"
        elif not claves_texto.strip():
            falta = "faltan las columnas del índice"
    if falta:
        hallazgos.append(_hallazgo(
            texto, inicio, "INDICE_SINTAXIS_INVALIDA",
            f"Se identificó que el índice {nombre + ' ' if nombre else ''}no está bien escrito: {falta}. Se "
            f"recomienda completarlo con la estructura CREATE [UNIQUE] [NONCLUSTERED] INDEX Nombre ON "
            f"Esquema.Tabla (Columnas), ya que así como está SQL Server no puede crearlo.",
        ))
        return None

    claves = [_limpiar(re.sub(r"\s+(?:ASC|DESC)\s*$", "", c, flags=re.IGNORECASE)) for c in _separar(claves_texto)]
    resto = sentencia[cabecera.end(5) - 1 + len(claves_texto) + 2:]
    incluidas: List[str] = []
    include = re.search(r"\bINCLUDE\s*\(", resto, re.IGNORECASE)
    if include:
        contenido, _ = _contenido_parentesis(resto, include.end() - 1)
        incluidas = [_limpiar(c) for c in _separar(contenido)]
    return _Indice(
        posicion=inicio,
        nombre=nombre,
        unico=bool(cabecera.group(1)),
        clustered=bool(cabecera.group(2)) and cabecera.group(2).strip().upper() == "CLUSTERED",
        tabla=cabecera.group(4),
        claves=claves,
        incluidas=incluidas,
        posicion_tabla=inicio + cabecera.start(4),
    )


def _validar_indice(texto: str, indice: _Indice, tabla_script: Optional[_Tabla]) -> List[Hallazgo]:
    hallazgos = []
    tipo = _tipo(indice.unico, indice.clustered)
    prefijo = _prefijo(indice.unico, indice.clustered)
    esperado = _nombre_esperado(indice)
    tabla = _limpiar(indice.tabla)

    # Nombre: prefijo según el tipo y formato <Prefijo>_<Tabla>_<Campos>_INC<nn>.
    if indice.nombre.split("_")[0].upper() != prefijo:
        hallazgos.append(_hallazgo(
            texto, indice.posicion, "INDICE_PREFIJO_INVALIDO",
            f"Se identificó que el índice {indice.nombre} es {tipo}, pero su nombre no usa el prefijo {prefijo}_. "
            f"Se recomienda nombrarlo según el manual, ya que el prefijo indica el tipo de índice "
            f"(ej.: {esperado}).",
        ))
    elif indice.nombre.lower() != esperado.lower():
        hallazgos.append(_hallazgo(
            texto, indice.posicion, "INDICE_NOMBRE_NO_ESTANDAR",
            f"Se identificó que el nombre del índice {indice.nombre} no sigue el formato "
            f"{prefijo}_Tabla_Campos{f'_INC{len(indice.incluidas):02d}' if indice.incluidas else ''}. Se "
            f"recomienda nombrarlo con la tabla y los campos indexados"
            f"{' y el número de columnas incluidas' if indice.incluidas else ''}, ya que así se sabe qué "
            f"cubre el índice sin abrirlo (ej.: {esperado}).",
        ))

    if "." not in tabla:
        hallazgos.append(_hallazgo(
            texto, indice.posicion_tabla, "INDICE_SIN_ESQUEMA",
            f"Se identificó que el índice {indice.nombre} se crea sobre la tabla {tabla} sin declarar su "
            f"esquema. Se recomienda añadir el esquema; si es dbo, definirlo explícitamente, ya que así se "
            f"evita crear el índice en una tabla equivocada (ej.: ON dbo.{tabla}).",
        ))

    # Columnas de texto descriptivo (descripción, dirección...): se busca indexar lo que sirve.
    for columna in indice.claves + indice.incluidas:
        que = _texto_descriptivo(columna)
        if que:
            donde = "como clave" if columna in indice.claves else "en el INCLUDE"
            hallazgos.append(_hallazgo(
                texto, indice.posicion, "INDICE_COLUMNA_DESCRIPTIVA",
                f"Se identificó que el índice {indice.nombre} usa {donde} la columna {columna}, que guarda "
                f"texto descriptivo ({que}). Se recomienda no incluirla e indexar columnas que se usan para "
                f"buscar o filtrar (códigos, fechas, estados), ya que el texto largo vuelve pesado el índice "
                f"y no ayuda a las búsquedas.",
            ))

    # La clave primaria siempre es el índice clúster (identidad): ningún otro índice
    # puede serlo. No se prohíbe tajantemente: se pide definirlo NONCLUSTERED.
    if indice.clustered:
        sugerido = _nombre_esperado(_Indice(**{**indice.__dict__, "clustered": False}))
        pk = (tabla_script.pk_nombre if tabla_script else "") or "la clave primaria"
        hallazgos.append(_hallazgo(
            texto, indice.posicion, "INDICE_CLUSTERED_CON_PK",
            f"Se identificó que el índice {indice.nombre} se define como {tipo}, pero {pk} es siempre el "
            f"índice clúster de la tabla (identidad). Se recomienda definirlo como "
            f"{'UNIQUE ' if indice.unico else ''}NONCLUSTERED, ya que la tabla solo puede tener un índice "
            f"clúster y ese lugar lo ocupa la clave primaria (ej.: {sugerido}).",
        ))

    if not tabla_script:
        return hallazgos
    if tabla.split(".")[-1].lower() != tabla_script.nombre.lower():
        hallazgos.append(_hallazgo(
            texto, indice.posicion_tabla, "INDICE_OTRA_TABLA",
            f"Se identificó que el índice {indice.nombre} es de la tabla {tabla}, pero el script crea la "
            f"tabla {tabla_script.nombre}. Se recomienda validar que el índice corresponda a esta tabla, ya "
            f"que se revisa junto con su script.",
        ))
        return hallazgos

    # Columnas que no existen y columnas que no se pueden indexar.
    for columna in indice.claves + indice.incluidas:
        if columna.lower() not in tabla_script.columnas:
            hallazgos.append(_hallazgo(
                texto, indice.posicion, "INDICE_COLUMNA_NO_EXISTE",
                f"Se identificó que el índice {indice.nombre} usa la columna {columna}, que no existe en la "
                f"tabla {tabla_script.nombre}. Se recomienda usar el nombre exacto de la columna, ya que así "
                f"como está SQL Server no puede crear el índice.",
            ))
    for columna in indice.claves:
        tipo_columna = tabla_script.columnas.get(columna.lower(), "")
        if tipo_columna and _TIPOS_NO_INDEXABLES.match(tipo_columna):
            hallazgos.append(_hallazgo(
                texto, indice.posicion, "INDICE_COLUMNA_NO_INDEXABLE",
                f"Se identificó que el índice {indice.nombre} usa como clave la columna {columna}, que es "
                f"{tipo_columna}. Se recomienda llevarla al INCLUDE o definir una longitud fija, ya que SQL "
                f"Server no permite usar ese tipo como clave de un índice.",
            ))

    return hallazgos


def _validar_duplicados(texto: str, indices: List[_Indice], tabla_script: Optional[_Tabla]) -> List[Hallazgo]:
    """Dos índices con las mismas columnas clave (o uno igual a la clave primaria)."""
    hallazgos = []
    vistos: Dict[Tuple[str, Tuple[str, ...]], str] = {}
    if tabla_script and tabla_script.pk:
        clave_pk = (tabla_script.nombre.lower(), tuple(c.lower() for c in tabla_script.pk))
        vistos[clave_pk] = tabla_script.pk_nombre or "la clave primaria"
    for indice in indices:
        clave = (_limpiar(indice.tabla).split(".")[-1].lower(), tuple(c.lower() for c in indice.claves))
        if clave in vistos:
            hallazgos.append(_hallazgo(
                texto, indice.posicion, "INDICE_DUPLICADO",
                f"Se identificó que el índice {indice.nombre} tiene las mismas columnas clave que "
                f"{vistos[clave]} ({', '.join(indice.claves)}). Se recomienda eliminar el índice repetido, "
                f"ya que ocupa espacio y vuelve más lentas las inserciones sin mejorar las consultas.",
            ))
        else:
            vistos[clave] = indice.nombre
    return hallazgos
