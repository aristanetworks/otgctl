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

import json
import sys
from collections.abc import Mapping
from typing import IO, Any

import requests
import urllib3
import yaml


def _debug_print(msg: str) -> None:
    print(msg, file=sys.stderr)


def execute_request(
    server: str,
    http_method: str,
    path: str,
    body: dict[str, Any] | None,
    insecure: bool = False,
    cert: str | tuple[str, str] | None = None,
    verbose: bool = False,
    timeout: float = 30.0,
) -> tuple[int, Mapping[str, str], bytes]:
    """Make an HTTP request and return (status_code, headers, content_bytes)."""
    url = server.rstrip("/") + path

    kwargs = {}
    if insecure:
        kwargs["verify"] = False
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    if cert is not None:
        kwargs["cert"] = cert

    if body is not None:
        kwargs["json"] = body

    if verbose:
        _debug_print(f"> {http_method} {url}")
        if body is not None:
            _debug_print(f"> {json.dumps(body, indent=2)}")

    resp = requests.request(http_method, url, timeout=timeout, **kwargs)

    if verbose:
        _debug_print(f"< HTTP {resp.status_code}")
        for k, v in resp.headers.items():
            _debug_print(f"< {k}: {v}")
        content_type = resp.headers.get("Content-Type", "")
        is_text = "json" in content_type or "text/" in content_type
        if is_text and resp.content:
            _debug_print(f"< {resp.content.decode('utf-8', errors='replace')}")
        elif resp.content:
            _debug_print(f"< ({len(resp.content)} bytes binary)")

    return (resp.status_code, resp.headers, resp.content)


def format_response(
    status_code: int,
    headers: Mapping[str, str],
    content: bytes,
    output_format: str = "yaml",
) -> tuple[str, bytes | None]:
    """Format an HTTP response for display.

    Returns (text_to_print, binary_bytes_or_None).
    If the response is binary, text_to_print is a warning message and
    binary_bytes_or_None contains the raw bytes (caller decides whether
    to write them based on whether stdout is a tty).
    """
    content_type = headers.get("Content-Type", "")
    media_type = content_type.split(";", 1)[0].strip().lower()

    is_json = (
        media_type in ("application/json", "text/json")
        or media_type.endswith("+json")
    )
    is_text = is_json or media_type.startswith("text/")
    is_ok = 200 <= status_code < 300

    if not is_text and content:
        msg = f"HTTP {status_code}\n"
        msg += f"Content-Type: {content_type}\n"
        msg += f"Content-Length: {len(content)}\n"
        msg += "Binary response; redirect stdout to save (e.g. otgctl ... > file.pcap)"
        return (msg, content)

    lines = []
    if not is_ok:
        lines.append(f"HTTP {status_code}")

    if is_json and content:
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            lines.append(content.decode("utf-8", errors="replace"))
        else:
            if output_format == "json":
                lines.append(json.dumps(data, indent=2))
            else:
                lines.append(yaml.dump(data, default_flow_style=False).rstrip())
    elif content:
        lines.append(content.decode("utf-8", errors="replace"))

    return ("\n".join(lines), None)


def print_response(text: str, binary: bytes | None, file: IO[bytes] | None = None) -> None:
    """Print or write the response.

    If binary is not None and stdout is not a tty (or file is given),
    write the binary data. Otherwise print the text message.
    """
    if binary is not None:
        if file is not None:
            file.write(binary)
        elif not sys.stdout.isatty():
            sys.stdout.buffer.write(binary)
        else:
            print(text)
    else:
        if text:
            print(text)
