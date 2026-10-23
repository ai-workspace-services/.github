#!/usr/bin/env python3
"""Persist the Accounts worker's six launcher checks using an offline executor fixture.

These tests exercise the shell caller, not the migration API or database behavior.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

WRAPPER = Path(__file__).with_name("migrate-core-data.sh").resolve()
EXECUTOR = '''#!/usr/bin/python3 -I
import json, os, sys
print(json.dumps({"argv": sys.argv[1:], "environment": sorted(os.environ)}))
'''


class MigrationWrapperTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="migration-wrapper-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.binary = self.root / "reviewed migratectl"
        self.binary.write_text(EXECUTOR)
        self.binary.chmod(0o755)
        self.env = {"PATH": os.defpath, "LANG": "C", "MIGRATECTL_BIN": str(self.binary),
                    "MIGRATECTL_SHA256": hashlib.sha256(self.binary.read_bytes()).hexdigest()}

    def call(self, args, **overrides):
        env = {**self.env, **overrides}
        return subprocess.run(["/bin/bash", str(WRAPPER), *args], cwd=self.root,
                              env=env, text=True, capture_output=True, timeout=10)

    def refused(self, result, reason):
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn(reason, result.stderr)
        self.assertEqual(result.stdout, "", "unverified executor must not run")

    def test_pinned_help_delegates_exact_arguments_and_safe_environment(self):
        subprocess.run(["/bin/bash", "-n", str(WRAPPER)], check=True)
        args = ["--help", "--source-token-env", "QA_SOURCE_TOKEN", "--target-token-env=QA_TARGET_TOKEN"]
        result = self.call(args, QA_SOURCE_TOKEN="fixture-source", QA_TARGET_TOKEN="fixture-target",
                           UNREQUESTED_TOKEN="fixture-unused", HTTP_PROXY="http://127.0.0.1:9",
                           HTTPS_PROXY="http://127.0.0.1:9", PYTHONPATH="/unused-fixture",
                           PGPASSWORD="fixture-unused")
        self.assertEqual(result.returncode, 0, result.stderr)
        observed = json.loads(result.stdout)
        self.assertEqual(observed["argv"], ["transfer-api", *args])
        self.assertTrue({"QA_SOURCE_TOKEN", "QA_TARGET_TOKEN"} <= set(observed["environment"]))
        self.assertFalse({"UNREQUESTED_TOKEN", "HTTP_PROXY", "HTTPS_PROXY", "PYTHONPATH", "PGPASSWORD",
                          "MIGRATECTL_BIN", "MIGRATECTL_SHA256"} & set(observed["environment"]))

    def test_missing_pin_rejects_even_help_without_path_fallback(self):
        for name in ("MIGRATECTL_BIN", "MIGRATECTL_SHA256"):
            with self.subTest(name=name):
                self.refused(self.call(["--help"], **{name: ""}), "are required")

    def test_wrong_digest_and_tampered_binary_never_execute(self):
        self.refused(self.call(["--help"], MIGRATECTL_SHA256="0" * 64), "SHA-256 differs")
        self.binary.write_text(EXECUTOR + "# unreviewed change\n")
        self.refused(self.call(["--help"]), "SHA-256 differs")

    def test_relative_symlink_and_unsafe_file_modes_reject(self):
        self.refused(self.call(["--help"], MIGRATECTL_BIN=self.binary.name), "absolute path")
        alias = self.root / "linked-migratectl"
        alias.symlink_to(self.binary)
        self.refused(self.call(["--help"], MIGRATECTL_BIN=str(alias)), "regular executable")
        for mode in (0o775, 0o757, 0o644):
            with self.subTest(mode=oct(mode)):
                self.binary.chmod(mode)
                self.refused(self.call(["--help"]), "regular executable")

    def test_plaintext_flags_reject_without_echoing_values(self):
        value = "fixture-value-never-echo"
        for flag in ("--token", "--source-token", "--target-token", "--auth-token"):
            for args in ([flag, value], [flag + "=" + value]):
                with self.subTest(args=args):
                    result = self.call(args)
                    self.refused(result, "plaintext credential flags are unsupported")
                    self.assertNotIn(value, result.stdout + result.stderr)

    def test_unsafe_credential_environment_references_reject(self):
        for name in ("LD_PRELOAD", "LD_LIBRARY_PATH", "DYLD_INSERT_LIBRARIES", "DYLD_LIBRARY_PATH",
                     "PATH", "HOME", "BASH_ENV", "ENV", "PYTHONPATH", "PYTHONHOME"):
            for flag in ("--source-token-env", "--target-token-env"):
                with self.subTest(name=name, flag=flag):
                    self.refused(self.call([flag + "=" + name]), "cannot replace executable/runtime")
        for name in ("", "1INVALID", "INVALID NAME", "$(touch injected)"):
            with self.subTest(name=name):
                self.refused(self.call(["--target-token-env", name]), "valid credential environment reference")
        self.assertFalse((self.root / "injected").exists())


if __name__ == "__main__":
    unittest.main()
