#!/usr/bin/env bash
# Public caller only. Host/service execution belongs to the pinned Playbooks owner.
set -euo pipefail
set +x
command -v python3 >/dev/null 2>&1 || {
  echo 'install-control-plane: python3 is required; provision the reviewed runtime first' >&2
  exit 2
}
python3 - "$@" <<'PY'
import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

GITOPS_URL = "https://github.com/ai-workspace-infra/gitops.git"
PLAYBOOKS_URL = "https://github.com/ai-workspace-infra/playbooks.git"
BILLING_URL = "https://github.com/ai-workspace-services/billing-service.git"
SHA = re.compile(r"[0-9a-fA-F]{40}")


def fail(message):
    raise ValueError(message)


parser = argparse.ArgumentParser(
    prog="install-control-plane.sh",
    description="Delegate self-hosted control-plane deployment to immutable Playbooks.",
    epilog="Requires git, python3, PyYAML and a provisioned Ansible runtime. Set CONTROL_PLANE_CMDB "
    "and CONTROL_PLANE_VARS_FILE to operator-provided files. Apply prepares pinned "
    "controller collections through the fixed Playbooks common owner in a private directory. "
    "No OS or Python packages are installed. The vars file contains "
    "nonsecret runtime policy and Vault references; the owner resolves credentials. No secret arguments. "
    "--check delegates preflight only and does not prepare collections; isolated runtime acceptance is still pending. "
    "Offline tests only: CONTROL_PLANE_OFFLINE_TEST=1 with both GITOPS_CHECKOUT and "
    "PLAYBOOKS_CHECKOUT, plus BILLING_CHECKOUT when release.billing is declared; --check required, "
    "canonical origins (Billing: HTTPS only), clean trees and exact SHAs verified.",
    allow_abbrev=False,
)
parser.add_argument("--config", required=True, help="YAML path relative to the pinned GitOps root")
parser.add_argument("--gitops-ref", required=True, help="full 40-character GitOps commit SHA (no branch/tag)")
parser.add_argument("--check", action="store_true", help="request owner preflight without applying")
args = parser.parse_args()


def git(*arguments):
    result = subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", "-c", "submodule.recurse=false", *map(str, arguments)],
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if result.returncode:
        fail("git operation failed; verify repository access and the requested immutable commit")
    return result.stdout.strip()


def verify_checkout(root, url, sha):
    root = Path(root).resolve(strict=True)
    if Path(git("-C", root, "rev-parse", "--show-toplevel")).resolve() != root:
        fail("checkout must be a repository root")
    origins = (url,) if url == BILLING_URL else (url, url.replace("https://github.com/", "git@github.com:"))
    origin = (git("-C", root, "remote", "get-url", "origin") if url == BILLING_URL
              else git("-C", root, "config", "--get", "remote.origin.url"))
    if origin not in origins:
        fail("checkout origin must match the fixed canonical repository URL")
    if git("-C", root, "rev-parse", "HEAD") != sha:
        fail("checkout HEAD does not match the required full SHA")
    if git("-C", root, "status", "--porcelain", "--untracked-files=all", "--ignored"):
        fail("checkout must be clean, including untracked and ignored files")
    return root


def checkout(destination, url, sha, local):
    if local:
        return verify_checkout(local, url, sha)
    # Fetch only the named object: no default branch checkout or fallback.
    git("init", "--quiet", destination)
    git("-C", destination, "remote", "add", "origin", url)
    git("-C", destination, "fetch", "--quiet", "--no-tags", "--depth=1", "origin", sha)
    git("-C", destination, "checkout", "--quiet", "--detach", sha)
    return verify_checkout(destination, url, sha)


def tracked_file(root, relative):
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts or ".git" in candidate.parts:
        fail("--config must stay inside the GitOps checkout")
    resolved = (root / candidate).resolve(strict=True)
    if root not in resolved.parents or not resolved.is_file():
        fail("--config must resolve to a file inside the GitOps checkout")
    git("-C", root, "ls-files", "--error-unmatch", "--", resolved.relative_to(root))
    return resolved


