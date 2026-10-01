"""User-facing HTTP server for Lab 3 (port 8080)."""

import os
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import urlopen


PORT = int(os.environ.get("US_PORT", "8080"))


class UserHandler(BaseHTTPRequestHandler):
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
            if any(len(values[key]) != 1 for key in
                   ("hostname", "fs_port", "number", "as_ip", "as_port")):
                raise ValueError
            hostname = values["hostname"][0]
            fs_port = int(values["fs_port"][0])
            number = int(values["number"][0])
            as_ip = values["as_ip"][0]
            as_port = int(values["as_port"][0])
            if (not hostname or any(char.isspace() for char in hostname)
                    or not as_ip or number < 0
                    or not 1 <= fs_port <= 65535
                    or not 1 <= as_port <= 65535):
                raise ValueError
        except (KeyError, ValueError):
            return self.respond(400, "Missing or invalid query parameter\n")

        query = f"TYPE=A\nNAME={hostname}\n"
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.settimeout(3)
                sock.sendto(query.encode("utf-8"), (as_ip, as_port))
                packet, _ = sock.recvfrom(4096)
        except OSError:
            return self.respond(502, "Authoritative server unavailable\n")

        response = packet.decode("utf-8", errors="replace")
        if response.startswith("404"):
            return self.respond(404, "Hostname not registered\n")
        fields = {}
        try:
            for item in response.split():
                key, separator, value = item.partition("=")
                if separator:
                    fields[key] = value
            if fields["TYPE"] != "A" or fields["NAME"] != hostname:
                raise ValueError
            fs_ip = fields["VALUE"]
        except (KeyError, ValueError):
            return self.respond(502, "Invalid authoritative response\n")

        url = f"http://{fs_ip}:{fs_port}/fibonacci?{urlencode({'number': number})}"
        try:
            with urlopen(url, timeout=5) as result:
                body = result.read().decode("utf-8")
        except HTTPError as error:
            return self.respond(error.code, error.read().decode("utf-8", errors="replace"))
        except (URLError, TimeoutError, UnicodeDecodeError):
            return self.respond(502, "Fibonacci server unavailable\n")
        self.respond(200, body)


if __name__ == "__main__":
    with ThreadingHTTPServer(("0.0.0.0", PORT), UserHandler) as server:
        print(f"User server listening on HTTP {PORT}", flush=True)
        server.serve_forever()
