# Copyright 2026 Arista Networks, Inc.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# https://www.apache.org/licenses/LICENSE-2.0

from __future__ import annotations

import io
import json
from unittest import mock

import pytest
import yaml

pytest.importorskip("snappi")
grpc = pytest.importorskip("grpc")
from google.protobuf import json_format
from snappi import otg_pb2 as pb

from otgctl.cli import main
from otgctl.grpc_client import GrpcClient, format_grpc_response, grpc_target


@pytest.fixture
def transport():
    with mock.patch("grpc.insecure_channel") as channel_factory, mock.patch(
        "snappi.otg_pb2_grpc.OpenapiStub"
    ) as stub_factory:
        yield channel_factory, stub_factory.return_value


@pytest.mark.parametrize("method,body,request_field,response_field", [
    ("SetConfig", {"ports": [{"name": "p1", "location": "eth1"}]}, "config", "warning"),
    ("GetConfig", None, None, "config"),
    ("UpdateConfig", {"choice": "flows"}, "config_update", "warning"),
    ("AppendConfig", {}, "config_append", "warning"),
    ("DeleteConfig", {}, "config_delete", "warning"),
    ("SetControlState", {"choice": "traffic"}, "control_state", "warning"),
    ("SetControlAction", {"choice": "port"}, "control_action", "control_action_response"),
    ("GetMetrics", {"choice": "flow"}, "metrics_request", "metrics_response"),
    ("GetStates", {"choice": "ipv4_neighbors"}, "states_request", "states_response"),
    ("GetCapture", {"port_name": "p1"}, "capture_request", "response_bytes"),
    ("GetVersion", None, None, "version"),
])
def test_request_wrapping_and_response_unwrapping(
    transport, method, body, request_field, response_field,
):
    channel_factory, stub = transport
    response = getattr(pb, method + "Response")()
    if method == "GetCapture":
        response.response_bytes = b"\xd4\xc3\xb2\xa1\x00\xff"
    elif method == "GetVersion":
        response.version.app_version = "test"
    elif method == "GetConfig":
        response.config.ports.add(name="p1", location="eth1")
    elif method == "GetMetrics":
        response.metrics_response.flow_metrics.add(name="f1", frames_tx=100, frames_rx=0)
    elif response_field == "warning":
        response.warning.warnings.append("server warning")
    getattr(stub, method).return_value = response

    with GrpcClient("grpc://example.test:40051", timeout=7) as client:
        result = client.execute(method, body)
    rpc = getattr(stub, method)
    rpc.assert_called_once()
    assert rpc.call_args.kwargs == {"timeout": 7}
    request = rpc.call_args.args[0]
    if request_field:
        assert json_format.MessageToDict(request, preserving_proto_field_name=True) == {
            request_field: body,
        }
    else:
        assert request.DESCRIPTOR.full_name == "google.protobuf.Empty"
    if method == "GetCapture":
        assert result == response.response_bytes
    elif method == "GetMetrics":
        assert result == {"flow_metrics": [{"name": "f1", "frames_tx": "100", "frames_rx": "0"}]}
    elif response_field == "warning":
        assert result == {"warnings": ["server warning"]}
    else:
        assert result == json_format.MessageToDict(
            getattr(response, response_field), preserving_proto_field_name=True)
    channel_factory.return_value.close.assert_called_once()
    assert sum(child.call_count for child in stub._mock_children.values()) == 1


@pytest.mark.parametrize("value", [0, 2**53 + 1, 2**64 - 1])
@pytest.mark.parametrize("output_format", ["json", "yaml"])
def test_cli_uint64_counters_preserve_precision(transport, capsys, value, output_format):
    _, stub = transport
    response = pb.GetMetricsResponse()
    response.metrics_response.flow_metrics.add(name="f1", frames_tx=value, frames_rx=0)
    stub.GetMetrics.return_value = pb.GetMetricsResponse.FromString(response.SerializeToString())

    main(["-s", "grpc://example.test:40051", "-m", "GetMetrics", "//flow",
          "-o", output_format])

    output = capsys.readouterr().out
    parsed = json.loads(output) if output_format == "json" else yaml.safe_load(output)
    assert parsed == {"flow_metrics": [{
        "name": "f1", "frames_tx": str(value), "frames_rx": "0",
    }]}


