"""Recomendaciones y chat local de Genesis-IA."""

import json
import os
import re
from typing import Dict, Iterable, List, Optional
from urllib.error import URLError
from urllib.request import Request, urlopen

from app.modelos.hallazgo import Hallazgo, OrigenAnalisis, Severidad


OLLAMA_URL = os.getenv("GENESIS_OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_CHAT_URL = os.getenv("GENESIS_OLLAMA_CHAT_URL", "http://localhost:11434/api/chat")
OLLAMA_MODELO = os.getenv("GENESIS_OLLAMA_MODELO", "qwen2.5-coder:3b")
LIMITE_SQL = 16000
LIMITE_SQL_CHAT = 1200
_HISTORIAL_CHAT: Dict[str, List[dict]] = {}


_RECOMENDACIONES = {
    "CONVERSION_IMPLICITA": "Alinear los tipos del predicado o JOIN y validar el plan.",
    "HINT_PLAN_PROHIBIDO": "Comparar el plan sin el hint antes de forzar una estrategia.",
    "SELECT_ESTRELLA_PROHIBIDO": "Seleccionar solo las columnas necesarias.",
    "SELECT_INTO_PROHIBIDO": "Declarar la temporal e insertar explícitamente si necesita controlarla.",
    "NOLOCK_EN_TABLA_FISICA": "Validar el aislamiento antes de usar NOLOCK; puede producir lecturas sucias.",
    "SQL_DINAMICO_PROHIBIDO": "Usar sp_executesql con parámetros en lugar de concatenar valores.",
    "VARIABLE_DECLARADA_SIN_USO": "Retirar variables que no participan en el flujo.",
    "TABLA_SIN_DESCRIPCION": "Añadir una descripción breve del propósito de la tabla.",
    "COLUMNA_FALTANTE": "Completar la documentación de la columna.",
}


def generar_sugerencias(hallazgos: Iterable[Hallazgo], limite: int = 6) -> List[Hallazgo]:
    resultado = []
    vistas = set()
    for hallazgo in hallazgos:
        mensaje = _RECOMENDACIONES.get(hallazgo.regla)
        if not mensaje or hallazgo.regla in vistas:
            continue
        vistas.add(hallazgo.regla)
        resultado.append(Hallazgo(
            linea=hallazgo.linea,
            origen=OrigenAnalisis.IA_EXPERTO,
            severidad=Severidad.BAJO,
            regla=f"IA_{hallazgo.regla}",
            mensaje=mensaje,
        ))
        if len(resultado) >= limite:
            break
    return resultado


def generar_sugerencias_sql(sql: str, limite: int = 6) -> List[dict]:
    sugerencias = []
    tablas = re.findall(r"\b(?:LEFT|RIGHT|INNER|FULL|CROSS)?\s*JOIN\s+([\w.\[\]]+)", sql, re.IGNORECASE)
    repetidas = sorted({tabla.strip("[]").upper() for tabla in tablas if tablas.count(tabla) >= 2})
    if repetidas:
        sugerencias.append({
            "titulo": f"Revisar JOIN repetidos a {', '.join(repetidas)}",
            "cambio_propuesto": "Evaluar una relación previa o APPLY solo si conserva cardinalidad y duplicados.",
        })
    if re.search(r"\bYEAR\s*\(|\b(?:CAST|CONVERT)\s*\(", sql, re.IGNORECASE):
        sugerencias.append({
            "titulo": "Revisar funciones sobre columnas filtradas",
            "cambio_propuesto": "Usar rangos y tipos compatibles sin aplicar funciones a la columna.",
        })
    if re.search(r"\w+\s*\+\s*''", sql, re.IGNORECASE):
        sugerencias.append({
            "titulo": "Revisar conversión implícita en el predicado",
            "cambio_propuesto": "Comparar la columna con un valor del mismo tipo.",
        })
    if re.search(r"\b(?:@Fecha\w*|Fecha\w*)\s+(?:VARCHAR|CHAR)", sql, re.IGNORECASE):
        sugerencias.append({
            "titulo": "Revisar tipos de parámetros de fecha",
            "cambio_propuesto": "Considerar DATE o DATETIME2 sin cambiar la firma sin validar consumidores.",
        })
    return sugerencias[:limite]


def _fallback_sugerencias(sql: str, hallazgos: Iterable[Hallazgo]) -> List[dict]:
    resultado = generar_sugerencias_sql(sql)
    vistos = {item["titulo"] for item in resultado}
    for hallazgo in generar_sugerencias(hallazgos):
        titulo = hallazgo.regla.removeprefix("IA_").replace("_", " ").title()
        if titulo not in vistos:
            resultado.append({"titulo": titulo, "cambio_propuesto": hallazgo.mensaje})
            vistos.add(titulo)
    return resultado[:6]


def _prompt_recomendaciones(sql: str, tipo: str, hallazgos: Iterable[Hallazgo]) -> str:
    reglas = "\n".join(f"- {h.regla}: {h.mensaje}" for h in hallazgos) or "- Ninguna"
    return f"""Eres el asesor de tuning SQL Server de Genesis-IA.
No ejecutes SQL. Las reglas listadas son obligatorias y ya se muestran aparte.
Encuentra oportunidades adicionales, pero no cambies cardinalidad, duplicados,
firma ni contrato sin advertirlo. Devuelve JSON breve:
{{"resumen":"...","encontrado":["..."],"mejoras":["..."],"sql_optimizado":"","nota_validacion":"..."}}
Máximo tres elementos por lista. Tipo: {tipo}
Reglas:
{reglas}
SQL:
```sql
{sql[:LIMITE_SQL]}
```"""


def _fallback_recomendaciones(sql: str, hallazgos: Iterable[Hallazgo], motivo: str) -> dict:
    sugerencias = _fallback_sugerencias(sql, hallazgos)
    return {
        "disponible": False,
        "modelo": OLLAMA_MODELO,
        "fuente": "reglas_base",
        "sugerencias": sugerencias,
        "resumen": motivo,
        "encontrado": [item["titulo"] for item in sugerencias[:3]],
        "mejoras": [item["cambio_propuesto"] for item in sugerencias[:3]],
        "sql_optimizado": "",
        "nota_validacion": "Comparar resultados, lecturas lógicas y plan antes de aplicar cambios.",
    }


def analizar_con_ollama(sql: str, tipo_revision: str, hallazgos: Iterable[Hallazgo]) -> dict:
    hallazgos = list(hallazgos)
    cuerpo = json.dumps({
        "model": OLLAMA_MODELO,
        "prompt": _prompt_recomendaciones(sql, tipo_revision, hallazgos),
        "stream": False,
        "format": "json",
        "keep_alive": "10m",
        "options": {"temperature": 0.15, "num_predict": 240},
    }).encode("utf-8")
    try:
        with urlopen(Request(OLLAMA_URL, data=cuerpo, headers={"Content-Type": "application/json"}, method="POST"), timeout=30) as respuesta:
            datos = json.loads(respuesta.read().decode("utf-8"))
        resultado = json.loads(datos.get("response", "{}"))
        if not isinstance(resultado, dict):
            raise ValueError("Respuesta de recomendaciones invalida")
        resultado.setdefault("encontrado", [])
        resultado.setdefault("mejoras", [])
        resultado.setdefault("sql_optimizado", "")
        return {"disponible": True, "modelo": OLLAMA_MODELO, "fuente": "ollama", **resultado}
    except (URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        return _fallback_recomendaciones(sql, hallazgos, "Ollama no respondió; se muestran oportunidades locales.") | {"detalle": str(exc)}


def conversar_con_ollama(sql: str, pregunta: str, tipo_revision: str = "procedimiento_normal", session_id: Optional[str] = None) -> dict:
    """Chat libre: Ollama decide si explicar, tunear o devolver código."""
    session_id = session_id or "sesion-local"
    historial = _HISTORIAL_CHAT.setdefault(session_id, [])
    if not historial:
        historial.append({
            "role": "system",
            "content": f"""Eres Genesis IA, un asistente conversacional experto en SQL Server.
Responde exactamente a la pregunta del usuario, sin menú fijo ni respuestas
preparadas. Puedes explicar, analizar, hacer tuning o escribir código según lo
que pida. Conserva la lógica y aplica cambios graduales. Nunca ejecutes SQL ni
inventes tablas, columnas o datos. Si falta un plan o esquema, dilo.
Procedimiento de referencia:
```sql
{sql[:LIMITE_SQL_CHAT]}
```
Tipo de revisión: {tipo_revision}""",
        })
    historial.append({"role": "user", "content": pregunta[:6000]})
    cuerpo = json.dumps({
        "model": OLLAMA_MODELO,
        "messages": [historial[0], *historial[-12:]],
        "stream": False,
        "keep_alive": "10m",
        "options": {"temperature": 0.25, "num_predict": 120},
    }).encode("utf-8")
    try:
        with urlopen(Request(OLLAMA_CHAT_URL, data=cuerpo, headers={"Content-Type": "application/json"}, method="POST"), timeout=20) as respuesta:
            datos = json.loads(respuesta.read().decode("utf-8"))
        mensaje = str((datos.get("message") or {}).get("content", "")).strip()
        if not mensaje:
            raise ValueError("Respuesta vacia")
        historial.append({"role": "assistant", "content": mensaje})
        return {"disponible": True, "modelo": OLLAMA_MODELO, "fuente": "ollama", "modo": "chat", "mensaje": mensaje}
    except (URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        historial.pop()
        return {
            "disponible": False,
            "modelo": OLLAMA_MODELO,
            "mensaje": "Ollama no pudo responder esta pregunta. Comprueba que Ollama esté ejecutándose.",
            "detalle": str(exc),
        }
