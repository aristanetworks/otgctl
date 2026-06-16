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

import pytest

from otgctl.methods import METHOD_MAP, resolve_method


class TestGrpcToRest:
    @pytest.mark.parametrize("grpc,expected", [
        ("SetConfig", ("POST", "/config")),
        ("GetConfig", ("GET", "/config")),
        ("UpdateConfig", ("PATCH", "/config")),
        ("AppendConfig", ("PATCH", "/config/append")),
        ("DeleteConfig", ("PATCH", "/config/delete")),
        ("SetControlState", ("POST", "/control/state")),
        ("SetControlAction", ("POST", "/control/action")),
        ("GetMetrics", ("POST", "/monitor/metrics")),
        ("GetStates", ("POST", "/monitor/states")),
        ("GetCapture", ("POST", "/monitor/capture")),
        ("GetVersion", ("GET", "/capabilities/version")),
    ])
    def test_grpc_to_rest(self, grpc: str, expected: tuple[str, str]) -> None:
        assert resolve_method(grpc) == expected


class TestRestPathResolve:
    @pytest.mark.parametrize("path,expected_verb", [
        ("/config", "POST"),
        ("/control/state", "POST"),
        ("/capabilities/version", "GET"),
        ("/monitor/capture", "POST"),
    ])
    def test_rest_path_resolve(self, path: str, expected_verb: str) -> None:
        verb, resolved_path = resolve_method(path)
        assert verb == expected_verb
        assert resolved_path == path


class TestVerbPathResolve:
    def test_explicit_verb_path(self) -> None:
        assert resolve_method("POST /config") == ("POST", "/config")

    def test_explicit_verb_unknown_path(self) -> None:
        assert resolve_method("DELETE /custom/endpoint") == ("DELETE", "/custom/endpoint")

    def test_case_insensitive_verb(self) -> None:
        assert resolve_method("get /config") == ("GET", "/config")


class TestOperationIdResolve:
    @pytest.mark.parametrize("op_id,expected", [
        ("set_config", ("POST", "/config")),
        ("get_config", ("GET", "/config")),
        ("set_control_state", ("POST", "/control/state")),
        ("set_control_action", ("POST", "/control/action")),
        ("get_metrics", ("POST", "/monitor/metrics")),
        ("get_states", ("POST", "/monitor/states")),
        ("get_capture", ("POST", "/monitor/capture")),
        ("get_version", ("GET", "/capabilities/version")),
    ])
    def test_operation_id_resolve(self, op_id: str, expected: tuple[str, str]) -> None:
        assert resolve_method(op_id) == expected


class TestUnknownMethod:
    def test_unknown_grpc_name(self) -> None:
        with pytest.raises(ValueError, match="Unknown method"):
            resolve_method("DoSomething")

    def test_unknown_rest_path(self) -> None:
        with pytest.raises(ValueError, match="Unknown REST path"):
            resolve_method("/nonexistent/path")
