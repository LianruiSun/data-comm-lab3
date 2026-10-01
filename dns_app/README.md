# Lab 3: simplified authoritative server

The three folders are independent Python 3.11 services. They use only the Python
standard library and include a Dockerfile each.

| Service | Protocol | Default port | Endpoint |
| --- | --- | ---: | --- |
| `AS` | UDP | 53533 | Type A registration and lookup |
| `FS` | HTTP | 9090 | `PUT /register`, `GET /fibonacci?number=X` |
| `US` | HTTP | 8080 | `GET /fibonacci?hostname=...&fs_port=...&number=...&as_ip=...&as_port=...` |

## Run locally

Open three terminals in this `dns_app` directory and run:

```powershell
python AS/server.py
python FS/server.py
python US/server.py
```

Register the Fibonacci service (PowerShell):

```powershell
$body = '{"hostname":"fibonacci.com","ip":"127.0.0.1","as_ip":"127.0.0.1","as_port":"53533"}'
Invoke-WebRequest -Method Put -Uri http://127.0.0.1:9090/register -ContentType application/json -Body $body
```

Then, within 10 seconds of registering, request a result:

```powershell
Invoke-WebRequest -Uri 'http://127.0.0.1:8080/fibonacci?hostname=fibonacci.com&fs_port=9090&number=10&as_ip=127.0.0.1&as_port=53533'
```

The returned body is `55`, which is F(10). Register again if the 10-second TTL
has expired. `AS/records.json` is created automatically when registration occurs.

## Docker

Build each image from its service folder:

```powershell
docker build -t lab3-as ./AS
docker build -t lab3-fs ./FS
docker build -t lab3-us ./US
```

Place the containers on one Docker network and publish their ports. The
`ip` in the registration body must be the FS container IP address reachable
from US; `as_ip` must be the AS container IP address reachable from both FS and
US. Use `docker inspect` to find these addresses. The host-visible ports do
not replace the container ports in the JSON and browser URL.

## Verify

```powershell
python test_integration.py
```

This runs all three servers on temporary ports and checks registration, DNS
lookup, Fibonacci computation, and the required HTTP 400 responses.
