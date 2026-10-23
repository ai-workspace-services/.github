#!/usr/bin/env python3
"""Offline contract tests: fixture commits, mocked transport, recording owner runner."""
import json
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

WRAPPER = Path(__file__).with_name("install-control-plane.sh").resolve()
REAL_GIT = shutil.which("git")
GITOPS_URL = "https://github.com/ai-workspace-infra/gitops.git"
PLAYBOOKS_URL = "https://github.com/ai-workspace-infra/playbooks.git"
BILLING_URL = "https://github.com/ai-workspace-services/billing-service.git"

RUNNER = '''import json, os, sys
from pathlib import Path
Path(os.environ["OWNER_RECORD"]).write_text(json.dumps({
    "args": sys.argv[1:], "cwd": os.getcwd(),
    "gitops": os.environ["GITOPS_CHECKOUT"],
    "playbooks": os.environ["PLAYBOOKS_CHECKOUT"],
    "billing": os.environ.get("BILLING_CHECKOUT"),
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
    sources = {os.environ["GITOPS_SHA"]: os.environ["FIXTURE_GITOPS"],
               os.environ["PLAYBOOKS_SHA"]: os.environ["FIXTURE_PLAYBOOKS"]}
    if os.environ.get("BILLING_SHA"):
        sources[os.environ["BILLING_SHA"]] = os.environ["FIXTURE_BILLING"]
    source = sources.get(sha)
    if not source or os.environ.get("FETCH_FAIL") or sha == os.environ.get("FETCH_FAIL_SHA"):
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
        for name in ("GITOPS_CHECKOUT", "PLAYBOOKS_CHECKOUT", "BILLING_CHECKOUT", "CONTROL_PLANE_OFFLINE_TEST",
                     "BILLING_SHA", "FIXTURE_BILLING", "FETCH_FAIL", "FETCH_FAIL_SHA"):
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

    def add_billing(self):
        self.billing = self.root / "billing fixture"
        self.schema = self.billing / "sql/billing-service-schema.sql"
        self.schema.parent.mkdir(parents=True)
        self.schema.write_text("-- Offline fixture; never executed.\n")
        self.billing_sha = self.init_repo(self.billing, BILLING_URL)
        self.env.update(BILLING_SHA=self.billing_sha, FIXTURE_BILLING=str(self.billing))
        self.set_billing_declaration("  billing:\n    source_sha: '" + self.billing_sha +
                                     "'\n    schema_file: sql/billing-service-schema.sql\n")

    def set_billing_declaration(self, fragment):
        self.config.write_text(self.declaration() + fragment)
        self.gitops_sha = self.commit(self.gitops)
        self.env["GITOPS_SHA"] = self.gitops_sha

    def git_calls(self):
        return [json.loads(line) for line in (self.root / "git.jsonl").read_text().splitlines()]

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
        self.assertIsNone(record["billing"], "legacy structural checks must not infer a Billing source")

    def test_billing_fetches_third_canonical_exact_sha_and_delegates(self):
        self.add_billing()
        result = self.run_wrapper()
        self.assertEqual(result.returncode, 0, result.stderr)
        record = json.loads((self.root / "owner.json").read_text())
        self.assertEqual(record["args"], ["--config", record["gitops"] + "/resources/test/candidate.yaml",
                                          "--gitops-ref", self.gitops_sha, "--check"])
        self.assertEqual(Path(record["billing"]).name, "billing-service")
        self.assertTrue(Path(record["billing"]).is_absolute())
        calls = self.git_calls()
        fetches = [call for call in calls if "fetch" in call]
        self.assertEqual([call[-1] for call in fetches],
                         [self.gitops_sha, self.playbooks_sha, self.billing_sha])
        self.assertTrue(all(call[-5:-1] == ["--quiet", "--no-tags", "--depth=1", "origin"] for call in fetches))
        self.assertEqual([call[-1] for call in calls if "remote" in call and "add" in call],
                         [GITOPS_URL, PLAYBOOKS_URL, BILLING_URL])
        self.assertTrue(all("main" not in call and "latest" not in call for call in calls))
        for name in ("gitops", "playbooks", "billing"):
            self.assertFalse(Path(record[name]).exists(), "temporary checkouts must be cleaned")

    def test_billing_fetch_failure_never_falls_back_or_runs_owner(self):
        self.add_billing()
        self.assert_rejected(self.run_wrapper(FETCH_FAIL_SHA=self.billing_sha), "git operation failed")
        calls = self.git_calls()
        self.assertEqual([call[-1] for call in calls if "fetch" in call],
                         [self.gitops_sha, self.playbooks_sha, self.billing_sha])
        self.assertTrue(all("main" not in call and "latest" not in call for call in calls))

    def test_billing_invalid_pins_and_schema_paths_fail_before_owner_fetch(self):
        self.add_billing()
        cases = [("  billing: null\n", "source_sha"), ("  billing: {}\n", "source_sha")]
        for sha in ("main", "v1", "a" * 39, "g" * 40, "A" * 40, "$(touch injected)"):
            cases.append(("  billing:\n    source_sha: '" + sha +
                          "'\n    schema_file: sql/billing-service-schema.sql\n", "source_sha"))
        for path in ("", "../sql/billing-service-schema.sql", "/sql/billing-service-schema.sql", "other.sql"):
            cases.append(("  billing:\n    source_sha: '" + self.billing_sha +
                          "'\n    schema_file: '" + path + "'\n", "schema_file"))
        for fragment, message in cases:
            with self.subTest(fragment=fragment):
                self.set_billing_declaration(fragment)
                self.assert_rejected(self.run_wrapper(offline=True, BILLING_CHECKOUT=str(self.billing)), message)
        self.assertNotIn('"fetch"', (self.root / "git.jsonl").read_text())
        self.assertFalse((self.root / "injected").exists())

    def test_billing_offline_exact_clean_https_checkout_without_fetch(self):
        self.add_billing()
        result = self.run_wrapper(offline=True, BILLING_CHECKOUT=str(self.billing))
        self.assertEqual(result.returncode, 0, result.stderr)
        record = json.loads((self.root / "owner.json").read_text())
        self.assertEqual(record["billing"], str(self.billing))
        self.assertNotIn('"fetch"', (self.root / "git.jsonl").read_text())

    def test_billing_local_override_requires_explicit_offline_check(self):
        self.add_billing()
        self.assert_rejected(self.run_wrapper(BILLING_CHECKOUT=str(self.billing)), "local checkouts require")
        self.assert_rejected(self.run_wrapper(["--config", "resources/test/candidate.yaml", "--gitops-ref", self.gitops_sha],
                                              offline=True, BILLING_CHECKOUT=str(self.billing)), "local checkouts require")

    def test_billing_offline_declaration_requires_checkout_without_network(self):
        self.add_billing()
        self.assert_rejected(self.run_wrapper(offline=True), "BILLING_CHECKOUT is required")
        self.assertNotIn('"fetch"', (self.root / "git.jsonl").read_text())

    def test_billing_override_without_declaration_rejected(self):
        self.assert_rejected(self.run_wrapper(offline=True, BILLING_CHECKOUT=str(self.root)),
                             "BILLING_CHECKOUT requires a matching release.billing")

    def test_billing_local_origin_must_be_canonical_https(self):
        self.add_billing()
        for origin in ("https://example.com/billing-service.git", "git@github.com:ai-workspace-services/billing-service.git"):
            with self.subTest(origin=origin):
                self.git(self.billing, "remote", "set-url", "origin", origin)
                self.assert_rejected(self.run_wrapper(offline=True, BILLING_CHECKOUT=str(self.billing)),
                                     "canonical repository")

    def test_billing_local_head_must_equal_declared_source_sha(self):
        self.add_billing()
        self.schema.write_text("-- Different committed Billing source.\n")
        self.commit(self.billing)
        self.assert_rejected(self.run_wrapper(offline=True, BILLING_CHECKOUT=str(self.billing)), "HEAD does not match")

    def test_billing_modified_untracked_and_ignored_files_rejected(self):
        self.add_billing()
        original = self.schema.read_text()
        self.schema.write_text(original + "-- changed\n")
        self.assert_rejected(self.run_wrapper(offline=True, BILLING_CHECKOUT=str(self.billing)), "must be clean")
        self.schema.write_text(original)
        for name in ("untracked", "ignored"):
            with self.subTest(name=name):
                if name == "ignored":
                    (self.billing / ".git/info/exclude").write_text("ignored\n")
                extra = self.billing / name
                extra.write_text("fixture")
                self.assert_rejected(self.run_wrapper(offline=True, BILLING_CHECKOUT=str(self.billing)), "must be clean")
                extra.unlink()

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


class ProfileRendererTests(unittest.TestCase):
    def test_generated_region_preserves_bilingual_deployment_tldr(self):
        source = WRAPPER.with_name("render-profile-readme.py")
        spec = importlib.util.spec_from_file_location("profile_renderer", source)
        module = importlib.util.module_from_spec(spec)
        with patch.object(sys, "dont_write_bytecode", True):
            spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory(prefix="profile-region-test-") as temporary:
            module.TARGETS = {}
            originals = {}
            for language, name in (("en", "README.md"), ("zh", "README_ZH.md")):
                original = (WRAPPER.parents[1] / "profile" / name).read_text()
                originals[language] = original
                target = Path(temporary) / name
                target.write_text(original)
                module.TARGETS[language] = target
            data = {"latest": {"prod": None, "uat": {"metadata": {"container": {"tags": ["fixture-tag"]}},
                                                       "created_at": "2026-10-23T00:00:00Z"}, "sit": None},
                    "images": []}
            with patch.object(module, "collect", return_value=data), patch.dict(os.environ, GITHUB_TOKEN="offline-fixture"):
                self.assertEqual(module.main(), 0)
            for language, target in module.TARGETS.items():
                updated = target.read_text()
                self.assertEqual(module.BLOCK.sub("<release-region>", originals[language]),
                                 module.BLOCK.sub("<release-region>", updated))
                self.assertIn("install-control-plane.sh", updated)
                self.assertIn("r101", updated)
                self.assertIn("artifact_found", module.BLOCK.search(updated).group())
                self.assertNotIn("![live]", updated)


if __name__ == "__main__":
    unittest.main()