def test_validation_does_not_send_request(transport):
    _, stub = transport
    with GrpcClient("grpc://example.test:40051") as client:
        with pytest.raises(ValueError, match="installed snappi schema"):
            client.execute("SetConfig", {"future_unknown_field": True})
        with pytest.raises(ValueError, match="does not accept a request body"):
            client.execute("GetConfig", {"ports": []})
        with pytest.raises(ValueError, match="must be an object"):
            client.execute("SetConfig", [])
    stub.SetConfig.assert_not_called()
    stub.GetConfig.assert_not_called()


def test_cli_rejects_yaml_field_unknown_to_snappi(transport, tmp_path, capsys):
    channel_factory, stub = transport
    source = tmp_path / "unsupported.yaml"
    source.write_text(
        "method: SetConfig\nrequest:\n"
        "  ports:\n    - name: p1\n      location: eth1\n"
        "  experimental_option: true\n")
    with pytest.raises(SystemExit) as exc:
        main(["-s", "grpc://example.test:40051", str(source)])
    assert exc.value.code == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "Invalid SetConfig request for the installed snappi schema" in output.err
    assert 'no field named "experimental_option"' in output.err
    assert "Traceback" not in output.err
    stub.SetConfig.assert_not_called()
    channel_factory.return_value.close.assert_called_once()


def test_rpc_error_closes_channel_and_exits_nonzero(transport, capsys):
    channel_factory, stub = transport
    class Failure(grpc.RpcError):
        def code(self):
            return grpc.StatusCode.INVALID_ARGUMENT

        def details(self):
            return '{"errors": ["invalid request"]}'

    stub.GetVersion.side_effect = Failure()
    with pytest.raises(SystemExit) as exc:
        main(["-s", "grpc://example.test:40051", "-m", "GetVersion"])
    assert exc.value.code == 1
    stderr = capsys.readouterr().err
    assert 'gRPC INVALID_ARGUMENT: {"errors": ["invalid request"]}' in stderr
    assert "Traceback" not in stderr
    channel_factory.return_value.close.assert_called_once()


@pytest.mark.parametrize("code", [grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED])
def test_transport_failures_keep_grpc_status(transport, code):
    _, stub = transport
    class Failure(grpc.RpcError):
        def code(self):
            return code

        def details(self):
            return "transport failure"

    stub.GetVersion.side_effect = Failure()
    with GrpcClient("grpc://example.test:40051") as client:
        with pytest.raises(RuntimeError, match=code.name):
            client.execute("GetVersion", None)


def test_cli_replays_in_order_on_one_channel(transport, tmp_path, capsys):
    channel_factory, stub = transport
    stub.SetConfig.return_value = pb.SetConfigResponse(warning=pb.Warning())
    stub.GetConfig.return_value = pb.GetConfigResponse(config=pb.Config())
    source = tmp_path / "requests.yaml"
    source.write_text("method: set_config\nrequest: {}\n---\nmethod: GET /config\n")
    main(["-s", "grpc://example.test:40051", str(source)])
    assert [call[0] for call in stub.mock_calls] == ["SetConfig", "GetConfig"]
    channel_factory.assert_called_once()
    assert capsys.readouterr().out == "{}\n{}\n"


def test_cli_stops_replay_after_failure(transport, tmp_path, capsys):
    channel_factory, stub = transport
    stub.SetConfig.side_effect = RuntimeError("request failed")
    source = tmp_path / "requests.yaml"
    source.write_text("method: SetConfig\nrequest: {}\n---\nmethod: GetConfig\n")
    with pytest.raises(SystemExit) as exc:
        main(["-s", "grpc://example.test:40051", str(source)])
    assert exc.value.code == 1
    stub.SetConfig.assert_called_once()
    stub.GetConfig.assert_not_called()
    channel_factory.return_value.close.assert_called_once()
    assert "request failed" in capsys.readouterr().err


def test_cli_shorthand_and_verbose_json(transport, capsys):
    _, stub = transport
    stub.SetControlState.return_value = pb.SetControlStateResponse(warning=pb.Warning())
    main(["-s", "grpc://example.test:40051", "-m", "set_control_state",
          "-o", "json", "-v", "//traffic/flow_transmit/state=start"])
    request = stub.SetControlState.call_args.args[0]
    assert request.control_state.traffic.flow_transmit.state == pb.StateTrafficFlowTransmit.State.Enum.Value("start")
    output = capsys.readouterr()
    assert json.loads(output.out) == {}
    assert "> gRPC SetControlState" in output.err
    assert "< gRPC OK" in output.err
    stub.GetConfig.assert_not_called()


