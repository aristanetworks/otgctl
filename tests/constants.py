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
from typing import Any

FIXTURES: str = os.path.join(os.path.dirname(__file__), "fixtures")

TYPE1_SINGLE_BODY: dict[str, Any] = {
    "ports": [
        {"location": "Ethernet1", "name": "p1"},
        {"location": "Ethernet3", "name": "p2"},
    ],
    "flows": [{
        "name": "f1",
        "tx_rx": {"choice": "port", "port": {"tx_name": "p1", "rx_names": ["p2"]}},
        "size": {"choice": "fixed", "fixed": 128},
        "rate": {"choice": "pps", "pps": "100"},
        "duration": {"choice": "fixed_packets", "fixed_packets": {"packets": 1000}},
    }],
}

TYPE2_BODY: dict[str, Any] = {
    "ports": [
        {"location": "Ethernet1", "name": "p1"},
        {"location": "Ethernet3", "name": "p2"},
    ],
    "flows": [{
        "name": "f1",
        "tx_rx": {"choice": "port", "port": {"tx_name": "p1", "rx_names": ["p2"]}},
    }],
}
