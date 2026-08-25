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

import io
import os
from unittest import mock

import pytest
import yaml

from otgctl.input import load_inputs, parse_api_path
from tests.constants import FIXTURES, TYPE1_SINGLE_BODY, TYPE2_BODY


class TestApiPath:
    def test_simple(self) -> None:
        result = parse_api_path("/traffic/flow_transmit/state=start")
        assert result == {
            "choice": "traffic",
            "traffic": {
                "choice": "flow_transmit",
                "flow_transmit": {
                    "state": "start",
                },
            },
        }

    def test_single_level(self) -> None:
        result = parse_api_path("/state=start")
        assert result == {"state": "start"}

    def test_two_levels(self) -> None:
        result = parse_api_path("/port/capture/state=started")
        assert result == {
            "choice": "port",
            "port": {
                "choice": "capture",
                "capture": {
                    "state": "started",
                },
            },
        }

    def test_plural_key_single_value_becomes_list(self) -> None:
        result = parse_api_path("/port/port_names=Ethernet1")
        assert result == {
            "choice": "port",
            "port": {
                "port_names": ["Ethernet1"],
            },
        }

    def test_plural_key_multiple_values(self) -> None:
        result = parse_api_path("/port/port_names=Ethernet1,Ethernet2")
        assert result == {
            "choice": "port",
            "port": {
                "port_names": ["Ethernet1", "Ethernet2"],
            },
        }

    def test_multiple_keys_semicolon(self) -> None:
        result = parse_api_path(
            "/port/port_names=Ethernet1,Ethernet2;column_names=transmit,capture")
        assert result == {
            "choice": "port",
            "port": {
                "port_names": ["Ethernet1", "Ethernet2"],
                "column_names": ["transmit", "capture"],
            },
        }

    def test_mixed_scalar_and_list(self) -> None:
        result = parse_api_path("/port/port_names=Ethernet1;state=started")
        assert result == {
            "choice": "port",
            "port": {
                "port_names": ["Ethernet1"],
                "state": "started",
            },
        }

    def test_comma_in_non_plural_key_makes_list(self) -> None:
        result = parse_api_path("/choice=a,b")
        assert result == {"choice": ["a", "b"]}

    def test_path_only_single(self) -> None:
        result = parse_api_path("/flow")
        assert result == {"choice": "flow"}

    def test_path_only_nested(self) -> None:
        result = parse_api_path("/traffic/flow_transmit")
        assert result == {
            "choice": "traffic",
            "traffic": {"choice": "flow_transmit"},
        }

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid API path"):
            parse_api_path("/")

    def test_malformed_leaf_without_key_value_raises(self) -> None:
        with pytest.raises(ValueError, match="key=value"):
            parse_api_path("/traffic/flow_transmit/state=start;badleaf")

    def test_empty_key_raises(self) -> None:
        with pytest.raises(ValueError, match="empty key"):
            parse_api_path("/traffic/=value")

    def test_empty_segment_raises(self) -> None:
        with pytest.raises(ValueError, match="empty segment"):
            parse_api_path("/traffic//state=start")

    def test_duplicate_key_raises(self) -> None:
        with pytest.raises(ValueError, match="duplicate key"):
            parse_api_path("/traffic/state=start;state=stop")


class TestType1Yaml:
    def test_single_doc(self) -> None:
        path = os.path.join(FIXTURES, "type1_single.yaml")
        entries = load_inputs([path], method_override=None)
        assert len(entries) == 1
        method, body = entries[0]
        assert method == "SetConfig"
        assert body == TYPE1_SINGLE_BODY

    def test_multi_doc(self) -> None:
        path = os.path.join(FIXTURES, "type1_multi.yaml")
        entries = load_inputs([path], method_override=None)
        assert len(entries) == 3
        assert entries[0][0] == "SetConfig"
        assert entries[1][0] == "SetControlState"
        assert entries[2][0] == "SetControlState"

    @pytest.mark.parametrize("method", [None, [], {}])
    def test_invalid_embedded_method_raises(self, method: object) -> None:
        yaml_text = yaml.safe_dump({"method": method, "request": {}})
        with mock.patch("sys.stdin", io.StringIO(yaml_text)):
            with pytest.raises(ValueError, match="non-empty string"):
                load_inputs(["-"], method_override=None)


class TestType2Yaml:
    def test_with_method_override(self) -> None:
        path = os.path.join(FIXTURES, "type2.yaml")
        entries = load_inputs([path], method_override="SetConfig")
        assert len(entries) == 1
        method, body = entries[0]
        assert method == "SetConfig"
        assert body == TYPE2_BODY

    def test_without_method_raises(self) -> None:
        path = os.path.join(FIXTURES, "type2.yaml")
        with pytest.raises(ValueError, match="method"):
            load_inputs([path], method_override=None)


