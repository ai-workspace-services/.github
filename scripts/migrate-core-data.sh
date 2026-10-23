#!/usr/bin/env bash
# URL migration is implemented by a release-manifest-pinned Accounts binary.
set -euo pipefail
set +x
# Bootstrap: install the reviewed release binary privately, obtain its SHA-256
# from the verified release manifest, then set MIGRATECTL_BIN (absolute path)
# and MIGRATECTL_SHA256. No installation, downloads or PATH fallback occur here.
/usr/bin/env -u PYTHONPATH -u PYTHONHOME -u LD_PRELOAD -u LD_LIBRARY_PATH \
  -u DYLD_INSERT_LIBRARIES -u DYLD_LIBRARY_PATH -u DYLD_FRAMEWORK_PATH \
  /usr/bin/python3 -I - "$@" <<'PY'
import hashlib
import os
from pathlib import Path
import re
import stat
import sys


def fail(message):
    print("migrate-core-data: " + message, file=sys.stderr)
    sys.exit(2)


binary = os.environ.get("MIGRATECTL_BIN", "")
expected = os.environ.get("MIGRATECTL_SHA256", "")
if not Path(binary).is_absolute() or not re.fullmatch(r"[0-9a-fA-F]{64}", expected):
    fail("MIGRATECTL_BIN absolute path and MIGRATECTL_SHA256 from the verified release manifest are required")
try:
    metadata = os.lstat(binary)
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_mode & 0o022 or not os.access(binary, os.X_OK):
        fail("pinned binary must be a regular executable, without group/world write access or symlink")
    digest = hashlib.sha256()
    with open(binary, "rb") as stream:
        opened = os.fstat(stream.fileno())
        if (opened.st_dev, opened.st_ino) != (metadata.st_dev, metadata.st_ino):
            fail("pinned binary changed before verification")
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != expected.lower():
        fail("pinned binary SHA-256 differs from the release manifest")
    after = os.lstat(binary)
    if (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) != (
        metadata.st_dev, metadata.st_ino, metadata.st_size, metadata.st_mtime_ns
    ):
        fail("pinned binary changed during verification")
    # Preserve only credential references actually requested, standard TLS/Vault
    # identity configuration, and the user's home for Vault's existing login.
    names = {"HOME", "LANG", "LC_ALL", "SSL_CERT_FILE", "SSL_CERT_DIR",
             "VAULT_ADDR", "VAULT_NAMESPACE", "VAULT_TOKEN", "VAULT_CACERT",
             "VAULT_CAPATH", "VAULT_CLIENT_CERT", "VAULT_CLIENT_KEY"}
    arguments = sys.argv[1:]
    for index, argument in enumerate(arguments):
        flag, separator, value = argument.partition("=")
        if flag in ("--token", "--source-token", "--target-token", "--auth-token"):
            fail("plaintext credential flags are unsupported; use token-env or auth-kv references")
        if flag in ("--source-token-env", "--target-token-env"):
            if not separator:
                value = arguments[index + 1] if index + 1 < len(arguments) else ""
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
                fail("valid credential environment reference required")
            if value.startswith(("LD_", "DYLD_")) or value in {
                "PATH", "HOME", "BASH_ENV", "ENV", "PYTHONPATH", "PYTHONHOME"
            }:
                fail("credential reference cannot replace executable/runtime environment settings")
            names.add(value)
    environment = {name: os.environ[name] for name in names if name in os.environ}
    environment["PATH"] = "/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:/usr/local/bin"
    os.execve(binary, [binary, "transfer-api", *arguments], environment)
except OSError:
    fail("pinned binary unavailable; install the reviewed release before running this caller")
PY
