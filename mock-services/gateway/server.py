import http.server
import json
import os
import random
import urllib.request
import urllib.error

PORT = int(os.environ.get("PORT", "8080"))
SHARD_COUNT = int(os.environ.get("SHARD_COUNT", "1"))

OPERATOR_ENDPOINT = os.environ.get(
    "OPERATOR_ENDPOINT",
    "operator.platform.svc.cluster.local:9000",
)

OPERATOR_SERVICE_TEMPLATE = os.environ.get(
    "OPERATOR_SERVICE_TEMPLATE",
    "operator-{shard}.platform.svc.cluster.local:9000",
)

CLUSTER_NAME = os.environ.get("CLUSTER_NAME", "unknown")


def get_operator_host(shard=None):
    if SHARD_COUNT > 1:
        return OPERATOR_SERVICE_TEMPLATE.format(shard=shard)
    return OPERATOR_ENDPOINT


def call_operator(path, method="POST", body=None, shard=None):
    host = get_operator_host(shard)
    url = f"http://{host}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read()), resp.status
    except urllib.error.URLError as e:
        return {"error": f"cannot reach operator at {host}: {e.reason}"}, 502
    except Exception as e:
        return {"error": f"unexpected error calling operator at {host}: {str(e)}"}, 500


class GatewayHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/healthz":
            self._json_response(200, {"status": "ok", "role": "gateway", "cluster": CLUSTER_NAME})

        elif self.path == "/inference":
            shard = random.randint(0, SHARD_COUNT - 1) if SHARD_COUNT > 1 else None
            host = get_operator_host(shard)
            print(f"[gateway] routing to operator at {host}")

            alloc_resp, alloc_status = call_operator("/allocate", shard=shard)
            if alloc_status != 200:
                self._json_response(alloc_status, alloc_resp)
                return

            instance_id = alloc_resp.get("instance_id", "unknown")
            print(f"[gateway] got instance {instance_id}")

            release_resp, release_status = call_operator(
                "/release", body={"instance_id": instance_id}, shard=shard
            )

            resp = {
                "status": "ok",
                "instance_id": instance_id,
                "allocated": alloc_status == 200,
                "released": release_status == 200,
                "operator_host": host,
                "cluster": CLUSTER_NAME,
            }
            if SHARD_COUNT > 1:
                resp["shard"] = shard
            self._json_response(200, resp)

        elif self.path == "/discovery":
            if SHARD_COUNT > 1:
                results = {}
                for s in range(SHARD_COUNT):
                    host = get_operator_host(s)
                    resp, status = call_operator("/info", method="GET", shard=s)
                    results[f"operator-{s}"] = {
                        "host": host,
                        "reachable": status == 200,
                        "response": resp,
                    }
                self._json_response(200, results)
            else:
                resp, status = call_operator("/info", method="GET")
                self._json_response(200, {
                    "operator": {
                        "endpoint": OPERATOR_ENDPOINT,
                        "reachable": status == 200,
                        "response": resp,
                    }
                })

        else:
            self._json_response(404, {"error": "not found"})

    def _json_response(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())

    def log_message(self, format, *args):
        print(f"[gateway] {args[0]}")


if __name__ == "__main__":
    server = http.server.HTTPServer(("0.0.0.0", PORT), GatewayHandler)
    print(f"gateway listening on :{PORT}")
    if SHARD_COUNT > 1:
        print(f"  mode: sharded ({SHARD_COUNT} shards)")
        print(f"  template: {OPERATOR_SERVICE_TEMPLATE}")
    else:
        print(f"  mode: single operator")
        print(f"  endpoint: {OPERATOR_ENDPOINT}")
    server.serve_forever()
