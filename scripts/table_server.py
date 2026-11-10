#!/usr/bin/env python3
"""Open the tarot table in the user's browser and wait until they finish drawing.

The page (assets/tarot-table.html) posts its result back to this server when the
user reaches the result step. The script then prints the result and exits, so the
agent can interpret it right away without the user copying anything.

Usage:
  table_server.py [--q "question"] [--spread celtic-cross | --n 4 --labels "a|b|c|d"]
                  [--ctx "context"] [--rev 0] [--timeout 900] [--no-open] [--json]

Output (stdout): the result text block that starts with
"🔮 ผลการจั่วไพ่จากโต๊ะไพ่ทาโรต์" (or, with --json, one JSON object with
"text" and "data"). Progress messages go to stderr.

Exit codes: 0 result received · 2 timed out · 1 error.
Only binds 127.0.0.1. A random token in the URL must come back with the result.
"""

import argparse
import http.server
import json
import secrets
import sys
import threading
import urllib.parse
import webbrowser
from pathlib import Path

PAGE = Path(__file__).resolve().parent.parent / "assets" / "tarot-table.html"
MAX_BODY = 64 * 1024


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def main():
    ap = argparse.ArgumentParser(description="Serve the tarot table locally and wait for the user's draw.")
    ap.add_argument("--q", help="คำถามที่เกลาแล้ว (กรอกให้ล่วงหน้า)")
    ap.add_argument("--spread", help="id สเปรด ถ้าใส่ หน้าเว็บจะข้ามไปหน้าคำถามเลย")
    ap.add_argument("--n", type=int, help="จำนวนใบสำหรับสเปรดกำหนดเอง")
    ap.add_argument("--labels", help="ชื่อตำแหน่งสำหรับสเปรดกำหนดเอง คั่นด้วย |")
    ap.add_argument("--ctx", help="บริบทที่ผู้ใช้เล่าไว้แล้ว (กรอกให้ล่วงหน้า)")
    ap.add_argument("--rev", choices=["0", "1"], help="0 = ไม่ใช้ไพ่กลับหัว")
    ap.add_argument("--timeout", type=int, default=900, help="วินาทีที่รอ (ค่าเริ่มต้น 900)")
    ap.add_argument("--no-open", action="store_true", help="ไม่เปิดเบราว์เซอร์ให้ แค่พิมพ์ URL")
    ap.add_argument("--json", action="store_true", help="พิมพ์ผลเป็น JSON {text, data}")
    args = ap.parse_args()

    if not PAGE.exists():
        log(f"ไม่พบไฟล์หน้าเว็บ: {PAGE}")
        sys.exit(1)

    token = secrets.token_urlsafe(16)
    state = {"result": None}
    done = threading.Event()

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):  # keep stdout clean for the agent
            pass

        def _send(self, code, body=b"", ctype="text/plain; charset=utf-8"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if body:
                self.wfile.write(body)

        def do_GET(self):
            path = urllib.parse.urlparse(self.path).path
            if path in ("/", "/tarot-table.html"):
                self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
            else:
                self._send(404, b"not found")

        def do_POST(self):
            u = urllib.parse.urlparse(self.path)
            if u.path != "/result":
                return self._send(404, b"not found")
            got = urllib.parse.parse_qs(u.query).get("t", [""])[0]
            if not secrets.compare_digest(got, token):
                return self._send(403, b"bad token")
            if done.is_set():
                return self._send(410, b"already received")
            if "application/json" not in (self.headers.get("Content-Type") or ""):
                return self._send(415, b"json only")
            try:
                n = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                n = 0
            if not 0 < n <= MAX_BODY:
                return self._send(413, b"too large")
            try:
                payload = json.loads(self.rfile.read(n).decode("utf-8"))
                text = str(payload["text"])
                if not text.startswith("🔮"):
                    raise ValueError("unexpected text")
            except Exception:
                return self._send(400, b"bad payload")
            state["result"] = {"text": text, "data": payload.get("data")}
            self._send(200, b"ok")
            done.set()

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = srv.server_address[1]
    params = {"ret": token}
    for k in ("q", "spread", "n", "labels", "ctx", "rev"):
        v = getattr(args, k)
        if v not in (None, ""):
            params[k] = str(v)
    url = f"http://127.0.0.1:{port}/tarot-table.html?" + urllib.parse.urlencode(params)

    threading.Thread(target=srv.serve_forever, daemon=True).start()
    log(f"เปิดโต๊ะไพ่แล้ว: {url}")
    log(f"รอผู้ใช้สับ ตัด จั่ว และเปิดไพ่ (สูงสุด {args.timeout} วินาที)")
    if not args.no_open:
        try:
            webbrowser.open(url)
        except Exception:
            log("เปิดเบราว์เซอร์อัตโนมัติไม่ได้ ให้ผู้ใช้เปิด URL ด้านบนเอง")

    ok = done.wait(args.timeout)
    srv.shutdown()
    if not ok:
        log("หมดเวลารอ ผู้ใช้ยังจั่วไพ่ไม่เสร็จ ถามผู้ใช้ว่าจะเปิดใหม่หรือวางผลเองในแชท")
        sys.exit(2)
    res = state["result"]
    if args.json:
        print(json.dumps(res, ensure_ascii=False))
    else:
        print(res["text"])


if __name__ == "__main__":
    main()
