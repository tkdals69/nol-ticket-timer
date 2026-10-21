"""NOL 예매 보조 타이머 - 로컬 서버.

역할:
  1. index.html 을 http://127.0.0.1:8787 로 서빙한다.
  2. /time 엔드포인트에서 nol.yanolja.com 에 HEAD 요청을 보내
     응답의 Date 헤더(서버 시각)와 로컬 송수신 시각을 돌려준다.
     브라우저는 CORS 때문에 타 도메인 응답 헤더를 못 읽으므로 이 프록시가 필요하다.

요청 빈도는 브라우저가 "동기화" 버튼을 누를 때 1초 남짓 동안 10회 안팎이며,
그 외에는 요청하지 않는다. 자동 클릭·예매 요청은 하지 않는다.
"""

import json
import sys
import time
import urllib.request
from email.utils import parsedate_to_datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOST = "127.0.0.1"
PORT = 8787
TIME_SOURCE_URL = "https://nol.yanolja.com/"
REQUEST_TIMEOUT_SEC = 5
USER_AGENT = "Mozilla/5.0 (nol-ticket-timer; local clock sync)"

BASE_DIR = Path(__file__).resolve().parent
INDEX_PATH = BASE_DIR / "index.html"


def fetch_server_time():
    """HEAD 요청 1회. 로컬 송신/수신 시각(ms)과 서버 Date 헤더(ms)를 반환한다."""
    request = urllib.request.Request(
        TIME_SOURCE_URL, method="HEAD", headers={"User-Agent": USER_AGENT}
    )
    sent_at = time.time() * 1000
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SEC) as response:
            date_header = response.headers.get("Date")
    except urllib.error.HTTPError as error:
        # 4xx/5xx 여도 Date 헤더는 대개 붙어 온다.
        date_header = error.headers.get("Date")
    received_at = time.time() * 1000

    if not date_header:
        raise RuntimeError("Date header missing in response")

    server_ms = parsedate_to_datetime(date_header).timestamp() * 1000
    return {"sentAt": sent_at, "receivedAt": received_at, "serverMs": server_ms}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/time"):
            self._handle_time()
        elif self.path in ("/", "/index.html"):
            self._send_file(INDEX_PATH, "text/html; charset=utf-8")
        else:
            self.send_error(404)

    def _handle_time(self):
        try:
            payload = fetch_server_time()
            status = 200
        except Exception as error:  # noqa: BLE001 - 사용자에게 사유를 그대로 보여준다
            payload = {"error": str(error)}
            status = 502
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        # 외부에 게시한 타이머 페이지가 이 로컬 프록시를 쓸 수 있도록 허용한다.
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path, content_type):
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        sys.stdout.write("%s - %s\n" % (self.log_date_time_string(), fmt % args))


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"NOL 예매 보조 타이머: http://{HOST}:{PORT}  (Ctrl+C 로 종료)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
