#!/usr/bin/env python3
"""BuzzBridge Entity Audit Tool
Rev: 1.0

Reads the HA entity and device registries directly and validates that all
BuzzBridge entities follow the expected naming convention:

  Device:  {prefix} {Thermostat|Base|Remote} {room}
  Entity:  {domain}.{prefix}_{type}_{room}_{measurement}

Reports:
  - Devices with wrong naming pattern
  - Entity IDs that don't match their device name
  - Orphaned entities (no device)
  - Disabled entities
  - Duplicate unique_ids
  - Entity/device count summary

Usage:
    python3 entity_audit.py [--registry-path /homeassistant/.storage]

Runs offline — reads registry JSON files directly, no HA API needed.
"""

import argparse
import json
import sys
from pathlib import Path

# Default HA storage path
DEFAULT_STORAGE = "/homeassistant/.storage"

DOMAIN = "buzzbridge"
DEVICE_TYPES = {"Thermostat", "Base", "Remote"}


def load_json(path: Path) -> dict:
    """Load a JSON file, return empty dict on failure."""
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"  ERROR: Cannot read {path}: {e}", file=sys.stderr)
        return {}


def slugify(text: str) -> str:
    """Simple slugify matching HA's behavior for common cases."""
    import re
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = text.strip("_")
    return text


def audit(storage_path: str) -> int:
    """Run the audit and return exit code (0=pass, 1=issues found)."""
    storage = Path(storage_path)
    issues = 0

    # Load registries
    dev_data = load_json(storage / "core.device_registry")
    ent_data = load_json(storage / "core.entity_registry")

    if not dev_data or not ent_data:
        print("ERROR: Could not load registry files. Check --registry-path.")
        return 2

    devices = dev_data.get("data", {}).get("devices", [])
    entities = ent_data.get("data", {}).get("entities", [])

    # Filter to BuzzBridge
    bb_devices = {}
    for d in devices:
        for dom, ident in d.get("identifiers", []):
            if dom == DOMAIN:
                bb_devices[d["id"]] = d
                break

    bb_entities = [e for e in entities if e.get("platform") == DOMAIN]

    print(f"BuzzBridge Entity Audit")
    print(f"=======================")
    print(f"  Devices: {len(bb_devices)}")
    print(f"  Entities: {len(bb_entities)}")
    print()

    # ------------------------------------------------------------------
    # 1. Device naming audit
    # ------------------------------------------------------------------
    print("--- Device Naming ---")
    for dev_id, dev in bb_devices.items():
        name = dev.get("name", "")
        name_by_user = dev.get("name_by_user")
        model = dev.get("model", "")

        # Extract identifier
        ident = None
        for dom, ident_id in dev.get("identifiers", []):
            if dom == DOMAIN:
                ident = ident_id
                break

        # Check naming pattern: should contain a type keyword
        parts = name.split()
        has_type = any(t in parts for t in DEVICE_TYPES)

        if not has_type:
            print(f"  WARN: Device '{name}' missing type prefix (Thermostat/Base/Remote)")
            print(f"         Identifier: {ident}, Model: {model}")
            issues += 1

        if name_by_user:
            print(f"  NOTE: Device '{name}' has name_by_user override: '{name_by_user}'")

    if issues == 0:
        print("  All devices follow naming convention.")
    print()

    # ------------------------------------------------------------------
    # 2. Entity ID audit
    # ------------------------------------------------------------------
    print("--- Entity ID Audit ---")
    entity_issues = 0
    for ent in bb_entities:
        eid = ent.get("entity_id", "")
        dev_id = ent.get("device_id")
        unique_id = ent.get("unique_id", "")
        original_name = ent.get("original_name", "")
        disabled = ent.get("disabled_by")

        # Check entity belongs to a device
        if not dev_id:
            print(f"  WARN: Entity '{eid}' has no device_id (orphaned)")
            entity_issues += 1
            continue

        dev = bb_devices.get(dev_id)
        if not dev:
            print(f"  WARN: Entity '{eid}' references unknown device '{dev_id}'")
            entity_issues += 1
            continue

        # Check entity ID matches device name
        dev_name = dev.get("name", "")
        expected_slug = slugify(dev_name)
        domain_part, slug_part = eid.split(".", 1)

        if not slug_part.startswith(f"{expected_slug}_"):
            print(f"  MISMATCH: Entity '{eid}'")
            print(f"            Device: '{dev_name}' -> expected prefix: '{expected_slug}_'")
            print(f"            Unique ID: {unique_id}")
            entity_issues += 1

        if disabled:
            print(f"  DISABLED: '{eid}' (disabled_by: {disabled})")

    issues += entity_issues
    if entity_issues == 0:
        print("  All entity IDs match their device names.")
    print()

    # ------------------------------------------------------------------
    # 3. Duplicate unique_id check
    # ------------------------------------------------------------------
    print("--- Duplicate Unique IDs ---")
    uid_map: dict[str, list[str]] = {}
    for ent in bb_entities:
        uid = ent.get("unique_id", "")
        eid = ent.get("entity_id", "")
        uid_map.setdefault(uid, []).append(eid)

    dupes = {uid: eids for uid, eids in uid_map.items() if len(eids) > 1}
    if dupes:
        for uid, eids in dupes.items():
            print(f"  DUPLICATE unique_id '{uid}':")
            for eid in eids:
                print(f"    - {eid}")
            issues += 1
    else:
        print("  No duplicate unique_ids found.")
    print()

    # ------------------------------------------------------------------
    # 4. Summary by device
    # ------------------------------------------------------------------
    print("--- Entities Per Device ---")
    ents_by_dev: dict[str, list[str]] = {}
    for ent in bb_entities:
        dev_id = ent.get("device_id", "none")
        ents_by_dev.setdefault(dev_id, []).append(ent.get("entity_id", "?"))

    for dev_id, eids in sorted(ents_by_dev.items()):
        dev = bb_devices.get(dev_id)
        dev_name = dev.get("name", "unknown") if dev else "(no device)"
        model = dev.get("model", "") if dev else ""
        print(f"  {dev_name} [{model}] — {len(eids)} entities")
        for eid in sorted(eids):
            print(f"    {eid}")
        print()

    # ------------------------------------------------------------------
    # Result
    # ------------------------------------------------------------------
    if issues:
        print(f"RESULT: {issues} issue(s) found.")
        return 1
    else:
        print("RESULT: All checks passed.")
        return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BuzzBridge Entity Audit Tool")
    parser.add_argument(
        "--registry-path",
        default=DEFAULT_STORAGE,
        help=f"Path to HA .storage directory (default: {DEFAULT_STORAGE})",
    )
    args = parser.parse_args()
    sys.exit(audit(args.registry_path))
