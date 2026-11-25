"""Recording proxy between the benchmark clients and vLLM (server-local, CPU only).
Listens on 127.0.0.1:18231 and forwards to the vLLM OpenAI server on 127.0.0.1:18230. For /v1/chat/completions it adds
vLLM's "return_token_ids": true and appends {request, response} to ops/proxy_log/<tag>.jsonl, so every decision step has
its exact prompt and completion token ids. Clients see the normal OpenAI response (extra fields are ignored).
Usage: AB_PROXY_TAG=dojo python ab_proxy.py"""
import json
import os
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

UP = os.environ.get("AB_UPSTREAM", "http://127.0.0.1:18230")
PORT = int(os.environ.get("AB_PROXY_PORT", "18231"))
LOGDIR = Path("/home/project-b/LJW/agentbench2/ops/proxy_log")
LOGDIR.mkdir(parents=True, exist_ok=True)
TAG = os.environ.get("AB_PROXY_TAG", "default")
LOCK = threading.Lock()


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _forward(self, method, body=None):
        req = urllib.request.Request(UP + self.path, data=body, method=method,
                                     headers={"Content-Type": "application/json", "Authorization": "Bearer local"})
        try:
            with urllib.request.urlopen(req, timeout=1800) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def do_GET(self):
        code, data = self._forward("GET")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        rec_req = None
        if self.path.rstrip("/").endswith("/chat/completions"):
            try:
                rec_req = json.loads(raw)
                rec_req["return_token_ids"] = True
                raw = json.dumps(rec_req).encode()
            except ValueError:
                rec_req = None
        t0 = time.time()
        code, data = self._forward("POST", raw)
        if rec_req is not None and code == 200:
            try:
                resp = json.loads(data)
                with LOCK, (LOGDIR / f"{TAG}.jsonl").open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps({"t": time.time(), "sec": round(time.time() - t0, 2), "request": rec_req,
                                         "response": resp}) + "\n")
            except ValueError:
                pass
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    print(f"proxy :{PORT} -> {UP}, log {LOGDIR}/{TAG}.jsonl", flush=True)
    class Srv(ThreadingHTTPServer):
        request_queue_size = 256
        daemon_threads = True

    Srv(("127.0.0.1", PORT), H).serve_forever()
