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

METHOD_MAP: dict[str, tuple[str, str]] = {
    "SetConfig":        ("POST",  "/config"),
    "GetConfig":        ("GET",   "/config"),
    "UpdateConfig":     ("PATCH", "/config"),
    "AppendConfig":     ("PATCH", "/config/append"),
    "DeleteConfig":     ("PATCH", "/config/delete"),
    "SetControlState":  ("POST",  "/control/state"),
    "SetControlAction": ("POST",  "/control/action"),
    "GetMetrics":       ("POST",  "/monitor/metrics"),
    "GetStates":        ("POST",  "/monitor/states"),
    "GetCapture":       ("POST",  "/monitor/capture"),
    "GetVersion":       ("GET",   "/capabilities/version"),
}

# REST operationId aliases (snake_case from openapi.yaml)
OPERATION_ID_MAP: dict[str, str] = {
    "set_config":        "SetConfig",
    "get_config":        "GetConfig",
    "update_config":     "UpdateConfig",
    "append_config":     "AppendConfig",
    "delete_config":     "DeleteConfig",
    "set_control_state": "SetControlState",
    "set_control_action":"SetControlAction",
    "get_metrics":       "GetMetrics",
    "get_states":        "GetStates",
    "get_capture":       "GetCapture",
    "get_version":       "GetVersion",
}

# Methods that are snappi-internal and have no REST equivalent
SKIP_METHODS: set[str] = {"API Init"}

PATH_MAP: dict[str, list[tuple[str, str]]] = {}
for _grpc_name, (_http_method, _path) in METHOD_MAP.items():
    PATH_MAP.setdefault(_path, []).append((_http_method, _grpc_name))


def resolve_method(method_str: str) -> tuple[str, str]:
    """Resolve a method string to (http_method, path).

    Accepts:
      - gRPC name: "SetConfig"
      - REST path: "/config"
      - Explicit: "POST /config"
    """
    if " " in method_str:
        parts = method_str.split(None, 1)
        return (parts[0].upper(), parts[1])

    if method_str in METHOD_MAP:
        return METHOD_MAP[method_str]

    if method_str in OPERATION_ID_MAP:
        return METHOD_MAP[OPERATION_ID_MAP[method_str]]

    if method_str.startswith("/"):
        if method_str in PATH_MAP:
            entries = PATH_MAP[method_str]
            if len(entries) == 1:
                return (entries[0][0], method_str)
            # Ambiguous path — multiple methods. Prefer POST > GET > PATCH.
            for prefer in ("POST", "GET", "PATCH", "PUT", "DELETE"):
                for http_method, _ in entries:
                    if http_method == prefer:
                        return (http_method, method_str)
            return (entries[0][0], method_str)
        raise ValueError(f"Unknown REST path: {method_str}")

    raise ValueError(
        f"Unknown method: {method_str}. "
        f"Expected a gRPC method name ({', '.join(METHOD_MAP)}), "
        f"a REST path, or 'VERB /path'."
    )
