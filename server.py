import json
from email.parser import BytesParser
from email.policy import default
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

from app.analizadores.analizador_diccionario_procedimientos import verificar_diccionario
from app.analizadores.analizador_diccionario_tablas import verificar_diccionario_tablas
from app.analizadores.analizador_tablas import verificar_tabla
from app.analizadores.analizador_reportes import verificar_reporte
from app.analizadores.analizador_procedimientos_normales import verificar_procedimiento_normal
from app.analizadores.planes_ejecucion import analizar_plan_ejecucion
from app.ia.recomendador import analizar_con_ollama, conversar_con_ollama
from app.modelos.hallazgo import Hallazgo, OrigenAnalisis, Severidad


class GenesisHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory='interfaz', **kwargs)

    def do_GET(self):
        parsed = urlsplit(self.path)
        if parsed.path == '/api/health':
            self._send_json({'status': 'ok'})
            return
        super().do_GET()

    def do_POST(self):
        parsed = urlsplit(self.path)
        if parsed.path == '/api/analizar-plan':
            self._analizar_plan()
            return
        if parsed.path == '/api/sugerencias':
            self._sugerencias_ia()
            return
        if parsed.path == '/api/chat':
            self._chat_ia()
            return
        if parsed.path != '/api/analizar':
            self.send_error(404, 'Ruta no encontrada')
            return

        try:
            length = int(self.headers.get('Content-Length', '0'))
            raw_body = self.rfile.read(length).decode('utf-8') if length > 0 else '{}'
            payload = json.loads(raw_body or '{}')
        except Exception:
            self._send_json({'error': 'JSON inválido'}, status=400)
            return

        tipo = (payload.get('tipoRevision') or 'tabla').strip()
        sql_text = (payload.get('sqlObject') or '').strip()
        dict_text = (payload.get('dictScript') or '').strip()
        es_dbcmaica = bool(payload.get('esDbcmaica', False))
        modo_revision = (payload.get('modoRevision') or 'diccionario').strip()

        if not sql_text:
            self._send_json({'error': 'Debes completar el SQL del objeto.'}, status=400)
            return

        try:
            if tipo == 'reporte':
                hallazgos = verificar_reporte(sql_text)
            elif tipo == 'procedimiento_normal':
                hallazgos = verificar_procedimiento_normal(sql_text)
            elif tipo == 'procedimiento':
                hallazgos = verificar_diccionario(sql_text, dict_text)
            elif tipo == 'tabla_estructura' or modo_revision == 'tabla_estructura':
                hallazgos = verificar_tabla(sql_text, es_dbcmaica)
            else:
                hallazgos = verificar_diccionario_tablas(sql_text, dict_text)
        except Exception as exc:  # pragma: no cover - safety net for runtime errors
            self._send_json({'error': f'Error al ejecutar el analizador: {exc}'}, status=500)
            return

        resumen = {
            'critico': 0,
            'alto': 0,
            'medio': 0,
            'bajo': 0,
        }
        hallazgos_serializados = []

        for hallazgo in hallazgos:
            severidad = str(hallazgo.severidad.value).lower()
            if severidad in resumen:
                resumen[severidad] += 1
            hallazgos_serializados.append({
                'linea': hallazgo.linea,
                'origen': hallazgo.origen.value,
                'severidad': severidad,
                'regla': hallazgo.regla,
                'mensaje': hallazgo.mensaje,
            })

        self._send_json({
            'tipoRevision': tipo,
            'resumen': resumen,
            'hallazgos': hallazgos_serializados,
            'sugerenciasIA': {
                'pendiente': True,
                'modelo': 'qwen2.5-coder:3b',
                'sugerencias': [],
            },
        })

    def _sugerencias_ia(self):
        try:
            length = int(self.headers.get('Content-Length', '0'))
            payload = json.loads(self.rfile.read(length).decode('utf-8') or '{}')
            sql_text = (payload.get('sqlObject') or '').strip()
            tipo = (payload.get('tipoRevision') or 'tabla').strip()
            if not sql_text:
                self._send_json({'error': 'Debes completar el SQL del objeto.'}, status=400)
                return
            hallazgos = [
                Hallazgo(
                    linea=int(item.get('linea') or 1),
                    origen=OrigenAnalisis(item.get('origen', OrigenAnalisis.REGLAS_ESTATICAS.value)),
                    severidad=Severidad(item.get('severidad', Severidad.ALTO.value)),
                    regla=item.get('regla', ''),
                    mensaje=item.get('mensaje', ''),
                )
                for item in payload.get('hallazgos', [])
            ]
            self._send_json(analizar_con_ollama(sql_text, tipo, hallazgos))
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self._send_json({'error': f'No se pudieron preparar las sugerencias: {exc}'}, status=400)

    def _chat_ia(self):
        try:
            length = int(self.headers.get('Content-Length', '0'))
            payload = json.loads(self.rfile.read(length).decode('utf-8') or '{}')
            sql_text = (payload.get('sqlObject') or '').strip()
            pregunta = (payload.get('pregunta') or '').strip()
            if not sql_text or not pregunta:
                self._send_json({'error': 'Debes enviar el SQL y una pregunta.'}, status=400)
                return
            self._send_json(conversar_con_ollama(
                sql_text,
                pregunta,
                (payload.get('tipoRevision') or 'procedimiento_normal').strip(),
                (payload.get('sessionId') or '').strip() or None,
            ))
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self._send_json({'error': f'No se pudo preparar la consulta: {exc}'}, status=400)

    def _analizar_plan(self):
        limite_bytes = 25 * 1024 * 1024
        try:
            longitud = int(self.headers.get('Content-Length', '0'))
            if longitud <= 0 or longitud > limite_bytes:
                self._send_json({'error': 'El archivo debe tener entre 1 byte y 25 MB.'}, status=400)
                return

            tipo_contenido = self.headers.get_content_type()
            frontera = self.headers.get_boundary()
            if tipo_contenido != 'multipart/form-data' or not frontera:
                self._send_json({'error': 'La solicitud debe ser multipart/form-data.'}, status=400)
                return

            cuerpo = self.rfile.read(longitud)
            encabezado = (
                f'Content-Type: multipart/form-data; boundary={frontera}\r\n'
                'MIME-Version: 1.0\r\n\r\n'
            ).encode('utf-8')
            formulario = BytesParser(policy=default).parsebytes(encabezado + cuerpo)
            parte_plan = next(
                (
                    parte for parte in formulario.iter_parts()
                    if parte.get_content_disposition() == 'form-data'
                    and parte.get_filename()
                ),
                None,
            )
            if parte_plan is None:
                self._send_json({'error': 'Debes seleccionar un archivo .sqlplan.'}, status=400)
                return

            nombre = parte_plan.get_filename()
            if not nombre.lower().endswith('.sqlplan'):
                self._send_json({'error': 'Solo se aceptan archivos con extensión .sqlplan.'}, status=400)
                return

            contenido = parte_plan.get_payload(decode=True) or b''
            hallazgos, operadores, memoria = analizar_plan_ejecucion(contenido)
        except ET.ParseError:
            self._send_json({'error': 'El archivo no contiene un plan XML válido de SQL Server.'}, status=400)
            return
        except (TypeError, ValueError) as exc:
            self._send_json({'error': f'No se pudo leer el archivo: {exc}'}, status=400)
            return
        except Exception as exc:  # pragma: no cover - red de seguridad del endpoint HTTP
            self._send_json({'error': f'Error interno al analizar el plan: {exc}'}, status=500)
            return

        resumen = {severidad: 0 for severidad in ('critico', 'alto', 'medio', 'bajo')}
        hallazgos_serializados = []
        for hallazgo in hallazgos:
            severidad = hallazgo.severidad.value.lower()
            resumen[severidad] += 1
            hallazgos_serializados.append({
                'linea': hallazgo.linea,
                'origen': hallazgo.origen.value,
                'severidad': severidad,
                'regla': hallazgo.regla,
                'mensaje': hallazgo.mensaje,
            })

        operadores_serializados = [
            {
                'nodoId': operador.nodo_id,
                'operacionFisica': operador.operacion_fisica,
                'operacionLogica': operador.operacion_logica,
                'estimacionFilas': operador.estimacion_filas,
                'filasReales': operador.filas_reales,
                'filasLeidas': operador.filas_leidas,
                'lecturasLogicas': operador.lecturas_logicas,
                'objeto': operador.objeto,
                'tieneSpill': operador.tiene_spill,
                'tieneConversionImplicita': operador.tiene_conversion_implicita,
            }
            for operador in operadores
        ]
        memoria_serializada = None if memoria is None else {
            'solicitadaKb': memoria.memoria_solicitada_kb,
            'concedidaKb': memoria.memoria_concedida_kb,
            'maximaUtilizadaKb': memoria.memoria_maxima_utilizada_kb,
        }
        self._send_json({
            'archivo': nombre,
            'resumen': resumen,
            'hallazgos': hallazgos_serializados,
            'operadores': operadores_serializados,
            'memoria': memoria_serializada,
        })

    def _send_json(self, payload, status=200):
        body = json.dumps(payload).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            # El navegador puede cancelar una consulta lenta de Ollama.
            return

    def log_message(self, format, *args):
        return


if __name__ == '__main__':
    server = ThreadingHTTPServer(('0.0.0.0', 8000), GenesisHandler)
    print('Servidor Genesis IA corriendo en http://localhost:8000')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
