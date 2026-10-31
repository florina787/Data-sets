"""TEST-ONLY stand-in for an Ollama server, used to exercise the gateway's HTTP runtime.

It is never used by the application. Real answers come only from the user's own Qwen model.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class FakeOllama:
    def __init__(self, reply: str = '{"summary": "AC-204 vibration rose."}', model: str = "qwen2.5:1.5b-instruct-q4_K_M", delay_chunks: float = 0.0):
        self.reply, self.model, self.calls = reply, model, []
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):  # quiet
                pass

            def do_GET(self):
                if self.path == "/api/tags":
                    body = json.dumps({"models": [{"name": outer.model, "size": 986_000_000, "details": {"family": "qwen2", "parameter_size": "1.5B", "quantization_level": "Q4_K_M"}}]}).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                else:
                    self.send_response(404)
                    self.end_headers()

            def do_POST(self):
                n = int(self.headers.get("Content-Length", 0))
                req = json.loads(self.rfile.read(n))
                outer.calls.append(req)
                self.send_response(200)
                self.send_header("Content-Type", "application/x-ndjson")
                self.end_headers()
                words = outer.reply.split(" ")
                import time

                for i, w in enumerate(words):
                    time.sleep(delay_chunks)
                    self.wfile.write((json.dumps({"message": {"content": w + (" " if i < len(words) - 1 else "")}, "done": False}) + "\n").encode())
                    self.wfile.flush()
                self.wfile.write((json.dumps({"message": {"content": ""}, "done": True, "prompt_eval_count": 42, "eval_count": len(words),
                                              "eval_duration": 50_000_000}) + "\n").encode())

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
