# Copyright 2026 Arista Networks, Inc.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# https://www.apache.org/licenses/LICENSE-2.0

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import otgctl


def test_http_and_cli_work_without_grpc_dependencies():
    script = '''
import importlib.abc
import io
import sys
from unittest import mock

attempted = []
class BlockOptional(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in {"snappi", "grpc", "google"}:
            attempted.append(fullname)
            raise ModuleNotFoundError("optional dependency blocked: " + fullname)

sys.meta_path.insert(0, BlockOptional())
from otgctl.cli import main
response = mock.Mock(status_code=200, headers={"Content-Type": "application/json"},
                     content=b'{"app_version":"test"}')
with mock.patch("otgctl.client.requests.request", return_value=response) as request:
    main(["-m", "GetVersion"])
    request.assert_called_once()
with mock.patch("sys.stdin", io.StringIO('{"ports": []}')):
    with mock.patch("otgctl.client.requests.request", return_value=response) as request:
        main(["-m", "SetConfig", "-"])
        assert request.call_args.kwargs["json"] == {"ports": []}
with mock.patch("otgctl.client.requests.request", return_value=response) as request:
    main(["-m", "GetStates", "//ipv4_neighbors"])
    assert request.call_args.kwargs["json"] == {"choice": "ipv4_neighbors", "ipv4_neighbors": {}}
for flag in ["--list-methods", "--help", "--version"]:
    try:
        main([flag])
    except SystemExit as exc:
        assert exc.code == 0
assert attempted == []
try:
    main(["-s", "grpc://example.test:40051", "-m", "GetVersion"])
except SystemExit as exc:
    assert exc.code == 1
else:
    raise AssertionError("gRPC must fail when its dependency is unavailable")
assert not any(name.split(".")[0] in {"snappi", "grpc"} for name in sys.modules)
'''
    env = dict(os.environ, PYTHONPATH=str(Path(otgctl.__file__).resolve().parents[1]))
    result = subprocess.run([sys.executable, "-c", script], env=env,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert "app_version: test" in result.stdout
    assert "GetVersion" in result.stdout
    assert "pip install 'otgctl[snappi]'" in result.stderr
    assert "Traceback" not in result.stderr
