#!/usr/bin/env python3
"""List all BuzzBridge entity IDs from the HA entity registry."""
import json

with open("/homeassistant/.storage/core.entity_registry") as f:
    reg = json.load(f)

for e in sorted(reg["data"]["entities"], key=lambda x: x.get("entity_id", "")):
    if e.get("platform") == "buzzbridge":
        print(e["entity_id"])
