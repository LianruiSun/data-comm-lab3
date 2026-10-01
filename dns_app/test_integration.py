"""Run the three services together and check the complete request path."""

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent


def free_port(socket_type):
    with socket.socket(socket.AF_INET, socket_type) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class FullFlowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tempdir = tempfile.TemporaryDirectory()
        cls.as_port = free_port(socket.SOCK_DGRAM)
        cls.fs_port = free_port(socket.SOCK_STREAM)
        cls.us_port = free_port(socket.SOCK_STREAM)
        cls.processes = []
        for name, variables in (
            ("AS", {"AS_PORT": str(cls.as_port),
                    "AS_RECORDS_FILE": str(Path(cls.tempdir.name) / "records.json")}),
            ("FS", {"FS_PORT": str(cls.fs_port)}),
            ("US", {"US_PORT": str(cls.us_port)}),
        ):
            process = subprocess.Popen(
                [sys.executable, str(ROOT / name / "server.py")],
                env={**os.environ, **variables},
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            cls.processes.append(process)
        for _ in range(40):
            try:
                with urlopen(f"http://127.0.0.1:{cls.fs_port}/missing", timeout=0.2):
                    pass
            except HTTPError:
                break
            except OSError:
                time.sleep(0.1)
        else:
            raise RuntimeError("HTTP servers did not start")

    @classmethod
    def tearDownClass(cls):
        for process in cls.processes:
            process.terminate()
        for process in cls.processes:
            process.wait(timeout=5)
        cls.tempdir.cleanup()

    def test_register_lookup_and_compute(self):
        registration = {
            "hostname": "fibonacci.com",
            "ip": "127.0.0.1",
            "as_ip": "127.0.0.1",
            "as_port": str(self.as_port),
        }
        request = Request(
            f"http://127.0.0.1:{self.fs_port}/register",
            data=json.dumps(registration).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="PUT",
        )
        with urlopen(request, timeout=5) as response:
            self.assertEqual(response.status, 201)

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(3)
            sock.sendto(b"TYPE=A\nNAME=fibonacci.com\n", ("127.0.0.1", self.as_port))
            answer, _ = sock.recvfrom(4096)
        self.assertIn(b"NAME=fibonacci.com VALUE=127.0.0.1", answer)

        query = (
            f"http://127.0.0.1:{self.us_port}/fibonacci?"
            f"hostname=fibonacci.com&fs_port={self.fs_port}&number=10"
            f"&as_ip=127.0.0.1&as_port={self.as_port}"
        )
        with urlopen(query, timeout=5) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(response.read(), b"55\n")

        with self.assertRaises(HTTPError) as missing:
            urlopen(f"http://127.0.0.1:{self.us_port}/fibonacci?number=10")
        self.assertEqual(missing.exception.code, 400)

        with self.assertRaises(HTTPError) as malformed:
            urlopen(f"http://127.0.0.1:{self.fs_port}/fibonacci?number=nope")
        self.assertEqual(malformed.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
