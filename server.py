import json
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlsplit

from app.analizadores.analizador_diccionario_procedimientos import verificar_diccionario
from app.analizadores.analizador_diccionario_tablas import verificar_diccionario_tablas


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

        if not sql_text or not dict_text:
            self._send_json({'error': 'Debes completar el SQL del objeto y el diccionario.'}, status=400)
            return

        try:
            if tipo == 'procedimiento':
                hallazgos = verificar_diccionario(sql_text, dict_text)
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
        self.wfile.write(body)

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