@pytest.mark.parametrize("source", ['{"choice": "flow"}', 'choice: flow\n'])
def test_choice_only_yaml_json_does_not_add_request_fields(transport, source):
    _, stub = transport
    stub.GetMetrics.return_value = pb.GetMetricsResponse()
    with mock.patch("sys.stdin", io.StringIO(source)):
        main(["-s", "grpc://example.test:40051", "-m", "GetMetrics", "-"])
    request = stub.GetMetrics.call_args.args[0].metrics_request
    assert request.HasField("choice")
    assert not request.HasField("flow")


def test_cli_flow_shorthand_includes_empty_message(transport, capsys):
    _, stub = transport
    response = {"choice": "flow_metrics", "flow_metrics": [{"name": "f1", "frames_tx": "0"}]}
    stub.GetMetrics.return_value = json_format.ParseDict(
        {"metrics_response": response}, pb.GetMetricsResponse())
    main(["-s", "grpc://example.test:40051", "-m", "GetMetrics", "//flow", "-o", "json"])
    request = stub.GetMetrics.call_args.args[0]
    assert json_format.MessageToDict(request, preserving_proto_field_name=True) == {
        "metrics_request": {"choice": "flow", "flow": {}},
    }
    assert request.metrics_request.HasField("flow")
    assert json.loads(capsys.readouterr().out) == response


def test_cli_ipv4_neighbors_shorthand(transport, capsys):
    _, stub = transport
    response = {"choice": "ipv4_neighbors", "ipv4_neighbors": [{
        "ethernet_name": "ethernet1", "ipv4_address": "192.0.2.2",
    }]}
    stub.GetStates.return_value = json_format.ParseDict(
        {"states_response": response}, pb.GetStatesResponse())
    main(["-s", "grpc://example.test:40051", "-m", "GetStates",
          "//ipv4_neighbors", "-o", "json"])
    request = stub.GetStates.call_args.args[0]
    assert json_format.MessageToDict(request, preserving_proto_field_name=True) == {
        "states_request": {"choice": "ipv4_neighbors", "ipv4_neighbors": {}},
    }
    assert request.states_request.HasField("ipv4_neighbors")
    assert json.loads(capsys.readouterr().out) == response


def test_cli_textproto(transport, tmp_path):
    _, stub = transport
    stub.SetConfig.return_value = pb.SetConfigResponse()
    source = tmp_path / "config.textproto"
    source.write_text('config { ports { name: "p1" location: "eth1" } }')
    main(["-s", "grpc://example.test:40051", "-m", "SetConfig", str(source)])
    assert stub.SetConfig.call_args.args[0].config.ports[0].location == "eth1"


@pytest.mark.parametrize("content", [b"", b"\xd4\xc3\xb2\xa1\x00\xff"])
def test_cli_capture_keeps_raw_bytes(transport, content):
    _, stub = transport
    stub.GetCapture.return_value = pb.GetCaptureResponse(response_bytes=content)
    stdout = mock.Mock()
    stdout.isatty.return_value = False
    stdout.buffer = io.BytesIO()
    with mock.patch("sys.stdout", stdout):
        main(["-s", "grpc://example.test:40051", "-m", "GetCapture", "//port_name=p1"])
    assert stdout.buffer.getvalue() == content
    assert stdout.write.call_count == 0


def test_binary_terminal_message():
    text, binary = format_grpc_response(b"\x00\xff")
    assert binary == b"\x00\xff"
    assert "gRPC OK" in text
    assert "redirect stdout" in text
    assert "HTTP" not in text


@pytest.mark.parametrize("server,target", [
    ("grpc://example.test:40051", "example.test:40051"),
    ("grpc://example.test:40051/", "example.test:40051"),
    ("grpc://[::1]:40051", "[::1]:40051"),
])
def test_target(server, target):
    assert grpc_target(server) == target


@pytest.mark.parametrize("server", [
    "grpcs://example.test:40051", "grpc://example.test", "grpc://:40051",
    "grpc://example.test:0", "grpc://example.test:65536", "grpc://example.test:abc",
    "grpc://user:pass@example.test:40051", "grpc://example.test:40051/path",
    "grpc://example.test:40051?x=y", "grpc://example.test:40051#fragment",
])
def test_invalid_target(server):
    with pytest.raises(ValueError):
        grpc_target(server)


@pytest.mark.parametrize("options", [
    ["-s", "grpcs://example.test:40051"],
    ["-s", "grpc://example.test:40051", "--cert", "client.pem"],
])
def test_unsupported_tls_options_are_usage_errors(options, transport):
    channel_factory, _ = transport
    with pytest.raises(SystemExit) as exc:
        main(options + ["-m", "GetVersion"])
    assert exc.value.code == 2
    channel_factory.assert_not_called()
