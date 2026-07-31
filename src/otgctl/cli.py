# Copyright 2026 Arista Networks, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

import argparse
import importlib.metadata
import os
import sys

import requests

from otgctl.client import execute_request, format_response, print_response
from otgctl.input import load_inputs
from otgctl.methods import METHOD_MAP, resolve_method


def build_parser() -> argparse.ArgumentParser:
    try:
        version = importlib.metadata.version("otgctl")
    except importlib.metadata.PackageNotFoundError:
        version = "dev"
    parser = argparse.ArgumentParser(
        prog="otgctl",
        description=f"otgctl {version} — Make OTG REST API calls from YAML/JSON input.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {version}",
    )
    parser.add_argument(
        "-s", "--server",
        default=os.environ.get("OTG_API", "https://localhost:8443"),
        help="OTG server URL (default: $OTG_API or https://localhost:8443)",
    )
    parser.add_argument(
        "-m", "--method",
        help="gRPC method name or REST path (required when input file does not contain method)",
    )
    parser.add_argument(
        "-o", "--output-format",
        choices=["yaml", "json"],
        default="yaml",
        help="Output format (default: yaml)",
    )
    insecure=os.environ.get("OTG_INSECURE","false").lower()
    parser.add_argument(
        "-k", "--insecure",
        default=insecure not in ('false', 'f', '0'),
        action="store_true",
        help="Skip TLS certificate verification",
    )
    parser.add_argument(
        "--cert",
        help="Client certificate file for mTLS",
    )
    parser.add_argument(
        "--key",
        help="Client private key file for mTLS",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="HTTP request timeout in seconds (default: 30)",
    )
    parser.add_argument(
        "--list-methods",
        action="store_true",
        help="List available gRPC method names for -m and exit",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print request and response details to stderr",
    )
    parser.add_argument(
        "sources",
        nargs="*",
        metavar="FILE_OR_STRING",
        help='YAML/JSON file, "-" for stdin, or //api/path=value',
    )
    return parser


def _request_url(server: str, path: str) -> str:
    return server.rstrip("/") + path


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list_methods:
        for name, (http_method, path) in METHOD_MAP.items():
            print(f"{name:20s} {http_method:5s} {path}")
        sys.exit(0)

    if not args.sources:
        if args.method:
            try:
                http_method, _ = resolve_method(args.method)
            except ValueError as e:
                print(f"Error: {e}", file=sys.stderr)
                sys.exit(1)
            if http_method == "GET":
                args.sources = []
            else:
                parser.error(
                    "No input sources provided. Use a file path, "
                    "'-' for stdin, or a //api/path=value.")
        else:
            parser.error(
                "No input sources provided. Use a file path, "
                "'-' for stdin, or a //api/path=value.")

    try:
        entries = load_inputs(args.sources, args.method)
    except (ValueError, FileNotFoundError, OSError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    for method_str, body in entries:
        try:
            http_method, path = resolve_method(method_str)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

        try:
            cert = None
            if args.cert:
                cert = (args.cert, args.key) if args.key else args.cert
            status, headers, content = execute_request(
                args.server, http_method, path, body,
                insecure=args.insecure, cert=cert,
                verbose=args.verbose, timeout=args.timeout)
        except requests.exceptions.ConnectTimeout:
            print(
                f"Error: connection to {_request_url(args.server, path)} "
                f"timed out after {args.timeout:g}s",
                file=sys.stderr,
            )
            sys.exit(1)
        except requests.exceptions.ReadTimeout:
            print(
                f"Error: server did not respond from "
                f"{_request_url(args.server, path)} within {args.timeout:g}s",
                file=sys.stderr,
            )
            sys.exit(1)
        except requests.exceptions.SSLError as e:
            print(f"Error: TLS failed for {args.server}: {e}", file=sys.stderr)
            sys.exit(1)
        except requests.exceptions.ConnectionError as e:
            print(f"Error: could not connect to {args.server}: {e}", file=sys.stderr)
            sys.exit(1)
        except requests.exceptions.RequestException as e:
            print(f"Error: request failed: {e}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

        text, binary = format_response(
            status, headers, content, args.output_format)
        print_response(text, binary)
        if not 200 <= status < 300:
            sys.exit(1)


if __name__ == "__main__":
    main()
