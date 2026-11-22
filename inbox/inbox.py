"""The on-call inbox: Nagios POSTs alerts to /alert, and anyone can GET /alerts."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ALERTS = []


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        ALERTS.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
        a = ALERTS[-1]
        print(f"{a['type']:<9} {a['host']}/{a['service']} {a['state']}: {a['output']}", flush=True)
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        body = json.dumps(ALERTS).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


ThreadingHTTPServer(('0.0.0.0', 8080), Handler).serve_forever()
