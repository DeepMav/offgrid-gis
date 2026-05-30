#!/usr/bin/env python3
"""3DGS/점군 뷰어용 정적 서버.
- COOP/COEP (SharedArrayBuffer/cross-origin isolation)
- HTTP Range(206) 지원 → Potree 옥트리 스트리밍 필수
- 캐시 끔, .ply/.ksplat/.bin MIME
- POST /upload?name=x.ksplat → viewer 폴더 저장
사용: python3 server.py [port=8080]
"""
import os
import re
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

VIEWER_DIR = os.path.dirname(os.path.abspath(__file__))


class Handler(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map,
                      ".ply": "application/octet-stream",
                      ".ksplat": "application/octet-stream",
                      ".bin": "application/octet-stream",
                      ".js": "text/javascript",
                      ".mjs": "text/javascript",
                      ".json": "application/json"}

    def end_headers(self):
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Embedder-Policy", "require-corp")
        self.send_header("Cross-Origin-Resource-Policy", "cross-origin")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Accept-Ranges", "bytes")
        super().end_headers()

    def do_GET(self):
        rng = self.headers.get("Range")
        if not rng:
            return super().do_GET()
        path = self.translate_path(self.path)
        if not os.path.isfile(path):
            return super().do_GET()
        m = re.match(r"bytes=(\d+)-(\d*)", rng)
        if not m:
            return super().do_GET()
        size = os.path.getsize(path)
        start = int(m.group(1))
        end = int(m.group(2)) if m.group(2) else size - 1
        end = min(end, size - 1)
        if start > end or start >= size:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{size}")
            self.end_headers()
            return
        length = end - start + 1
        ctype = self.guess_type(path)
        self.send_response(206)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(length))
        self.end_headers()
        with open(path, "rb") as f:
            f.seek(start)
            remaining = length
            while remaining > 0:
                chunk = f.read(min(65536, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def do_POST(self):
        if not self.path.startswith("/upload"):
            self.send_error(404); return
        m = re.search(r"[?&]name=([^&]+)", self.path)
        name = os.path.basename(m.group(1) if m else "scene.ksplat")
        if not name.endswith(".ksplat"):
            self.send_error(400, "name must end with .ksplat"); return
        length = int(self.headers.get("Content-Length", 0))
        data = self.rfile.read(length)
        with open(os.path.join(VIEWER_DIR, name), "wb") as f:
            f.write(data)
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(f"saved {name} ({length} bytes)".encode())


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    print(f"뷰어: http://localhost:{port}/  (COOP/COEP + Range, Ctrl+C 종료)")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
