# otgctl

A command-line tool for making [Open Traffic Generator (OTG)](https://otg.dev) REST or gRPC API calls from YAML, JSON, or protobuf text-format input.

## Installation

```
pip install .
```

For gRPC transport or protobuf text-format input, install the optional snappi dependency:

```
pip install '.[snappi]'
```

HTTP requests with YAML or JSON input do not require snappi, grpcio, or protobuf.

Building from source uses the PEP 517/PEP 621 configuration in
`pyproject.toml` and requires setuptools 61 or newer plus `wheel`. Installing
a prebuilt wheel does not require setuptools. In a constrained build
environment where those tools are already installed, use:

```
python3 -m pip install --no-build-isolation .
```

## Development

Run the tests against the source tree with:

```
python3 -m pytest
```

To build a wheel and run the tests against that installed wheel in a clean
environment, first without snappi and then with it installed:

```
sh ci/test.sh
```

The wrapper uses `ci/Dockerfile.test` and accepts `PYTHON_VERSION` and `OTGCTL_TEST_IMAGE` environment
variables, for example `PYTHON_VERSION=3.13 sh ci/test.sh`.

See [`docs/RELEASE_PROCESS.md`](docs/RELEASE_PROCESS.md) for the release
checklist and artifact-publishing process.

## Usage

```
otgctl [-s SERVER] [-m METHOD] [-o json] [-k] [-v] [--cert FILE] [--key FILE] [--timeout SECONDS] [--list-methods] FILE_OR_STRING ...
```

### Options

| Flag | Description |
|------|-------------|
| `-s`, `--server` | OTG server URL: `http://`, `https://`, or `grpc://host:port` (default: `$OTG_API` or `https://localhost:8443`) |
| `-m`, `--method` | OTG method name or REST path (see [Methods](#methods)) |
| `-o`, `--output-format` | `yaml` (default) or `json` |
| `-k`, `--insecure` | Skip HTTP TLS certificate verification |
| `-v`, `--verbose` | Print request and response details to stderr |
| `--cert` | Client certificate file for mTLS |
| `--key` | Client private key file for mTLS (optional if cert file contains both) |
| `--timeout` | HTTP request timeout or gRPC deadline in seconds (default: 30) |
| `--list-methods` | List available method names for `-m` and exit |
| `--version` | Print the code version and exit |

For GET methods (GetConfig, GetVersion), input files can be omitted:

```
otgctl -m GetVersion
```

### gRPC transport

Use a `grpc://host:port` server URL to select plaintext gRPC:

```
otgctl -s grpc://otg-server:40051 -m GetVersion
otgctl -s grpc://otg-server:40051 config.yaml
otgctl -s grpc://otg-server:40051 -m GetMetrics //flow -o json
otgctl -s grpc://otg-server:40051 -m GetStates //ipv4_neighbors
otgctl -s grpc://otg-server:40051 -m GetCapture capture_request.yaml > capture.pcap
```

`OTG_API` can also contain a `grpc://` URL. Method names, operation IDs,
known REST paths, and explicit verb/path pairs select the corresponding RPC.
Custom HTTP endpoints have no gRPC equivalent.

Each input entry sends exactly one unary RPC, in order, over a shared channel.
There are no automatic configuration reads, merges, or version checks.
Requests use the same bodies as HTTP. `GetConfig` and `GetVersion` use empty
requests. Capture responses are written as raw bytes when stdout is redirected.
Structured responses use protobuf JSON conventions, including strings for
64-bit integer fields.

gRPC can send only methods and fields supported by the installed snappi schema.
Unknown fields in YAML/JSON requests are rejected before sending the RPC.
Unknown textproto fields are omitted with a warning, as described below.
The `//foo` shorthand includes the selected empty object:
`{"choice": "foo", "foo": {}}`. This makes `GetMetrics //flow` and
`GetStates //ipv4_neighbors` work with both transports when the corresponding
resources are configured. YAML/JSON bodies are sent as supplied; include the
selected object explicitly when the server requires it.
The client accepts unary responses up to 64 MiB; streaming RPCs are not selected
automatically. `--timeout` sets a deadline for each RPC.

TLS gRPC (`grpcs://`), `--cert`, and `--key` are not supported for this
transport. `-k` and `OTG_INSECURE` only affect HTTP certificate verification;
`grpc://` always uses plaintext.

### Environment Variables

| Variable | Description |
|----------|-------------|
| `OTG_API` | default server URL |
| `OTG_INSECURE` | when set to `true`, `1`, or another non-false value, behaves like `-k` |

### Exit Codes

Exit codes:

- `0`: all requests completed with 2xx HTTP status or gRPC OK status.
- `1`: input parsing failed, method resolution failed, request execution
  failed, an HTTP response was non-2xx, or an RPC returned a gRPC error.
- `2`: command-line usage error from argparse.

### Input formats

otgctl accepts four input formats. Multiple inputs can be given on a single command line and are executed sequentially.

#### 1. YAML with method and request

When the YAML contains `method` and `request` keys, the method is taken from the file and the request body is sent as-is. Files may contain multiple YAML documents separated by `---`, each executed in order.

```yaml
method: SetConfig
request:
  ports:
  - location: Ethernet1
    name: p1
  flows:
  - name: f1
    tx_rx:
      choice: port
      port:
        tx_name: p1
```

```
otgctl -s https://otg-server:8443 config.yaml
```

This format is produced by OTG RPC loggers (both gRPC and HTTP) and can be replayed directly.

#### 2. Raw data (YAML or JSON)

When the input has no `method` key, you must supply one with `-m`:

```
otgctl -s https://otg-server:8443 -m SetConfig traffic.yaml
otgctl -s https://otg-server:8443 -m SetConfig config.json
```

JSON files are detected by `.json` extension.

#### 3. Protobuf text format

Files ending in `.textproto`, `.textpb`, or `.pbtxt` are parsed using the
protobuf request model from the optional `snappi` package. Select the gRPC
operation with `-m`:

```
pip install 'otgctl[snappi]'
otgctl -s https://otg-server:8443 -m SetConfig config.textproto
```

Textproto files must use the protobuf request message for the selected method.
For example, `SetConfig` input includes a top-level `config` field:

```textproto
config {
  ports { name: "p1" location: "eth1" }
}
```

Fields unknown to the installed snappi schema cannot be sent from textproto
input. otgctl prints a warning and omits those fields, for both HTTP and gRPC.
Upgrade snappi to send fields introduced in a newer schema.

gRPC transport requires a compatible snappi schema for every input format.
HTTP transport can send newer fields without snappi validation when using
YAML or JSON input.

#### 4. API path

A compact notation for simple requests, prefixed with `//`. The slash-separated path builds a nested object with `choice` keys at each level. The leaf segment contains one or more `key=value` pairs.

```
otgctl -m SetControlState //traffic/flow_transmit/state=start
```

This is equivalent to sending:

```yaml
choice: traffic
traffic:
  choice: flow_transmit
  flow_transmit:
    state: start
```

**Multiple keys** are separated by `;`, and **list values** by `,`:

```
otgctl -m GetMetrics '//port/port_names=Ethernet1,Ethernet2;column_names=transmit,capture'
```

Produces:

```yaml
choice: port
port:
  port_names:
  - Ethernet1
  - Ethernet2
  column_names:
  - transmit
  - capture
```

Keys ending in "s" always produce a list, even with a single value (matching the OTG API convention where plural property names are arrays). Non-plural keys with commas also produce a list.

A path ending in a choice includes an empty object for that choice, e.g.,
```
otgctl -m GetMetrics //flow
```

Produces:

```yaml
choice: flow
flow: {}
```

This also applies to nested choices: `//traffic/flow_transmit` produces
`{"choice": "traffic", "traffic": {"choice": "flow_transmit", "flow_transmit": {}}}`.

The `//` prefix distinguishes an API path from a file path, so there is no ambiguity with files that start with `/`.

##### API path syntax limitations

The `//` API-path syntax is intended for simple string-valued requests. It does
not perform YAML/JSON type conversion: values are sent as strings, except that
comma-separated values and keys ending in `s` become lists of strings. Use YAML
or JSON input when you need booleans, numbers, nested arrays, escaping commas,
or more complex request bodies. Empty path segments and keys are rejected, as
are duplicate keys in a leaf.

#### Stdin

Use `-` to read from stdin:

```
cat config.yaml | otgctl -m SetConfig -
```

## Methods

Methods can be specified as gRPC names, REST operation IDs (snake\_case), or REST paths. All three forms are equivalent:

| gRPC name | Operation ID | HTTP | REST path |
|-----------|-------------|------|-----------|
| SetConfig | set\_config | POST | /config |
| GetConfig | get\_config | GET | /config |
| UpdateConfig | update\_config | PATCH | /config |
| AppendConfig | append\_config | PATCH | /config/append |
| DeleteConfig | delete\_config | PATCH | /config/delete |
| SetControlState | set\_control_state | POST | /control/state |
| SetControlAction | set\_control_action | POST | /control/action |
| GetMetrics | get\_metrics | POST | /monitor/metrics |
| GetStates | get\_states | POST | /monitor/states |
| GetCapture | get\_capture | POST | /monitor/capture |
| GetVersion | get\_version | GET | /capabilities/version |

You can also specify an explicit verb and path: `-m "POST /config"`.

## Output

JSON responses are printed as YAML by default. Use `-o json` for JSON output.

Non-2xx HTTP responses include the status code in the output. Binary responses (e.g. pcap data from GetCapture) print a warning on a terminal; redirect stdout to capture the data:

```
otgctl -m GetCapture capture_request.yaml > capture.pcap
```

gRPC failures print the gRPC status and server error details to stderr and stop
processing subsequent entries with exit code 1.

## mTLS

For HTTP servers requiring mutual TLS authentication:

```
otgctl --cert client.crt --key client.key -s https://otg-server:8443 config.yaml
```

If the certificate and key are in a single PEM file, `--key` can be omitted:

```
otgctl --cert client.pem -s https://otg-server:8443 config.yaml
```

## Examples

```bash
# Set a configuration from a YAML file
otgctl -s https://otg:8443 -k -m SetConfig topology.yaml

# Replay a recorded RPC log (multi-document YAML with methods embedded)
otgctl -s https://otg:8443 -k rpclog.yaml

# Start traffic flows
otgctl -s https://otg:8443 -m SetControlState //traffic/flow_transmit/state=start

# Get port metrics for specific ports
otgctl -s https://otg:8443 -m GetMetrics //port/port_names=Ethernet1,Ethernet2

# Get flow metrics as JSON
echo '{"choice": "flow"}' | otgctl -s https://otg:8443 -m GetMetrics -o json -
```
