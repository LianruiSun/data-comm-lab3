"""Fibonacci HTTP server for Lab 3 (port 9090)."""

import json
import os
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit


PORT = int(os.environ.get("FS_PORT", "9090"))


def fibonacci(number):
    previous, current = 0, 1
    for _ in range(number):
        previous, current = current, previous + current
    return previous


class FibonacciHandler(BaseHTTPRequestHandler):
    def respond(self, status, body):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlsplit(self.path)
        if path.path != "/fibonacci":
            return self.respond(404, "Not Found\n")
        values = parse_qs(path.query)
        try:
            number = int(values["number"][0])
            if number < 0 or len(values["number"]) != 1:
                raise ValueError
        except (KeyError, IndexError, ValueError):
            return self.respond(400, "number must be a nonnegative integer\n")
        self.respond(200, f"{fibonacci(number)}\n")

    def do_PUT(self):
        if urlsplit(self.path).path != "/register":
            return self.respond(404, "Not Found\n")
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 4096:
                raise ValueError
            data = json.loads(self.rfile.read(length))
            hostname, ip, as_ip = (data[key] for key in ("hostname", "ip", "as_ip"))
            as_port = int(data["as_port"])
            if not all(isinstance(value, str) and value for value in (hostname, ip, as_ip)):
                raise ValueError
            if not 1 <= as_port <= 65535 or any(char.isspace() for char in hostname + ip):
                raise ValueError
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            return self.respond(400, "Invalid registration JSON\n")

        message = f"TYPE=A\nNAME={hostname} VALUE={ip} TTL=10\n"
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.settimeout(3)
                sock.sendto(message.encode("utf-8"), (as_ip, as_port))
                response, _ = sock.recvfrom(4096)
        except OSError:
            return self.respond(502, "Authoritative server unavailable\n")
        if not response.startswith(b"201"):
            return self.respond(502, "Authoritative server rejected registration\n")
        self.respond(201, "Created\n")


if __name__ == "__main__":
    with ThreadingHTTPServer(("0.0.0.0", PORT), FibonacciHandler) as server:
        print(f"Fibonacci server listening on HTTP {PORT}", flush=True)
        server.serve_forever()
