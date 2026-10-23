#!/usr/bin/env python3
"""Offline contract tests: fixture commits, mocked transport, recording owner runner."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

WRAPPER = Path(__file__).with_name("install-control-plane.sh").resolve()
REAL_GIT = shutil.which("git")
GITOPS_URL = "https://github.com/ai-workspace-infra/gitops.git"
PLAYBOOKS_URL = "https://github.com/ai-workspace-infra/playbooks.git"

RUNNER = '''import json, os, sys
from pathlib import Path
Path(os.environ["OWNER_RECORD"]).write_text(json.dumps({
    "args": sys.argv[1:], "cwd": os.getcwd(),
    "gitops": os.environ["GITOPS_CHECKOUT"],
    "playbooks": os.environ["PLAYBOOKS_CHECKOUT"],
    "cmdb": os.environ["CONTROL_PLANE_CMDB"],
    "vars": os.environ["CONTROL_PLANE_VARS_FILE"],
}))
sys.exit(int(os.environ.get("OWNER_EXIT", "0")))
'''

TRANSPORT = '''#!/usr/bin/env python3
import json, os, subprocess, sys
from pathlib import Path
args = sys.argv[1:]
with open(os.environ["GIT_RECORD"], "a") as log:
    log.write(json.dumps(args) + "\\n")
if "fetch" in args:
    sha = args[-1]
    source = {os.environ["GITOPS_SHA"]: os.environ["FIXTURE_GITOPS"],
              os.environ["PLAYBOOKS_SHA"]: os.environ["FIXTURE_PLAYBOOKS"]}.get(sha)
    if not source or os.environ.get("FETCH_FAIL"):
        sys.exit(1)
    # Map the exact requested object to a local fixture, never contact a remote.
    args[-2] = source
sys.exit(subprocess.run([os.environ["REAL_GIT"], *args]).returncode)
'''


class WrapperTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="wrapper-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.playbooks = self.root / "playbooks fixture"
        self.gitops = self.root / "gitops fixture"
        self.runner = self.playbooks / "scripts/control_plane/entrypoint.py"
        self.runner.parent.mkdir(parents=True)
        self.runner.write_text(RUNNER)
        self.playbooks_sha = self.init_repo(self.playbooks, PLAYBOOKS_URL)
        self.config = self.gitops / "resources/test/candidate.yaml"
        self.config.parent.mkdir(parents=True)
        self.config.write_text(self.declaration())
        self.gitops_sha = self.init_repo(self.gitops, GITOPS_URL)
        self.git(self.gitops, "tag", "fixture-release")
        self.bin = self.root / "bin"
        self.bin.mkdir()
        (self.bin / "git").write_text(TRANSPORT)
        (self.bin / "git").chmod(0o755)
        for name in ("cmdb.json", "protected vars.yaml"):
            (self.root / name).write_text("{}\n")
        self.env = {**os.environ, "PATH": str(self.bin) + os.pathsep + os.environ["PATH"],
                    "REAL_GIT": REAL_GIT, "OWNER_RECORD": str(self.root / "owner.json"),
                    "GIT_RECORD": str(self.root / "git.jsonl"),
                    "GITOPS_SHA": self.gitops_sha, "PLAYBOOKS_SHA": self.playbooks_sha,
                    "FIXTURE_GITOPS": str(self.gitops), "FIXTURE_PLAYBOOKS": str(self.playbooks),
                    "CONTROL_PLANE_CMDB": "cmdb.json", "CONTROL_PLANE_VARS_FILE": "protected vars.yaml"}
        for name in ("GITOPS_CHECKOUT", "PLAYBOOKS_CHECKOUT", "CONTROL_PLANE_OFFLINE_TEST"):
            self.env.pop(name, None)

    def git(self, root, *args):
        return subprocess.check_output([REAL_GIT, "-C", str(root), *args], text=True).strip()

    def declaration(self):
        return "execution:\n  playbooks_sha: '" + self.playbooks_sha + "'\nrelease:\n  snapshot_tag: fixture-release\n"

    def commit(self, root):
        self.git(root, "add", ".")
        self.git(root, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.com",
                 "commit", "-qm", "offline fixture")
        return self.git(root, "rev-parse", "HEAD")

    def init_repo(self, root, origin):
        self.git(root, "init", "-q")
        self.git(root, "remote", "add", "origin", origin)
        return self.commit(root)

    def run_wrapper(self, args=None, offline=False, **env):
        runtime = {**self.env, **env}
        if offline:
            runtime.update(CONTROL_PLANE_OFFLINE_TEST="1", GITOPS_CHECKOUT=str(self.gitops),
                           PLAYBOOKS_CHECKOUT=str(self.playbooks))
        if args is None:
            args = ["--config", "resources/test/candidate.yaml", "--gitops-ref", self.gitops_sha, "--check"]
        return subprocess.run(["/bin/bash", str(WRAPPER), *args], cwd=self.root, env=runtime,
                              text=True, capture_output=True)

    def assert_rejected(self, result, message):
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(message, result.stderr)
        self.assertFalse((self.root / "owner.json").exists())

    def test_fetches_only_fixed_shas_and_delegates_exact_contract(self):
        result = self.run_wrapper()
        self.assertEqual(result.returncode, 0, result.stderr)
        record = json.loads((self.root / "owner.json").read_text())
        self.assertEqual(record["args"], ["--config", record["gitops"] + "/resources/test/candidate.yaml",
                                          "--gitops-ref", self.gitops_sha, "--check"])
        self.assertEqual(record["cwd"], record["playbooks"])
        self.assertEqual(record["cmdb"], str(self.root / "cmdb.json"))
        self.assertEqual(record["vars"], str(self.root / "protected vars.yaml"))
        calls = [json.loads(line) for line in (self.root / "git.jsonl").read_text().splitlines()]
        self.assertEqual([call[-1] for call in calls if "fetch" in call], [self.gitops_sha, self.playbooks_sha])
        self.assertEqual([call[-1] for call in calls if "remote" in call and "add" in call],
                         [GITOPS_URL, PLAYBOOKS_URL])
        self.assertTrue(all("main" not in call and "latest" not in call for call in calls))
        self.assertFalse(Path(record["gitops"]).exists(), "temporary clone must be cleaned")

    def test_apply_delegation_and_owner_failure_propagate(self):
        result = self.run_wrapper(["--config", "resources/test/candidate.yaml", "--gitops-ref", self.gitops_sha],
                                  OWNER_EXIT="17")
        self.assertEqual(result.returncode, 17, result.stderr)
        self.assertNotIn("--check", json.loads((self.root / "owner.json").read_text())["args"])

    def test_offline_clean_fixed_checkouts(self):
        result = self.run_wrapper(offline=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('"fetch"', (self.root / "git.jsonl").read_text())

    def test_offline_accepts_only_canonical_ssh_alias(self):
        for root, url in ((self.gitops, GITOPS_URL), (self.playbooks, PLAYBOOKS_URL)):
            self.git(root, "remote", "set-url", "origin", url.replace("https://github.com/", "git@github.com:"))
        result = self.run_wrapper(offline=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_ref_and_parameter_rejection(self):
        for ref in ("main", "v1.2.3", "a" * 39, "g" * 40, "$(touch injected)"):
            with self.subTest(ref=ref):
                self.assert_rejected(self.run_wrapper(["--config", "test.yaml", "--gitops-ref", ref]), "full 40")
        self.assert_rejected(self.run_wrapper(["--token", "never-a-real-token"]), "required")
        self.assertFalse((self.root / "injected").exists())

    def test_help_needs_no_runtime_inputs(self):
        result = self.run_wrapper(["--help"], CONTROL_PLANE_CMDB="", CONTROL_PLANE_VARS_FILE="")
        self.assertEqual(result.returncode, 0)
        self.assertIn("CONTROL_PLANE_CMDB", result.stdout)

    def test_shell_syntax(self):
        subprocess.run(["/bin/bash", "-n", str(WRAPPER)], check=True)

    def test_gitops_does_not_need_a_service_snapshot_tag(self):
        self.git(self.gitops, "tag", "-d", "fixture-release")
        result = self.run_wrapper(offline=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_operator_files(self):
        for name in ("CONTROL_PLANE_CMDB", "CONTROL_PLANE_VARS_FILE"):
            with self.subTest(name=name):
                self.assert_rejected(self.run_wrapper(**{name: ""}), name + " is required")

    def test_missing_python_and_yaml_fail_without_installing(self):
        runtime = self.root / "runtime"
        runtime.mkdir()
        env = {**self.env, "PATH": str(runtime)}
        result = subprocess.run(["/bin/bash", str(WRAPPER), "--help"], env=env, text=True, capture_output=True)
        self.assert_rejected(result, "python3 is required")
        (runtime / "python3").write_text('#!/bin/sh\nexec "' + shutil.which("python3") + '" -S "$@"\n')
        (runtime / "python3").chmod(0o755)
        self.assert_rejected(self.run_wrapper(PATH=str(runtime)), "PyYAML is required")

    def test_local_override_requires_explicit_offline_check_mode(self):
        self.assert_rejected(self.run_wrapper(GITOPS_CHECKOUT=str(self.gitops)), "local checkouts require")
        self.assert_rejected(self.run_wrapper(["--config", "resources/test/candidate.yaml", "--gitops-ref", self.gitops_sha],
                                              offline=True), "local checkouts require")

    def test_dirty_untracked_and_ignored_checkouts_rejected(self):
        for root in (self.gitops, self.playbooks):
            with self.subTest(root=root):
                extra = root / "untracked"
                extra.write_text("fixture")
                self.assert_rejected(self.run_wrapper(offline=True), "must be clean")
                extra.unlink()
        self.runner.write_text(RUNNER + "# changed\n")
        self.assert_rejected(self.run_wrapper(offline=True), "must be clean")
        self.runner.write_text(RUNNER)
        (self.playbooks / ".git/info/exclude").write_text("ignored\n")
        (self.playbooks / "ignored").write_text("fixture")
        self.assert_rejected(self.run_wrapper(offline=True), "must be clean")

    def test_wrong_origin_and_head_rejected(self):
        self.git(self.gitops, "remote", "set-url", "origin", "https://example.com/wrong.git")
        self.assert_rejected(self.run_wrapper(offline=True), "canonical repository")
        self.git(self.gitops, "remote", "set-url", "origin", GITOPS_URL)
        self.assert_rejected(self.run_wrapper(["--config", "resources/test/candidate.yaml", "--gitops-ref", "a" * 40,
                                              "--check"], offline=True), "HEAD does not match")

    def test_fetch_failure_has_no_branch_fallback(self):
        self.assert_rejected(self.run_wrapper(FETCH_FAIL="1"), "git operation failed")
        calls = (self.root / "git.jsonl").read_text()
        self.assertEqual(calls.count('"fetch"'), 1)
        self.assertNotIn('"main"', calls)

    def test_invalid_yaml_and_playbooks_pin(self):
        for declaration in ("execution: [", "[]", "execution: {}", "execution:\n  playbooks_sha: main\n",
                            "!!python/object/apply:os.system ['touch injected']"):
            with self.subTest(declaration=declaration):
                self.config.write_text(declaration)
                self.gitops_sha = self.commit(self.gitops)
                self.assert_rejected(self.run_wrapper(offline=True), "YAML" if declaration.startswith("!!")
                                     or declaration == "execution: [" else "playbooks_sha")
        self.assertFalse((self.root / "injected").exists())

    def test_examples_and_duplicate_keys_fail_before_owner_fetch(self):
        for extra in ("example_only: true\n", "example_only: false\nexample_only: true\n"):
            with self.subTest(extra=extra):
                self.config.write_text(self.declaration() + extra)
                self.gitops_sha = self.commit(self.gitops)
                self.assert_rejected(self.run_wrapper(offline=True),
                                     "example_only" if extra.count("example_only") == 1 else "unique strings")
        calls = (self.root / "git.jsonl").read_text()
        self.assertNotIn(str(self.playbooks), calls)

    def test_path_escape_and_missing_runner(self):
        for path in ("/tmp/test.yaml", "../test.yaml", ".git/test.yaml", "missing.yaml", "test.json"):
            with self.subTest(path=path):
                result = self.run_wrapper(["--config", path, "--gitops-ref", self.gitops_sha, "--check"], offline=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((self.root / "owner.json").exists())
        outside = self.root / "outside.yaml"
        outside.write_text(self.config.read_text())
        (self.gitops / "escape.yaml").symlink_to(outside)
        self.gitops_sha = self.commit(self.gitops)
        self.assert_rejected(self.run_wrapper(["--config", "escape.yaml", "--gitops-ref", self.gitops_sha, "--check"],
                                              offline=True), "inside the GitOps")
        self.runner.unlink()
        self.playbooks_sha = self.commit(self.playbooks)
        self.config.write_text(self.declaration())
        self.gitops_sha = self.commit(self.gitops)
        self.assert_rejected(self.run_wrapper(offline=True), "required file")


if __name__ == "__main__":
    unittest.main()
