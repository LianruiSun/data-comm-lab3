"""Simplified authoritative DNS server for Lab 3 (UDP port 53533)."""

import json
import os
import socketserver
import time
from pathlib import Path


PORT = int(os.environ.get("AS_PORT", "53533"))
RECORDS_FILE = Path(
    os.environ.get("AS_RECORDS_FILE", Path(__file__).with_name("records.json"))
)


def parse_message(message):
    fields = {}
    for item in message.split():
        key, separator, value = item.partition("=")
        if not separator or not key or not value or key in fields:
            raise ValueError("Malformed DNS field")
        fields[key] = value
    if fields.get("TYPE") != "A" or not fields.get("NAME"):
        raise ValueError("Only Type A records are supported")
    return fields


def read_records():
    if not RECORDS_FILE.exists():
        return {}
    with RECORDS_FILE.open(encoding="utf-8") as stream:
        return json.load(stream)


def save_records(records):
    RECORDS_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary_file = RECORDS_FILE.with_suffix(RECORDS_FILE.suffix + ".tmp")
    with temporary_file.open("w", encoding="utf-8") as stream:
        json.dump(records, stream)
    temporary_file.replace(RECORDS_FILE)


class DNSHandler(socketserver.BaseRequestHandler):
    def handle(self):
        packet, sock = self.request
        try:
            fields = parse_message(packet.decode("utf-8"))
            records = read_records()
            hostname = fields["NAME"]

            if "VALUE" in fields or "TTL" in fields:
                if set(fields) != {"TYPE", "NAME", "VALUE", "TTL"}:
                    raise ValueError("Registration requires TYPE, NAME, VALUE, TTL")
                ttl = int(fields["TTL"])
                if ttl <= 0:
                    raise ValueError("TTL must be positive")
                records[hostname] = {
                    "value": fields["VALUE"],
                    "ttl": ttl,
                    "expires_at": time.time() + ttl,
                }
                save_records(records)
                response = "201 Created\n"
            else:
                if set(fields) != {"TYPE", "NAME"}:
                    raise ValueError("Query requires TYPE and NAME")
                record = records.get(hostname)
                if record is None or record["expires_at"] <= time.time():
                    response = "404 Not Found\n"
                else:
                    response = (
                        f"TYPE=A\nNAME={hostname} VALUE={record['value']} "
                        f"TTL={record['ttl']}\n"
                    )
        except (UnicodeDecodeError, ValueError, json.JSONDecodeError, KeyError):
            response = "400 Bad Request\n"
        sock.sendto(response.encode("utf-8"), self.client_address)


class DNSServer(socketserver.UDPServer):
    allow_reuse_address = True


if __name__ == "__main__":
    with DNSServer(("0.0.0.0", PORT), DNSHandler) as server:
        print(f"Authoritative server listening on UDP {PORT}", flush=True)
        server.serve_forever()
