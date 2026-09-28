#!/usr/bin/env python3
"""Small contract tests for the capability schema and manifest validator."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = yaml.safe_load((ROOT / "capabilities/modules.yaml").read_text(encoding="utf-8"))
SCHEMA = json.loads((ROOT / "capabilities/schema.json").read_text(encoding="utf-8"))


def test_manifest_is_valid() -> None:
    errors = list(Draft202012Validator(SCHEMA).iter_errors(MANIFEST))
    assert not errors, "valid v1 manifest must satisfy the JSON Schema"


def test_missing_surface_is_rejected() -> None:
    invalid = copy.deepcopy(MANIFEST)
    del invalid["modules"][0]["surface"]
    errors = list(Draft202012Validator(SCHEMA).iter_errors(invalid))
    assert any("surface" in error.message for error in errors), (
        "a module without surface must fail schema validation"
    )


if __name__ == "__main__":
    test_manifest_is_valid()
    test_missing_surface_is_rejected()
    print("capabilities contract tests passed")
