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
from typing import Any
from urllib.parse import urlsplit

import yaml


def grpc_target(server: str) -> str:
    """Validate a plaintext gRPC URL and return its host:port target."""
    url = urlsplit(server)
    if url.scheme != "grpc":
        raise ValueError("Only plaintext grpc:// URLs are supported for gRPC")
    if (
        not url.hostname or url.port is None or url.port == 0
        or url.username is not None or url.password is not None
        or url.path not in ("", "/") or url.query or url.fragment
    ):
        raise ValueError("gRPC server must be a grpc://host:port URL")
    return url.netloc


class GrpcClient:
    """A channel shared by sequential, individual unary RPCs."""

    def __init__(
        self, server: str, timeout: float = 30.0, verbose: bool = False,
    ) -> None:
        target = grpc_target(server)
        try:
            import grpc
            from google.protobuf import json_format
            from google.protobuf.empty_pb2 import Empty
            from snappi import otg_pb2, otg_pb2_grpc
        except ImportError as e:
            raise ValueError(
                "gRPC requires the optional 'snappi' dependency. "
                "Install it with: pip install 'otgctl[snappi]'.") from e

        self._grpc = grpc
        self._json_format = json_format
        self._empty = Empty
        self._pb = otg_pb2
        self._server = server
        self._timeout = timeout
        self._verbose = verbose
        self._channel = grpc.insecure_channel(target, options=[
            ("grpc.max_receive_message_length", 64 * 1024 * 1024),
            ("grpc.enable_retries", 0),
        ])
        try:
            self._stub = otg_pb2_grpc.OpenapiStub(self._channel)
        except Exception:
            self._channel.close()
            raise

    def __enter__(self) -> GrpcClient:
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self._channel.close()

    def execute(self, method: str, body: dict[str, Any] | None) -> dict[str, Any] | bytes:
        """Wrap the input, execute one RPC, and extract its response body."""
        if body is not None and not isinstance(body, dict):
            raise ValueError(f"{method} request must be an object")
        rpc = getattr(self._stub, method, None)
        request_type = getattr(self._pb, f"{method}Request", None)
        if method in ("GetConfig", "GetVersion"):
            if body:
                raise ValueError(f"{method} does not accept a request body")
            request = self._empty()
        elif request_type is None or rpc is None:
            raise ValueError(
                f"Installed snappi does not support {method}; upgrade snappi.")
        else:
            request = request_type()
            fields = request.DESCRIPTOR.fields
            if len(fields) != 1:
                raise ValueError(f"Unsupported snappi request schema for {method}")
            try:
                self._json_format.ParseDict({fields[0].name: body or {}}, request)
            except self._json_format.ParseError as e:
                raise ValueError(
                    f"Invalid {method} request for the installed snappi schema: {e}") from e

        if rpc is None:
            raise ValueError(
                f"Installed snappi does not support {method}; upgrade snappi.")
        if self._verbose:
            print(f"> gRPC {method} {self._server}", file=sys.stderr)
            data = self._json_format.MessageToDict(
                request, preserving_proto_field_name=True)
            print(f"> {json.dumps(data, indent=2)}", file=sys.stderr)
        try:
            response = rpc(request, timeout=self._timeout)
        except self._grpc.RpcError as e:
            raise RuntimeError(f"gRPC {e.code().name}: {e.details()}") from e

        fields = response.DESCRIPTOR.fields
        if len(fields) != 1:
            raise ValueError(f"Unsupported snappi response schema for {method}")
        if method == "GetCapture":
            result = response.response_bytes
        else:
            result = self._json_format.MessageToDict(
                getattr(response, fields[0].name), preserving_proto_field_name=True)
        if self._verbose:
            print("< gRPC OK", file=sys.stderr)
            if isinstance(result, bytes):
                print(f"< ({len(result)} bytes binary)", file=sys.stderr)
            else:
                print(f"< {json.dumps(result, indent=2)}", file=sys.stderr)
        return result


def format_grpc_response(
    response: dict[str, Any] | bytes, output_format: str = "yaml",
) -> tuple[str, bytes | None]:
    if isinstance(response, bytes):
        return (
            f"gRPC OK\nContent-Length: {len(response)}\n"
            "Binary response; redirect stdout to save (e.g. otgctl ... > file.pcap)",
            response,
        )
    if output_format == "json":
        return json.dumps(response, indent=2), None
    return yaml.dump(response, default_flow_style=False).rstrip(), None
