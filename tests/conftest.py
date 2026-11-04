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

import os
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if os.environ.get("OTGCTL_TEST_INSTALLED") == "1":
    import otgctl
    import pytest

    package_path = Path(otgctl.__file__).resolve()
    if (
        not package_path.is_relative_to(Path(sys.prefix).resolve())
        or package_path.is_relative_to(SRC.resolve())
    ):
        raise pytest.UsageError(
            f"Expected otgctl installed in {sys.prefix}, imported {package_path}")
else:
    sys.path.insert(0, str(SRC))
