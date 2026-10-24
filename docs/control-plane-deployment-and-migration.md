# Selfhost control-plane deployment and migration

[简体中文](control-plane-deployment-and-migration.zh.md)

Status: implementation candidate, isolated integration acceptance pending. Commands
below describe the reviewed interface; no published installer release or runtime
availability is claimed. Replace every placeholder with reviewed release evidence.

Declaration contract: [GitOps #504](https://github.com/ai-workspace-infra/gitops/pull/504)
(merged; [contract task #503](https://github.com/ai-workspace-infra/gitops/issues/503)).
[Follow-up #506](https://github.com/ai-workspace-infra/gitops/pull/506) remains pending.
The contract templates are illustrative and cannot execute with `example_only: true`.

## Three entrypoints

| Script | Purpose | Contract |
| --- | --- | --- |
| [`install-control-plane.sh`](../scripts/install-control-plane.sh) | Install Accounts, Billing, Console/Portal, Content, PostgreSQL and declared dependencies | `--config <GitOps-relative YAML> --gitops-ref <full SHA> [--check]` |
| [`migrate-core-data.sh`](../scripts/migrate-core-data.sh) | Accounts migration client for one-way identity and complete billing transfer through Accounts URLs | Pinned `MIGRATECTL_BIN` / `MIGRATECTL_SHA256`; source/target URL and authentication references; preview by default; isolated acceptance pending |
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
| 1 | Prepare GitOps | Reviewed environment/resource/domain declarations, secret references, source/target identities and pinned execution refs |
| 2 | Provision through IaC | Reviewed plan, independent state, generated CMDB, host and SSH identity; no unreviewed resource replacement |
| 3 | Build one immutable five-repository snapshot | All five source SHAs, build provenance, artifact digests, schema and migration checksums verified through GitHub Actions or the approved local-build path |
| 4 | Install the control plane over SSH | SSH → Playbook → pinned GitOps → Doco-CD; verify the artifacts and configuration actually loaded on the target |
| 5 | Migrate core data with `migratectl` | Recoverable target backup, conflict-free preview, reviewed plan, transactional one-way import and business fingerprints |
| 6 | Run full candidate-environment regression | Restore with business data, all applicable regressions, idempotent rerun, interruption recovery, and stable observation |
| 7 | Prepare DNS cutover, without changing traffic | Exact records/TTL, writer handover, final-sync procedure, observation and rollback plan reviewed; explicit human confirmation still required |
| 8 | Execute explicitly confirmed cutover and accept | Record authorized confirmation and scope; fence source writes, final-sync, transfer writer ownership, change DNS, read back, then observe real business |

A fresh empty environment follows stages 1–4 and 6, recording why migration is
skipped. A generation upgrade follows all eight. An existing environment rolling
update starts with inventory and backup, makes non-destructive IaC changes,
converges the selected release, runs only explicitly approved incremental data
changes, converges edge nodes and verifies. Rerun never implies initialization,
reset, import or a second writer. While the source serves, record the snapshot
boundary; final synchronization belongs to stage 8. Stage 7 prepares and reviews
DNS values but does not edit DNS or authorize a writer change. Stage 8 requires
an explicit, recorded confirmation from the authorized human for the named
environment, source, target, data action and DNS records; silence, a passed
regression, or completion of stage 7 is not confirmation.

### Cleanroom validation and real replays

Prove that serving and candidate namespaces, state keys, lineages and actual
cloud-resource identities are disjoint. Verify an off-host encrypted recovery
point before deleting candidate compute. The
[IaC owner](https://github.com/ai-workspace-infra/iac_modules/blob/main/docs/howto/isolated-candidate-validation.md)
restricts the saved destroy plan to that instance and retains the source,
firewall, independent storage, backups and remote state. Normal recreation
restores default deletion protection. Obtain the full provider-attested SSH
fingerprint and match the network key before strict SSH; prepare controller
collections before Ansible parses roles. A single IPv6 `/128` is a host address,
while a network prefix must not become a deployment target. Canonical state
witnesses sort only Terraform's unordered check-result sets and retain all
resource values, lineage, serial and status changes.

Use the reviewed prebuilt `migratectl` for the explicitly approved data scope.
Users-only apply takes the shared transaction advisory lock, then exclusive
users/checkpoint locks before target data reads, rechecks the exact preview
digest under those locks, and releases them on commit or rollback. A writer
committing while it waits invalidates the old plan. This path no longer requires
a paused-writer assertion; other migration commands retain their contracts.
See [Accounts #271](https://github.com/ai-workspace-services/accounts/pull/271)
and its PostgreSQL 17 concurrent-writer regression.

After the initial deployment, migration and isolated recovery, use the populated
candidate as the baseline for at least three real rounds of IaC convergence,
complete deployment, fresh migration preview/apply/compare and state comparison.
Pin all source and artifact identities. Record Shanghai start/end, run ID,
exit code, schema/checkpoint and database identity. Compare business content and
user row versions, configuration, and long-running container identity/start/
restart state. A declared one-shot asset task may run, but must exit successfully
and leave identical complete asset content. Preserve failures and their new
reverification receipts. A live source remains bounded by its recorded snapshot;
final catch-up and traffic/writer transfer still require stage 8 authorization.

Acceptance covers identity/MFA, all billing dependencies, target-only data,
conflict rollback, concurrency locks, expired plans, replay, interrupted recovery
and schema fingerprints on PostgreSQL 17. Regressions include certificates/public
SNI, scoped credentials, ingress, Agent enrollment, VLESS, OAuth/webhooks, Content
and Exporter → Vector → Billing → PostgreSQL → Accounts. Observe at least two
complete relevant collection cycles, with start/end and freshness evidence.
Required FAIL, BLOCKED or NOT_RUN results stop handover.

## Immutable builds and releases

The five service repositories are `accounts`, `billing-service`, `portal`,
`content-service` and `postgresql`. Produce one snapshot from exact, recorded
source SHAs. GitHub Actions may run the build-only lane (for example,
`daily-main-snapshot.yaml`); GitHub Actions is not a mandatory build dependency.
An operator may instead use the approved local immutable-build path below.
Either path must build only: it must not provision, deploy, migrate or change
DNS. Inspect the actual workflow or local build procedure before use.

Verified r101 evidence: all five tags were CREATED at their source SHAs. CI runs
and release manifests for `accounts`, `billing-service`, `portal` and
`content-service` were verified successful; the PostgreSQL release is absent.
PostgreSQL dispatch through the GitHub App returned HTTP 422, `Actions has been
disabled for this repository`, again on rerun attempt 2. See
[run 39891515095, attempt 2](https://github.com/ai-workspace-infra/platform-ops-toolkit/actions/runs/39891515095).
Separately, the personal administrator API reports `actions/permissions`
`enabled: true` and workflow state `active`. The observed failure is a rejection
of the GitHub App dispatch path; it does not establish that Actions remains
globally disabled for the repository. The actor configuration discrepancy remains
unresolved. The historical r101 + HTTP 422 result remains **tags-created / four
builds verified / PostgreSQL dispatch rejected and release absent**, therefore
build-incomplete and not deployable. This is not a repository-filter bug or
evidence of absent tags.

The 422 record describes the GitHub App dispatch path at that time; it does not
require waiting for that actor configuration before using an approved local
build. Preserve the exact API response and identity-specific settings evidence
as historical facts. A local build may complete a missing artifact only if it
uses the existing recorded source SHA and immutable snapshot identity, and emits
the equivalent provenance and verification evidence below. It does not change
the historical r101 result or make that snapshot deployable retroactively.
Never move, replace or reuse a tag for different source.

### Approved local immutable-build path

Use this path when the release owner approves a local build for the named
snapshot. It is an alternative to Actions, not an exception to immutable source
and artifact controls:

1. Check out each required repository at its recorded full commit SHA. Confirm
   clean tracked and untracked state; record repository, snapshot tag and SHA.
2. Run the repository's reviewed build and verification procedure without
   changing build inputs or fetching mutable branch content. Record the exact
   commands, toolchain versions and result for each repository.
3. Record artifact names, sizes and SHA-256 values, container image digests,
   schema identity and migration checksums in a snapshot manifest. Keep the
   manifest and build logs with the release evidence.
4. Publish or retain outputs in an approved immutable artifact store. Read each
   artifact back and verify its digest against the manifest before selection.
   Do not treat a local filesystem copy, mutable tag, or successful compile as
   publication or runtime acceptance.
5. Mark the snapshot deployable only when all five repositories have complete,
   matching source and artifact evidence. Reuse already verified CI artifacts
   only when their source SHA and digest evidence match the same snapshot.

If the approved procedure cannot produce equivalent, independently reviewable
provenance and immutable artifacts, the snapshot remains incomplete. No GitHub
Actions enablement, workflow dispatch, or retry is required for a valid local
build; Actions results, when used, remain separately attributed to their actual
workflow run.

Each repository needs a matching tag/SHA, build record or workflow-run URL,
expected artifact and digest evidence before deployment. Missing, failed or
unknown builds block selection. Tags and registry artifacts alone do not
establish runtime health.
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
or an external file. `execution.playbooks_sha` must be a full commit SHA. Execution
also requires `release.billing.source_sha` (a lowercase 40-character commit SHA)
and `release.billing.schema_file: sql/billing-service-schema.sql`.
Repository URLs are fixed to `https://github.com/ai-workspace-infra/gitops.git`,
`https://github.com/ai-workspace-infra/playbooks.git` and
`https://github.com/ai-workspace-services/billing-service.git`; config cannot
override them. The wrapper safely reads YAML and automatically fetches three
exact commits: GitOps at `--gitops-ref`, Playbooks at `execution.playbooks_sha`,
and Billing at `release.billing.source_sha`. It verifies HEAD, canonical origin
and cleanliness, then runs from the Playbooks checkout:

```text
python3 scripts/control_plane/entrypoint.py --config <resolved-path> --gitops-ref <SHA> [--check]
```

`release.snapshot_tag` identifies the five service builds. `--gitops-ref` identifies
the separate GitOps declaration commit; GitOps does not need a same-name service
snapshot tag. Both identities must be recorded without substituting one for the other.

It passes absolute `GITOPS_CHECKOUT`, `PLAYBOOKS_CHECKOUT`, `BILLING_CHECKOUT`,
`CONTROL_PLANE_CMDB` and `CONTROL_PLANE_VARS_FILE`. No new public flags or secrets
are needed. The owner's `billing_artifact` verifies the tracked SQL against
`release.accounts.billing_schema_sha256`; the owner applies reviewed Billing DDL
to the first empty database before business grants/startup. The wrapper never
executes SQL. Old structural `--check` fixtures may omit `release.billing` and
use only two checkouts; actual owner execution fails without the Billing declaration
and artifact. The owner must validate the reviewed declaration,
target, immutable artifacts and protected runtime inputs. Cross-repository schema
conformance remains an integration gate; mocked wrapper tests do not establish it.
Missing owner, commit or prerequisite
fails closed. There is no branch/main fallback. `--check` delegates preflight;
it does not prove application or data-flow acceptance.

Path and input boundaries:

| Input | Resolution/owner |
| --- | --- |
| Public `--config` | Tracked YAML relative to the GitOps root; wrapper passes its resolved absolute path to the owner |
| `GITOPS_CHECKOUT`, `PLAYBOOKS_CHECKOUT`, `BILLING_CHECKOUT` | Wrapper-generated fixed checkouts; Billing uses `release.billing.source_sha`; operator overrides are offline-test-only |
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
and `PLAYBOOKS_CHECKOUT` together with `--check`. When `release.billing` is declared,
`BILLING_CHECKOUT` is also required; offline mode never fetches a missing checkout.
All must be repository roots with matching exact HEAD and no modified, untracked
or ignored files. GitOps/Playbooks accept the canonical HTTPS origin or its
`git@github.com:` SSH spelling; Billing requires the exact canonical HTTPS origin
used by the owner. A Billing override without its declaration is rejected.
These overrides are for offline tests only. Normal operations use fresh temporary
fixed-commit triple checkouts.

## Migration URL contract — isolated acceptance pending

The Accounts migration client uses the interface below. URL/API mode still awaits
isolated acceptance; existing deployments are not claimed to expose this API.

The historical inspection sampled [#267](https://github.com/ai-workspace-services/accounts/pull/267) while it was Draft,
source `c5e3bae3bea1d9b71ee2a579e4da8657fc192bc8`. Implementation
`84df2658cd70da0cdfd7e38d559f688705d4c218` resolves the former 32 MiB total-row
limit: encrypted immutable chunks have checksums and durable resumable retrieval;
preview/apply consume pages through SQL TEMP tables rather than whole row maps.
The recorded isolated PostgreSQL 17 regression passed approximately 44 MiB
preview/apply and interrupted-fetch recovery. The remaining 64 MiB limit applies
to metadata objects, not the total business dataset; compact row-digest metadata
is still retained, so this is not an unbounded constant-memory guarantee.
`--transfer-only` stages/verifies pages without business writes; default preview
is unchanged. Missing-page downloads have at most two attempts; mutation requests
are not automatically retried.
Rechecked on 2026-10-24: #267 merged as
`e1793b3e3586bfad5f8173ee3480189b98fde9e0`. The Draft reference and source above
remain historical samples; merge does not establish full runtime API acceptance.

[GitOps #505](https://github.com/ai-workspace-infra/gitops/issues/505) remains open
for the actual populated backup/restore gate and complete cross-repository runtime
acceptance; encrypted chunk/resume code is no longer the missing implementation.
[Playbooks #729](https://github.com/ai-workspace-infra/playbooks/pull/729) has merged
owner work including the optional listener and Billing/bootstrap readiness.
These code and isolated-regression results do not establish a fresh runtime
deployment, published binary release or usable live migration API.

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

The producer in Accounts `e829428800617900c51c779e4462b6236c8c017b` builds
`migratectl-linux-amd64`, `migratectl-linux-arm64`, `migratectl-darwin-amd64` and
`migratectl-darwin-arm64`, plus `SHA256SUMS` and `release-manifest.json`. Linux is
the supported host migration runner; Darwin assets support local tooling, and
Windows is not advertised. Follow the fixed-source
[Accounts release asset contract](https://github.com/ai-workspace-services/accounts/blob/c5e3bae3bea1d9b71ee2a579e4da8657fc192bc8/docs/migrations/migratectl-release-assets.md):

1. Verify the immutable release tag and exact selected target Accounts source SHA.
   The producer requires a clean checkout with HEAD equal to full `GITHUB_SHA`;
   manifest `commit` must equal that expected source SHA. A different commit is
   rejected, not accepted because the filename matches.
2. Check manifest `schema: 1`, `repository`, `tag` and `commit`. `files` lists
   filenames; `artifacts` records each exact `name`, `sha256`, `size_bytes`.
3. Verify `SHA256SUMS` against its own entry in the trusted manifest, then verify
   the selected binary against both its manifest entry and `SHA256SUMS`, including
   actual byte size. `SHA256SUMS` covers payloads and does not hash itself;
   neither checksum file provides a checksum of itself.
4. Install the verified protected executable, then set `MIGRATECTL_BIN` and the
   manifest's expected asset `MIGRATECTL_SHA256`. The producer implementation SHA
   does not replace the selected release source commit or artifact digest.
   Historical releases without these assets are not silently accepted or modified.

Four-platform local builds, checksum checks and native help passed; publication
was not performed by those packaging tests. Verify actual published assets before
operational use and record fixed Accounts and Playbooks commits separately.

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

## Online business append and post-repair recovery points

The [V5 append and replay receipt](https://github.com/ai-workspace-services/knowledge/blob/main/content/02-iac-devops/cloud-infrastructure-devsecops-baseline/records/prod-v5-20261023/20261024-prod-v5-business-append-and-traffic-regression.zh.md) and [populated environment snapshot](https://github.com/ai-workspace-services/knowledge/blob/main/content/02-iac-devops/cloud-infrastructure-devsecops-baseline/records/prod-v5-20261023/20261024-prod-v5-post-repair-environment-snapshot.zh.md) document the reviewed SSH/database-owner path. They do not establish acceptance of the separate URL/API caller or a complete generation cutover.

- Declare the actual data scope: users-only does not include plans, subscriptions, quotas, policies or accounting. GitOps owns nonsecret desired state; Vault owns secrets; Playbooks owns OS/configuration execution; IaC owns resources and isolated identities.
- Keep source reads consistent and read-only without imposing a blanket write-method denial on a fresh target. Public aliases must reach their actual upstream; ingestion still requires authentication and narrowly permitted paths/methods. An empty HTTP 200 is not delivery evidence.
- Acquire transaction locks before target reads. Bind reviewed online append plans to selected business data, validated identity mapping and schema. Unrelated heartbeats and planner/vacuum statistics must not invalidate them; business/financial conflicts still fail. Verify protected non-scope tables inside the transaction and release locks promptly. Identity exceptions must be explicit and narrowly scoped.
- Trace real samples through Exporter → Vector → Billing → PostgreSQL → Accounts → UI for at least two complete collection periods. Distinguish imported history, positive deltas, idle samples, missing policies and stale observations. Compare the same account across database, API and UI.
- Record deployment replays, at least three real append no-ops and node zero-change replays separately. Zero writes includes no sequence advancement; a previous users-only replay does not validate a larger scope.
- Capture a new populated recovery point after repair. Bind the database dump and full-row fingerprints to one exported MVCC snapshot; preserve and verify schema, ownership, ACLs and sequences in an isolated restore. Encrypt globals, runtime/TLS configuration and container metadata, retain immutable artifact references, and verify an off-host encrypted copy and decryption capability. Credential-free role stubs do not prove production login. Separate component timestamps are not a global atomic snapshot, and database restore timing is not whole-environment RTO.

Raw data, credentials, keys and runtime identities remain controlled. Cloud-disk recovery, shared Vault restore/unseal, payment, MFA/OAuth, unverified nodes and final reconciliation/writer handoff retain their actual NOT_RUN/BLOCKED status. This section grants no additional DNS or cutover authority.

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
