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
import os
from unittest import mock

import pytest

import yaml

from otgctl.cli import build_parser, main
from tests.constants import FIXTURES, TYPE1_SINGLE_BODY, TYPE2_BODY


def make_mock_response(
    status: int = 200,
    content_type: str = "application/json",
    body: dict[str, object] | None = None,
) -> mock.MagicMock:
    resp = mock.MagicMock()
    resp.status_code = status
    resp.headers = {"Content-Type": content_type}
    if body is None:
        body = {}
    resp.content = json.dumps(body).encode()
    return resp


class TestBuildParserServer:
    def test_default_server(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            parser = build_parser()
        args = parser.parse_args(["-m", "GetVersion"])
        assert args.server == "https://localhost:8443"

    def test_otg_api_env(self) -> None:
        with mock.patch.dict(os.environ, {"OTG_API": "https://myhost:9443"}):
            parser = build_parser()
        args = parser.parse_args(["-m", "GetVersion"])
        assert args.server == "https://myhost:9443"

    def test_flag_overrides_env(self) -> None:
        with mock.patch.dict(os.environ, {"OTG_API": "https://myhost:9443"}):
            parser = build_parser()
        args = parser.parse_args(["-s", "https://explicit:1234", "-m", "GetVersion"])
        assert args.server == "https://explicit:1234"


class TestBuildParserInsecure:
    def test_default_insecure(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            parser = build_parser()
        args = parser.parse_args(["-m", "GetVersion"])
        assert args.insecure == False

    @pytest.mark.parametrize("val", ["true", "True", "TRUE", "1"])
    def test_otg_insecure_truthy(self, val: str) -> None:
        with mock.patch.dict(os.environ, {"OTG_INSECURE": val}):
            parser = build_parser()
        args = parser.parse_args(["-m", "GetVersion"])
        assert args.insecure == True

    @pytest.mark.parametrize("val", ["false", "False", "FALSE", "f", "F", "0"])
    def test_otg_insecure_falsy(self, val: str) -> None:
        with mock.patch.dict(os.environ, {"OTG_INSECURE": val}):
            parser = build_parser()
        args = parser.parse_args(["-m", "GetVersion"])
        assert args.insecure == False

    def test_flag_sets_insecure(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            parser = build_parser()
        args = parser.parse_args(["-k", "-m", "GetVersion"])
        assert args.insecure == True

    def test_flag_overrides_falsy_env(self) -> None:
        with mock.patch.dict(os.environ, {"OTG_INSECURE": "false"}):
            parser = build_parser()
        args = parser.parse_args(["-k", "-m", "GetVersion"])
        assert args.insecure == True


class TestCliType1:
    @mock.patch("otgctl.client.requests.request")
    def test_single_doc(
        self, mock_request: mock.MagicMock, capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_request.return_value = make_mock_response(
            body={"warning": {}})
        path = os.path.join(FIXTURES, "type1_single.yaml")
        main(["-s", "https://test:8443", "-k", path])
        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[0] == ("POST", "https://test:8443/config")
        assert call_args[1]["json"] == TYPE1_SINGLE_BODY

    @mock.patch("otgctl.client.requests.request")
    def test_multi_doc(
        self, mock_request: mock.MagicMock, capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_request.return_value = make_mock_response(body={"warning": {}})
        path = os.path.join(FIXTURES, "type1_multi.yaml")
        main(["-s", "https://test:8443", "-k", path])
        assert mock_request.call_count == 3


class TestCliType2:
    @mock.patch("otgctl.client.requests.request")
    def test_yaml_with_method(
        self, mock_request: mock.MagicMock, capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_request.return_value = make_mock_response(body={"warning": {}})
        path = os.path.join(FIXTURES, "type2.yaml")
        main(["-s", "https://test:8443", "-m", "SetConfig", path])
        call_args = mock_request.call_args
        assert call_args[0] == ("POST", "https://test:8443/config")

    @mock.patch("otgctl.client.requests.request")
    def test_json_with_method(
        self, mock_request: mock.MagicMock, capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_request.return_value = make_mock_response(body={"warning": {}})
        path = os.path.join(FIXTURES, "type2.json")
        main(["-s", "https://test:8443", "-m", "SetConfig", path])
        call_args = mock_request.call_args
        assert call_args[0] == ("POST", "https://test:8443/config")
        assert call_args[1]["json"] == TYPE2_BODY


class TestCliApiPath:
    @mock.patch("otgctl.client.requests.request")
    def test_api_path(
        self, mock_request: mock.MagicMock, capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_request.return_value = make_mock_response(body={"warning": {}})
        main(["-s", "https://test:8443", "-m", "SetControlState",
              "//traffic/flow_transmit/state=start"])
        call_args = mock_request.call_args
        assert call_args[0] == ("POST", "https://test:8443/control/state")
        assert call_args[1]["json"] == {
            "choice": "traffic",
            "traffic": {
                "choice": "flow_transmit",
                "flow_transmit": {"state": "start"},
            },
        }


class TestCliOutputFormat:
    @mock.patch("otgctl.client.requests.request")
    def test_yaml_output(
        self, mock_request: mock.MagicMock, capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_request.return_value = make_mock_response(
            body={"metrics": [{"name": "f1", "frames_tx": 100}]})
        path = os.path.join(FIXTURES, "type1_single.yaml")
        main(["-s", "https://test:8443", path])
        output = capsys.readouterr().out
        parsed = yaml.safe_load(output)
        assert parsed == {"metrics": [{"name": "f1", "frames_tx": 100}]}

    @mock.patch("otgctl.client.requests.request")
    def test_json_output(
        self, mock_request: mock.MagicMock, capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_request.return_value = make_mock_response(
            body={"metrics": [{"name": "f1"}]})
        path = os.path.join(FIXTURES, "type1_single.yaml")
        main(["-s", "https://test:8443", "-o", "json", path])
        output = capsys.readouterr().out
        parsed = json.loads(output)
        assert parsed == {"metrics": [{"name": "f1"}]}


class TestCliServerDefault:
    @mock.patch("otgctl.client.requests.request")
    def test_otg_api_env(self, mock_request: mock.MagicMock) -> None:
        mock_request.return_value = make_mock_response()
        with mock.patch.dict(os.environ, {"OTG_API": "https://env-server:9443"}):
            main(["-m", "GetVersion"])
        assert mock_request.call_args[0] == ("GET", "https://env-server:9443/capabilities/version")


class TestCliListMethods:
    def test_list_methods(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main(["--list-methods"])
        assert exc_info.value.code == 0
        out = capsys.readouterr().out
        assert "SetConfig" in out
        assert "GetVersion" in out
        assert "/config" in out


class TestCliNoSources:
    @mock.patch("otgctl.client.requests.request")
    def test_get_method_no_sources(
        self, mock_request: mock.MagicMock, capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_request.return_value = make_mock_response(
            body={"api_spec_version": "0.1.0"})
        main(["-s", "https://test:8443", "-m", "GetVersion"])
        call_args = mock_request.call_args
        assert call_args[0] == ("GET", "https://test:8443/capabilities/version")

    def test_post_method_no_sources(self, capsys: pytest.CaptureFixture[str]) -> None:
        try:
            main(["-s", "https://test:8443", "-m", "SetConfig"])
        except SystemExit as e:
            assert e.code == 2
        err = capsys.readouterr().err
        assert "No input sources" in err


class TestCliErrors:
    def test_no_sources(self, capsys: pytest.CaptureFixture[str]) -> None:
        try:
            main([])
        except SystemExit as e:
            assert e.code == 2
        err = capsys.readouterr().err
        assert "No input sources" in err

    def test_type2_no_method(self, capsys: pytest.CaptureFixture[str]) -> None:
        path = os.path.join(FIXTURES, "type2.yaml")
        try:
            main(["-s", "https://test:8443", path])
        except SystemExit as e:
            assert e.code == 1
        err = capsys.readouterr().err
        assert "method" in err.lower()

    @mock.patch("otgctl.client.requests.request")
    def test_unknown_method(
        self, mock_request: mock.MagicMock, capsys: pytest.CaptureFixture[str],
    ) -> None:
        path = os.path.join(FIXTURES, "type2.yaml")
        try:
            main(["-s", "https://test:8443", "-m", "DoSomething", path])
        except SystemExit as e:
            assert e.code == 1
        err = capsys.readouterr().err
        assert "Unknown method" in err
        assert "DoSomething" in err
