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
import json
from unittest import mock

import pytest
import requests
import yaml

from otgctl.client import execute_request, format_response, print_response


class TestFormatResponse:
    def test_success_json_as_yaml(self) -> None:
        data = {"warning": {"warnings": ["test warning"]}}
        headers = {"Content-Type": "application/json"}
        content = json.dumps(data).encode()
        text, binary = format_response(200, headers, content, "yaml")
        assert binary is None
        parsed = yaml.safe_load(text)
        assert parsed == data

    def test_success_json_as_json(self) -> None:
        data = {"status": "ok"}
        headers = {"Content-Type": "application/json"}
        content = json.dumps(data).encode()
        text, binary = format_response(200, headers, content, "json")
        assert binary is None
        parsed = json.loads(text)
        assert parsed == data

    def test_error_response_includes_status(self) -> None:
        headers = {"Content-Type": "application/json"}
        data = {"detail": "not found"}
        content = json.dumps(data).encode()
        text, binary = format_response(404, headers, content, "yaml")
        assert "HTTP 404" in text
        assert "not found" in text

    def test_binary_response(self) -> None:
        headers = {"Content-Type": "application/octet-stream"}
        content = b"\x00\x01\x02\x03"
        text, binary = format_response(200, headers, content, "yaml")
        assert binary == content
        assert "Binary response" in text
        assert "redirect" in text

    def test_empty_success(self) -> None:
        headers = {"Content-Type": "application/json"}
        text, binary = format_response(200, headers, b"", "yaml")
        assert binary is None

    def test_text_content_type(self) -> None:
        headers = {"Content-Type": "text/plain"}
        content = b"some plain text"
        text, binary = format_response(200, headers, content, "yaml")
        assert text == "some plain text"
        assert binary is None

    def test_invalid_json_falls_back_to_text(self) -> None:
        headers = {"Content-Type": "application/json"}
        text, binary = format_response(
            200, headers, b"{not valid json", "yaml")
        assert text == "{not valid json"
        assert binary is None


class TestPrintResponse:
    def test_text_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        print_response("hello", None)
        assert capsys.readouterr().out == "hello\n"

    def test_binary_on_tty(self, capsys: pytest.CaptureFixture[str]) -> None:
        with mock.patch("sys.stdout") as mock_stdout:
            mock_stdout.isatty.return_value = True
            mock_stdout.write = lambda s: None
            print_response("Binary warning", b"\x00\x01")
        # Should not crash; prints warning text on tty

    def test_binary_to_pipe(self) -> None:
        buf = io.BytesIO()
        mock_stdout = mock.MagicMock()
        mock_stdout.isatty.return_value = False
        mock_stdout.buffer = buf
        with mock.patch("sys.stdout", mock_stdout):
            print_response("Binary warning", b"\x00\x01")
        assert buf.getvalue() == b"\x00\x01"

    def test_binary_to_file(self) -> None:
        buf = io.BytesIO()
        print_response("Binary warning", b"\x00\x01", file=buf)
        assert buf.getvalue() == b"\x00\x01"


class TestExecuteRequest:
    @mock.patch("otgctl.client.requests.request")
    def test_post_with_body(self, mock_request: mock.MagicMock) -> None:
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Type": "application/json"}
        mock_resp.content = b'{"status": "ok"}'
        mock_request.return_value = mock_resp

        status, headers, content = execute_request(
            "https://localhost:8443", "POST", "/config",
            {"ports": []}, insecure=True,
        )
        assert status == 200
        mock_request.assert_called_once_with(
            "POST", "https://localhost:8443/config",
            timeout=30.0, verify=False, json={"ports": []},
        )

    @mock.patch("otgctl.client.requests.request")
    def test_get_no_body(self, mock_request: mock.MagicMock) -> None:
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Type": "application/json"}
        mock_resp.content = b'{}'
        mock_request.return_value = mock_resp

        execute_request(
            "https://localhost:8443", "GET", "/config",
            None, insecure=False,
        )
        mock_request.assert_called_once_with(
            "GET", "https://localhost:8443/config", timeout=30.0,
        )

    @mock.patch("otgctl.client.requests.request")
    def test_mtls_cert_and_key(self, mock_request: mock.MagicMock) -> None:
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Type": "application/json"}
        mock_resp.content = b'{}'
        mock_request.return_value = mock_resp

        execute_request(
            "https://localhost:8443", "POST", "/config",
            {"ports": []}, cert=("client.crt", "client.key"),
        )
        mock_request.assert_called_once_with(
            "POST", "https://localhost:8443/config",
            timeout=30.0, cert=("client.crt", "client.key"), json={"ports": []},
        )

    @mock.patch("otgctl.client.requests.request")
    def test_custom_timeout(self, mock_request: mock.MagicMock) -> None:
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Type": "application/json"}
        mock_resp.content = b'{}'
        mock_request.return_value = mock_resp

        execute_request(
            "https://localhost:8443", "GET", "/config",
            None, timeout=5.0,
        )
        mock_request.assert_called_once_with(
            "GET", "https://localhost:8443/config", timeout=5.0,
        )

    @mock.patch("otgctl.client.requests.request")
    def test_request_timeout_propagates(
        self, mock_request: mock.MagicMock,
    ) -> None:
        mock_request.side_effect = requests.exceptions.Timeout("timed out")

        with pytest.raises(requests.exceptions.Timeout, match="timed out"):
            execute_request("https://localhost:8443", "GET", "/config", None)

    @mock.patch("otgctl.client.requests.request")
    def test_verbose_prints_request_and_response(
        self, mock_request: mock.MagicMock, capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Type": "application/json"}
        mock_resp.content = b'{"status": "ok"}'
        mock_request.return_value = mock_resp

        execute_request(
            "https://localhost:8443", "POST", "/config",
            {"ports": []}, verbose=True,
        )
        err = capsys.readouterr().err
        assert "> POST https://localhost:8443/config" in err
        assert '"ports"' in err
        assert "< HTTP 200" in err
        assert "< Content-Type: application/json" in err
        assert '{"status": "ok"}' in err

    @mock.patch("otgctl.client.requests.request")
    def test_verbose_no_body(
        self, mock_request: mock.MagicMock, capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Type": "application/json"}
        mock_resp.content = b'{}'
        mock_request.return_value = mock_resp

        execute_request(
            "https://localhost:8443", "GET", "/config",
            None, verbose=True,
        )
        err = capsys.readouterr().err
        assert "> GET https://localhost:8443/config" in err
        assert "< HTTP 200" in err

    @mock.patch("otgctl.client.requests.request")
    def test_verbose_binary_response(
        self, mock_request: mock.MagicMock, capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Type": "application/octet-stream"}
        mock_resp.content = b'\x00\x01\x02'
        mock_request.return_value = mock_resp

        execute_request(
            "https://localhost:8443", "POST", "/monitor/capture",
            {}, verbose=True,
        )
        err = capsys.readouterr().err
        assert "3 bytes binary" in err

    @mock.patch("otgctl.client.requests.request")
    def test_mtls_cert_only(self, mock_request: mock.MagicMock) -> None:
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Type": "application/json"}
        mock_resp.content = b'{}'
        mock_request.return_value = mock_resp

        execute_request(
            "https://localhost:8443", "POST", "/config",
            None, cert="combined.pem",
        )
        mock_request.assert_called_once_with(
            "POST", "https://localhost:8443/config",
            timeout=30.0, cert="combined.pem",
        )
