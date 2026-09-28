#!/usr/bin/env python3
"""Validate the descriptive capability manifest and its cross-record invariants."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "capabilities" / "modules.yaml"
SCHEMA = ROOT / "capabilities" / "schema.json"


def fail(message: str) -> "NoReturn":
    raise SystemExit(f"capabilities validation failed: {message}")


def main() -> int:
    manifest = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(schema).iter_errors(manifest), key=lambda e: list(e.path))
    if errors:
        fail("; ".join(f"{list(error.path)}: {error.message}" for error in errors))

    modules = manifest["modules"]
    by_id = {module["id"]: module for module in modules}
    if len(by_id) != len(modules):
        fail("module ids must be unique")

    required_app_modules = {
        "portal.app.cloud_iac",
        "portal.app.docs",
        "portal.app.download",
        "portal.app.insight",
        "portal.app.demo",
        "portal.app.ai_aggregator",
    }
    missing = sorted(required_app_modules - by_id.keys())
    if missing:
        fail(f"missing appModules records: {', '.join(missing)}")

    builtin_count = sum(module.get("source") == "builtinExtension" for module in modules)
    if builtin_count != 4:
        fail(f"expected four builtinExtension records, found {builtin_count}")

    for module in modules:
        for dependency in module["depends_on"]:
            if dependency not in by_id:
                fail(f"{module['id']} depends on unknown module {dependency}")
        for route in module["routes"]:
            if route.startswith("/products/") and module["surface"] != "public":
                fail(f"product route {route} must be public")
            if route.startswith("/ai-workspace") and module["surface"] != "app":
                fail(f"AI Workspace route {route} must be app")

    public_product = by_id.get("portal.route.products")
    if not public_product or "/products/*" not in public_product["routes"]:
        fail("/products/* public route surface is missing")
    ai_workspace = by_id.get("portal.route.ai_workspace")
    if not ai_workspace or "/ai-workspace" not in ai_workspace["routes"]:
        fail("/ai-workspace app route surface is missing")

    print(f"capabilities validation passed: v{manifest['version'][1:]} / {len(modules)} records")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