def main():
    if not SHA.fullmatch(args.gitops_ref):
        fail("--gitops-ref must be a full 40-character commit SHA; branches and tags are rejected")
    if Path(args.config).suffix.lower() not in (".yaml", ".yml"):
        fail("--config must name a GitOps-relative YAML file")
    try:
        import yaml
    except ImportError:
        fail("PyYAML is required by python3; provision the reviewed runtime first (no packages installed)")
    class UniqueSafeLoader(yaml.SafeLoader):
        pass

    def unique_mapping(loader, node):
        result = {}
        for key, value in node.value:
            name = loader.construct_object(key)
            if not isinstance(name, str) or name in result:
                fail("YAML keys must be unique strings")
            result[name] = loader.construct_object(value)
        return result

    UniqueSafeLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)
    if not shutil.which("git"):
        fail("git is required")
    for name in ("CONTROL_PLANE_CMDB", "CONTROL_PLANE_VARS_FILE"):
        if not os.environ.get(name):
            fail(name + " is required (operator-provided file)")
        path = Path(os.environ[name]).resolve(strict=True)
        if not path.is_file() or not os.access(path, os.R_OK):
            fail(name + " must be a readable file")
        os.environ[name] = str(path)
    offline = os.environ.get("CONTROL_PLANE_OFFLINE_TEST", "")
    local_gitops = os.environ.get("GITOPS_CHECKOUT", "")
    local_playbooks = os.environ.get("PLAYBOOKS_CHECKOUT", "")
    local_billing = os.environ.get("BILLING_CHECKOUT", "")
    if offline not in ("", "1"):
        fail("CONTROL_PLANE_OFFLINE_TEST must be 1 or unset")
    if offline or local_gitops or local_playbooks or local_billing:
        if not (offline == "1" and local_gitops and local_playbooks and args.check):
            fail("local checkouts require CONTROL_PLANE_OFFLINE_TEST=1, both checkouts and --check")
    with tempfile.TemporaryDirectory(prefix="control-plane-") as temporary:
        gitops_sha = args.gitops_ref.lower()
        gitops = checkout(Path(temporary) / "gitops", GITOPS_URL, gitops_sha, local_gitops)
        config = tracked_file(gitops, args.config)
        try:
            declaration = yaml.load(config.read_text(encoding="utf-8"), Loader=UniqueSafeLoader)
        except (yaml.YAMLError, UnicodeError):
            fail("--config is not valid safe YAML")
        if isinstance(declaration, dict) and declaration.get("example_only", False) is not False:
            fail("example_only declarations cannot execute; create a reviewed deployment declaration")
        execution = declaration.get("execution") if isinstance(declaration, dict) else None
        playbooks_sha = execution.get("playbooks_sha") if isinstance(execution, dict) else None
        if not isinstance(playbooks_sha, str) or not SHA.fullmatch(playbooks_sha):
            fail("execution.playbooks_sha must be a full 40-character commit SHA")
        release = declaration.get("release", {})
        if not isinstance(release, dict):
            fail("release must be a mapping")
        billing = release.get("billing")
        if "billing" in release:
            if not isinstance(billing, dict) or not isinstance(billing.get("source_sha"), str) or not re.fullmatch(
                r"[0-9a-f]{40}", billing["source_sha"]
            ):
                fail("release.billing.source_sha must be a full lowercase 40-character commit SHA")
            if billing.get("schema_file") != "sql/billing-service-schema.sql":
                fail("release.billing.schema_file must be sql/billing-service-schema.sql")
            if offline and not local_billing:
                fail("BILLING_CHECKOUT is required for offline tests with release.billing")
        elif local_billing:
            fail("BILLING_CHECKOUT requires a matching release.billing declaration")
        playbooks = checkout(Path(temporary) / "playbooks", PLAYBOOKS_URL, playbooks_sha.lower(), local_playbooks)
        runner = tracked_file(playbooks, "scripts/control_plane/entrypoint.py")
        env = {**os.environ, "GITOPS_CHECKOUT": str(gitops), "PLAYBOOKS_CHECKOUT": str(playbooks),
               "PYTHONDONTWRITEBYTECODE": "1"}
        env.pop("BILLING_CHECKOUT", None)
        if billing is not None:
            billing_root = checkout(Path(temporary) / "billing-service", BILLING_URL, billing["source_sha"], local_billing)
            env["BILLING_CHECKOUT"] = str(billing_root)
        if not args.check:
            prepare = tracked_file(playbooks, "roles/vhosts/common/files/prepare_controller.sh")
            env["ANSIBLE_COLLECTIONS_PATH"] = str(Path(temporary) / "controller-collections")
            env["ANSIBLE_COLLECTIONS_SCAN_SYS_PATH"] = "False"
            result = subprocess.run(["bash", str(prepare)], cwd=playbooks, env=env)
            if result.returncode:
                fail("pinned common owner could not prepare controller collections; deployment not started")
        command = ["python3", str(runner), "--config", str(config), "--gitops-ref", gitops_sha]
        if args.check:
            command.append("--check")
        return subprocess.run(command, cwd=playbooks, env=env).returncode


try:
    sys.exit(main())
except (ValueError, OSError):
    error = sys.exc_info()[1]
    # Files may have sensitive names; report filesystem failures without paths.
    message = str(error) if isinstance(error, ValueError) else "required file or command unavailable"
    print("install-control-plane: " + message, file=sys.stderr)
    sys.exit(2)
PY
