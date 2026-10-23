# Selfhost control-plane deployment and migration

[简体中文](control-plane-deployment-and-migration.zh.md)

Status: implementation candidate, isolated integration acceptance pending. Commands
below describe the reviewed interface; no published installer release or runtime
availability is claimed. Replace every placeholder with reviewed release evidence.

Companion declaration: [GitOps Draft #504](https://github.com/ai-workspace-infra/gitops/pull/504)
([contract task #503](https://github.com/ai-workspace-infra/gitops/issues/503)). Its
templates are illustrative and cannot execute with `example_only: true`.

## Three entrypoints

| Script | Purpose | Contract |
| --- | --- | --- |
| [`install-control-plane.sh`](../scripts/install-control-plane.sh) | Install Accounts, Billing, Console/Portal, Content, PostgreSQL and declared dependencies | `--config <GitOps-relative YAML> --gitops-ref <full SHA> [--check]` |
| `scripts/migrate-core-data.sh` (Accounts worker) | One-way identity and complete billing migration through Accounts URLs | Pinned `MIGRATECTL_BIN` / `MIGRATECTL_SHA256`; source/target URL and authentication references; preview by default; isolated acceptance pending |
| [`setup-proxy.sh`](../scripts/setup-proxy.sh) | Edge node onboarding to an existing control plane | Existing `--node` and node credential contract; implementation unchanged |

The legacy `setup-selfhost.sh` domain printer has been merged into the new
installation entrypoint. Domains now come from the pinned GitOps declaration.
This wrapper parses inputs, verifies commits and delegates; Playbooks owns host,
certificate, deployment, backup/restore and migration execution. IaC owns resources,
DNS, state and generated CMDB. GitOps owns non-secret desired state. Accounts owns
data scope, conflicts, transactions and idempotency. There is no inline SQL,
Ansible or Compose execution in the public wrapper.

## Eight stages

| Stage | Action | Required evidence |
| --- | --- | --- |
| 1 | Prepare GitOps | Environment, resources, domains, secret references, source/target identities |
| 2 | Provision through IaC | Reviewed plan, independent state, generated CMDB, host and SSH identity |
| 3 | Build one immutable five-repository snapshot | All builds pass; source SHA, image digest, schema and migration checksums recorded |
| 4 | Install Selfhost Control Plane | SSH → Playbook → fixed GitOps → Doco-CD; verify actual loaded artifacts |
| 5 | Migrate core data one way | Recoverable target backup, conflict-free preview, transactional import and business fingerprints |
| 6 | Accept the candidate environment | Restore with business data, applicable regressions, rerun, interruption recovery and observation |
| 7 | Prepare traffic handover | Concrete writer handover, final synchronization, DNS, observation and recovery plan; human confirmation pending |
| 8 | Execute confirmed handover and accept | Fence source writes, final synchronization, transfer writer ownership, switch traffic and observe real business |

A fresh empty environment follows stages 1–4 and 6, recording why migration is
skipped. A generation upgrade follows all eight. An existing environment rolling
update starts with inventory and backup, makes non-destructive IaC changes,
converges the selected release, runs only explicitly approved incremental data
changes, converges edge nodes and verifies. Rerun never implies initialization,
reset, import or a second writer. While the source serves, record the snapshot
boundary; final synchronization belongs to stage 8. Stage 7 cannot authorize it.

Acceptance covers identity/MFA, all billing dependencies, target-only data,
conflict rollback, concurrency locks, expired plans, replay, interrupted recovery
and schema fingerprints on PostgreSQL 17. Regressions include certificates/public
SNI, scoped credentials, ingress, Agent enrollment, VLESS, OAuth/webhooks, Content
and Exporter → Vector → Billing → PostgreSQL → Accounts. Observe at least two
complete relevant collection cycles, with start/end and freshness evidence.
Required FAIL, BLOCKED or NOT_RUN results stop handover.

## Immutable builds and releases

The five service repositories are `accounts`, `billing-service`, `portal`,
`content-service` and `postgresql`. `daily-main-snapshot.yaml` must select that
explicit list and run the build-only lane. Before tagging or dispatching, check
that Actions is enabled in every repository, the intended workflow is enabled,
and the workflow supports dispatch. Inspect the actual workflow and tag-triggered
jobs: a build must not provision, deploy, migrate or change DNS.

Verified r101 evidence: all five tags were CREATED at their source SHAs.
PostgreSQL workflow dispatch returned HTTP 422, `Actions has been disabled for
this repository`. The snapshot is **tags-created / build-incomplete**. This is
not a repository-filter bug or evidence of absent tags. Capture the exact workflow
response, restore Actions enablement through the owning process, and retry the
build at the existing tag/SHA when the source is unchanged. A new immutable
revision is needed only when code/source SHA changes. Never move an existing tag.

Each repository needs matching tag/SHA, successful build URL, expected artifact
and digest evidence before deployment. Missing, failed or unknown builds block
selection. Tags and registry artifacts alone do not establish runtime health.
Promote reviewed artifacts without rebuilding from a moving branch. Stable
releases are immutable; formal release notes supply versioned script URLs and
the matching GitOps/Playbooks commits. No release identifier is invented here.

## Installation contract

The operator runtime requires Git, Python 3 and PyYAML, plus the dependencies of
the reviewed Playbooks owner. Missing Python/PyYAML fails explicitly; the wrapper
does not install packages. Prepare IaC CMDB and a protected vars file outside the
source checkouts. `CONTROL_PLANE_VARS_FILE` contains nonsecret runtime policy and
Vault references only, never plaintext credentials. Playbooks resolves Vault
credentials inside the owner before execution; the wrapper does not resolve or
copy secret values. Credentials never enter command arguments or public evidence.

The selected owner requires Python 3.11+, Ansible and its documented collections;
applying also requires the Vault CLI and an already-issued short-lived Vault
identity. The protected policy is operator-owned, mode 0600 or 0400, with a
`control_plane_runtime` mapping containing `vault_addr`, `vault_token_env: VAULT_TOKEN`
and the owner's complete `secret_refs` mapping. `vault_addr` must be an explicit
HTTPS origin; an inherited `VAULT_ADDR` alone does not replace the policy.
`--check` validates the local declaration/policy; it neither authenticates to
Vault nor proves that credentials, SSH or the target are usable.

```bash
export ENTRYPOINT_RELEASE='<reviewed immutable .github release or full SHA>'
export GITOPS_SHA='<reviewed full 40-character GitOps commit SHA>'
export CONTROL_PLANE_CMDB='/secure/run/cmdb.json'
export CONTROL_PLANE_VARS_FILE='/secure/run/vars.yaml'

curl -fsSL "https://raw.githubusercontent.com/ai-workspace-services/.github/${ENTRYPOINT_RELEASE}/scripts/install-control-plane.sh" \
  -o /tmp/install-control-plane.sh
# Inspect the downloaded script and verify its release checksum before execution.
bash /tmp/install-control-plane.sh \
  --config '<path/to/control-plane.yaml>' --gitops-ref "$GITOPS_SHA" --check
# After owner integration acceptance and the relevant deployment approval:
bash /tmp/install-control-plane.sh \
  --config '<path/to/control-plane.yaml>' --gitops-ref "$GITOPS_SHA"
```

`--config` is a tracked YAML file inside that GitOps commit, not an absolute path
or an external file. `execution.playbooks_sha` must be a full commit SHA. Repository
URLs are fixed to `https://github.com/ai-workspace-infra/gitops.git` and
`https://github.com/ai-workspace-infra/playbooks.git`; config cannot override them.
The wrapper fetches each exact commit, verifies HEAD and cleanliness, safely reads
YAML, then runs from the Playbooks checkout:

```text
python3 scripts/control_plane/entrypoint.py --config <resolved-path> --gitops-ref <SHA> [--check]
```

`release.snapshot_tag` identifies the five service builds. `--gitops-ref` identifies
the separate GitOps declaration commit; GitOps does not need a same-name service
snapshot tag. Both identities must be recorded without substituting one for the other.

It passes absolute `GITOPS_CHECKOUT`, `PLAYBOOKS_CHECKOUT`, `CONTROL_PLANE_CMDB` and
`CONTROL_PLANE_VARS_FILE`. The owner must validate the reviewed declaration,
target, immutable artifacts and protected runtime inputs. Cross-repository schema
conformance remains an integration gate; mocked wrapper tests do not establish it.
Missing owner, commit or prerequisite
fails closed. There is no branch/main fallback. `--check` delegates preflight;
it does not prove application or data-flow acceptance.

Path and input boundaries:

| Input | Resolution/owner |
| --- | --- |
| Public `--config` | Tracked YAML relative to the GitOps root; wrapper passes its resolved absolute path to the owner |
| `GITOPS_CHECKOUT`, `PLAYBOOKS_CHECKOUT` | Wrapper-generated fixed checkouts; operator overrides are offline-test-only |
| `CONTROL_PLANE_CMDB`, `CONTROL_PLANE_VARS_FILE` | Required external operator files, resolved from the invocation directory before the owner changes working directory |
| `AI_WORKSPACE_CMDB_JSON`, `CMDB_FILE` | Owner sets both from `CONTROL_PLANE_CMDB` before calling the inventory adapter |
| `release.doco_cd.target` / `storage_target` | Select `.doco-cd.<selection>.yml` at the pinned GitOps root; `working_dir` is GitOps-root-relative, Compose/env files are relative to that working directory |

The public GitOps schema rejects `target.cmdb_file` and top-level `vars_files`;
use the external operator inputs, even if a broader owner parser accepts those
fields. `source.host` / `source.generation` are optional deployment audit metadata,
not migration endpoint settings. The separate `kind: accounts-migration` example
does not go into `install-control-plane.sh`; URL migration uses the flags below,
and no automatic migration-YAML consumer is claimed here. Both GitOps examples
remain intentionally invalid until a reviewed executable declaration is prepared.

The CMDB must also describe storage: `storage` (or
`host_vars.control_plane_storage`) selects `profile: root` or `dedicated` and
`data_path`; dedicated storage adds the declared `mount_path` / `device_path`.
The pinned PostgreSQL bind must match `data_path`. A root profile does not require
a separate disk; the owner verifies the actual target storage during execution.

Offline wrapper tests may set `CONTROL_PLANE_OFFLINE_TEST=1`, `GITOPS_CHECKOUT`
and `PLAYBOOKS_CHECKOUT` together with `--check`. Both must be repository roots
with the exact canonical origin (HTTPS or its `git@github.com:` SSH spelling), matching HEAD and no modified, untracked
or ignored files. These overrides are for offline tests only. Normal operations
use fresh temporary fixed-commit checkouts.

## Migration URL contract — isolated acceptance pending

The Accounts worker owns the client implementation. These are the accepted
planned flags, not a claim that the API is available on existing deployments:

```bash
export MIGRATECTL_BIN='/secure/tools/migratectl'
export MIGRATECTL_SHA256='<64-character SHA-256 from the verified release manifest>'
bash scripts/migrate-core-data.sh \
  --source-url https://accounts-source.example.com \
  --source-token-env SOURCE_MIGRATION_TOKEN \
  --target-url https://accounts-target.example.com \
  --target-token-env TARGET_MIGRATION_TOKEN
# Apply only the reviewed preview, using the same source/target/auth references:
# append --apply --plan-id '<id>' --plan-sha256 '<sha256>'
```

Provision the reviewed Accounts binary separately. `MIGRATECTL_BIN` must be an
absolute path to a regular executable file, not a symlink, and must not be
group/world-writable. `MIGRATECTL_SHA256` comes from independently verified release
evidence, not merely a hash calculated from an untrusted local download. The
Python 3 wrapper checks that digest before executing `transfer-api`; it does not
install/download a binary or discover one through `PATH`. The pin contract has
been inspected in the Accounts-owned caller; isolated API acceptance remains pending.

`--source-auth-kv` or `--target-auth-kv` may replace the respective token-env flag;
each pair is mutually exclusive. Arguments contain reference names, never token
values. Migration credentials are short lived, peer/use scoped and independent
of the shared service token. `/api/migrations/v1` is the new opt-in API contract:
source read-only consistent snapshot/manifest/stream; target preview/apply/status
with protected staging, checksums, target-driven fetching and idempotent recovery.
Plans bind source snapshot, target baseline, tool version, scope and schema.
Changed baselines, expiry, identity/financial conflicts, illegal peers, redirects,
same-database migration, tampering and unsafe target-only activity must fail.

Scope includes stable identity/email/password hashes, MFA and recovery state,
OAuth, XConnect identity, teams, subscriptions, quotas, usage, invoices, payments,
refunds and related audit dependencies. Preserve protected TOTP material and verify
target usability. Exclude old sessions, temporary challenges and migration access
credentials. No real payment, refund or notification calls during migration.
Use machine-readable table/field coverage and content fingerprints, not row counts
alone. Receipts and user data remain in protected storage.

Existing V4 endpoints do not yet provide this API. V4→V5 retains the separately
reviewed SSH/database owner path; URL mode must explicitly report unsupported
endpoints with no implicit fallback. V4 does not need an API backport for the first
migration. Merge/release dependencies in order: Accounts → Playbooks → GitOps →
public caller. Keep this caller Draft until the owner commit, declaration and
isolated end-to-end acceptance are integrated.

## Historical records

These files retain their original dates, assumptions and evidence; use this guide
for the unified entrypoint contract:

- [PROD V2 deployment](prod-v2-deployment.md)
- [2026-10-16 upgrade/cutover](prod-v2-upgrade-cutover-20261016.md)
- [2026-10-18 upgrade recovery](prod-v2-upgrade-recovery-20261018.md)
- [V3 catalog regression](E2E/p0f-v3-catalog-upgrade-20261019.md)
- [V4 pinned node deployment](prod-v4-pinned-node-deployment-tldr.md)
- [Historical Selfhost implementation task](selfhost-orchestrator-one-shell-uat-prod.md)

Keep execution IDs, actual endpoint bindings, host/database identities, backup and
restore evidence, migration plan/results and regression receipts in controlled
operational records. Public documentation contains generic examples only.