class TestJsonFile:
    def test_json_input(self) -> None:
        path = os.path.join(FIXTURES, "type2.json")
        entries = load_inputs([path], method_override="SetConfig")
        assert len(entries) == 1
        method, body = entries[0]
        assert method == "SetConfig"
        assert body == TYPE2_BODY

    def test_json_without_method_raises(self) -> None:
        path = os.path.join(FIXTURES, "type2.json")
        with pytest.raises(ValueError, match="method"):
            load_inputs([path], method_override=None)


class TestApiPathInput:
    def test_api_path_with_method(self) -> None:
        entries = load_inputs(
            ["//traffic/flow_transmit/state=start"],
            method_override="SetControlState",
        )
        assert len(entries) == 1
        method, body = entries[0]
        assert method == "SetControlState"
        assert body["choice"] == "traffic"

    def test_api_path_without_method_raises(self) -> None:
        with pytest.raises(ValueError, match="API path input requires -m"):
            load_inputs(["//traffic/flow_transmit/state=start"], method_override=None)

    def test_path_only_api_path(self) -> None:
        entries = load_inputs(["//flow"], method_override="GetMetrics")
        assert len(entries) == 1
        assert entries[0] == ("GetMetrics", {"choice": "flow"})


class TestStdin:
    def test_stdin_with_dash(self) -> None:
        yaml_text = "ports:\n- name: p1\n  location: Ethernet1\n"
        with mock.patch("sys.stdin", io.StringIO(yaml_text)):
            entries = load_inputs(["-"], method_override="SetConfig")
        assert len(entries) == 1
        assert entries[0][0] == "SetConfig"
        assert entries[0][1]["ports"][0]["name"] == "p1"

    def test_empty_stdin_with_method(self) -> None:
        with mock.patch("sys.stdin", io.StringIO("")):
            entries = load_inputs(["-"], method_override="GetVersion")
        assert len(entries) == 1
        assert entries[0] == ("GetVersion", None)

    def test_empty_stdin_without_method_raises(self) -> None:
        with mock.patch("sys.stdin", io.StringIO("")):
            with pytest.raises(ValueError, match="Input is empty"):
                load_inputs(["-"], method_override=None)


class TestNoSources:
    def test_empty_raises_no_sources(self) -> None:
        with pytest.raises(ValueError, match="No input"):
            load_inputs([], method_override=None)


class TestSkipMethods:
    def test_api_init_skipped(self) -> None:
        path = os.path.join(FIXTURES, "type1_with_skip.yaml")
        entries = load_inputs([path], method_override=None)
        assert len(entries) == 1
        assert entries[0][0] == "set_config"

    def test_all_skipped_yields_empty(self) -> None:
        yaml_text = "method: API Init\nrequest:\n  ext: ixnetwork\n"
        with mock.patch("sys.stdin", io.StringIO(yaml_text)):
            entries = load_inputs(["-"], method_override=None)
        assert len(entries) == 0


class TestAnsibleTags:
    def test_permissive_yaml_loader(self) -> None:
        path = os.path.join(FIXTURES, "type1_ansible_tags.yaml")
        entries = load_inputs([path], method_override=None)
        assert len(entries) == 1
        assert entries[0][0] == "set_config"
        body = entries[0][1]
        assert body["ports"][0]["name"] == "Port 0"

    def test_unknown_scalar_tag(self) -> None:
        yaml_text = "value: !CustomScalar tagged-value\n"
        with mock.patch("sys.stdin", io.StringIO(yaml_text)):
            entries = load_inputs(["-"], method_override="SetConfig")
        assert entries == [("SetConfig", {"value": "tagged-value"})]

    def test_unknown_sequence_tag(self) -> None:
        yaml_text = "values: !CustomSequence\n- one\n- two\n"
        with mock.patch("sys.stdin", io.StringIO(yaml_text)):
            entries = load_inputs(["-"], method_override="SetConfig")
        assert entries == [("SetConfig", {"values": ["one", "two"]})]

    def test_unknown_mapping_tag(self) -> None:
        yaml_text = "value: !CustomMapping\n  key: tagged-value\n"
        with mock.patch("sys.stdin", io.StringIO(yaml_text)):
            entries = load_inputs(["-"], method_override="SetConfig")
        assert entries == [("SetConfig", {"value": {"key": "tagged-value"}})]


class TestMultipleSources:
    def test_file_and_api_path(self) -> None:
        path = os.path.join(FIXTURES, "type1_single.yaml")
        entries = load_inputs(
            [path, "//traffic/flow_transmit/state=start"],
            method_override="SetControlState",
        )
        assert len(entries) == 2
        assert entries[0][0] == "SetConfig"
        assert entries[1][0] == "SetControlState"
