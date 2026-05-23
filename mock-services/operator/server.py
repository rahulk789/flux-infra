import http.server
import json
import os
import random
import string

SHARD_ID = os.environ.get("SHARD_ID", "0")
PORT = int(os.environ.get("PORT", "9000"))


def random_instance_id():
    return f"gpu-{''.join(random.choices(string.ascii_lowercase, k=6))}"


class OperatorHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/healthz":
            self._json_response(200, {"status": "ok", "shard": SHARD_ID})
        elif self.path == "/info":
            self._json_response(200, {
                "shard_id": SHARD_ID,
                "hostname": os.environ.get("HOSTNAME", "unknown"),
            })
        else:
            self._json_response(404, {"error": "not found"})

    def do_POST(self):
        if self.path == "/allocate":
            instance_id = random_instance_id()
            print(f"[operator] allocated instance {instance_id}")
            self._json_response(200, {
                "instance_id": instance_id,
                "shard": SHARD_ID,
            })
        elif self.path == "/release":
            body = self._read_body()
            print(f"[operator] released instance {body.get('instance_id', '?')}")
            self._json_response(200, {"status": "released"})
        else:
            self._json_response(404, {"error": "not found"})

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        try:
            return json.loads(self.rfile.read(length))
        except Exception:
            return {}

    def _json_response(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, format, *args):
        print(f"[operator] {args[0]}")


if __name__ == "__main__":
    server = http.server.HTTPServer(("0.0.0.0", PORT), OperatorHandler)
    print(f"operator listening on :{PORT}")
    server.serve_forever()
