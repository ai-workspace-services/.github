# Selfhost 控制面部署与核心数据迁移

[English](control-plane-deployment-and-migration.md)

状态：实现候选，隔离联调与完整验收待完成。以下是可审查的接口合同，
不代表已发布安装版本或现有环境已提供 API。占位符必须替换为审核过的固定版本。

配套声明合同 [GitOps #504](https://github.com/ai-workspace-infra/gitops/pull/504) 已合并
（[合同任务 #503](https://github.com/ai-workspace-infra/gitops/issues/503)）；
[后续对齐 #506](https://github.com/ai-workspace-infra/gitops/pull/506) 仍待完成。
合同模板为示例，`example_only: true` 不允许执行。

## 代际记录与验收证据索引

本白皮书是组织级部署/迁移流程入口；逐轮运行值、失败与重验结果归档于 Knowledge，不替代 GitOps、IaC、Playbooks 或应用迁移工具的权威配置。V2→V5 证据链、真实回归 case、恢复回执及当前未通过项见 [PROD V4→V5 基线与升级复盘](https://github.com/ai-workspace-services/knowledge/blob/main/content/02-iac-devops/cloud-infrastructure-devsecops-baseline/17-prod-v4-v5-baseline-and-upgrade-retrospective.zh.md)。服务级 Compose/Playbooks 配置来源和脱敏运行回执见 [PROD V5 运行基线](https://github.com/ai-workspace-services/knowledge/blob/main/content/02-iac-devops/cloud-infrastructure-devsecops-baseline/records/prod-v5-20261023/prod-v5-runtime-and-snapshot-baseline-20261023.zh.md)。这些是有时间边界的事实归档；未运行项保持 NOT_RUN/BLOCKED，不从构建或 readiness 推导为业务验收。

## 三个入口

| 脚本 | 用途 | 接口 |
| --- | --- | --- |
| [`install-control-plane.sh`](../scripts/install-control-plane.sh) | 安装 Accounts、Billing、Console/Portal、Content、PostgreSQL 及声明的运行依赖 | `--config <GitOps 相对 YAML> --gitops-ref <完整 SHA> [--check]` |
| [`migrate-core-data.sh`](../scripts/migrate-core-data.sh) | Accounts 迁移客户端：通过 Accounts URL 单向迁移身份与完整计费关联数据 | 固定 `MIGRATECTL_BIN` / `MIGRATECTL_SHA256`，源/目标 URL 与两端认证引用；默认预览，隔离验收待完成 |
| [`setup-proxy.sh`](../scripts/setup-proxy.sh) | 为已有控制面接入边缘节点 | 保留当前 `--node` 等接口及节点凭据合同，脚本原样保留 |

旧 `setup-selfhost.sh` 域名打印入口已合并到新安装入口；域名由固定 GitOps 声明提供。
公开 Shell 仅解析参数、验证提交、调度执行。Playbooks 管理主机、证书、部署、备份恢复与迁移执行；
IaC 管理资源、DNS、state、CMDB；GitOps 保存不含秘密值的期望状态；Accounts 管理数据范围、冲突、事务和幂等语义。
公开包装脚本不内嵌 Ansible、SQL 或 Compose 执行。

## 八阶段流程

| 阶段 | 动作 | 通过条件 |
| --- | --- | --- |
| 1 | 准备 GitOps | 审核环境/资源/域名声明、密钥引用、源与目标身份及固定执行版本 |
| 2 | IaC 创建资源 | 计划审核、独立 state、生成 CMDB、主机与 SSH 身份核实；不执行未审核替换 |
| 3 | 创建统一不可变五仓快照 | 五仓源码 SHA、构建来源、构件 digest、schema 与迁移校验和均可验证；使用 GitHub Actions 或已批准的本地构建路径 |
| 4 | 通过 SSH 安装控制面 | SSH → Playbook → 固定 GitOps → Doco-CD；核验目标实际加载的构件与配置 |
| 5 | 使用 `migratectl` 迁移核心数据 | 目标可恢复备份、无冲突预览、审核计划、事务性单向导入与业务指纹 |
| 6 | 对候选环境执行完整回归 | 含业务数据的隔离恢复、全部适用回归、幂等重跑、中断恢复和稳定观察 |
| 7 | 准备 DNS 切换，不改变流量 | 审核精确记录/TTL、写入权交接、最终追齐步骤、观察与回滚计划；仍须等待人工明确确认 |
| 8 | 经明确确认后切换并验收 | 记录授权人及确认范围；隔离源写入、最终追齐、移交写入权、修改 DNS、回读并观察真实业务 |

全新空环境执行 1–4、6，记录跳过迁移的原因；代际升级执行全部阶段。
已有环境滚动更新采用盘点与备份 → IaC 无破坏增量 → 固定发布收敛 → 仅显式增量迁移 → 边缘节点收敛 → 验证。
重跑不隐式初始化、清库、重导入或创建第二个 writer。源持续服务时记录快照边界；最终追齐属于阶段 8。

### 部署与迁移的幂等重跑门禁

首轮完整部署成功后，以完全相同的不可变 GitOps/Playbooks/installer ref、镜像 digest、目标和非敏感配置，至少再完整运行三次。每次记录独立 run_id、Asia/Shanghai 起止、退出码、期望配置摘要、实际镜像/容器身份、重启计数、数据库身份及 schema checkpoint。要求无配置漂移、无非预期容器替换或重启、无新增数据库副作用；只有本地 syntax-check、`--check` 或健康探针不能替代真实重复部署。

迁移先做源端一致性只读快照、目标可恢复备份和字段级预览；应用前按精确计划摘要复核源/目标身份与基线。首次写入后每次重放都重新生成只读预览，并对空差异计划执行安全 no-op 校验；至少重复三次。相同身份/内容必须无差异，身份冲突或源/目标基线变化即停止，不覆盖目标独有事实，也不在源端写入。每轮均绑定 `migratectl` 版本与二进制 digest、schema/migration checkpoint、数据校验摘要、退出码和 run_id；应用 exit 0 不代表全业务验收通过。

构建成功、部署成功、数据迁移、备份恢复、真实业务验收和流量/写入切换分别作为独立状态记录。已部署服务可保持运行与零流量，但必须证明无不受控写入者；是否停服由实际迁移合同和目标运行状态决定，不沿用通用停服假设。
阶段 7 仅准备并审核 DNS 值，不修改 DNS 或授权写入权变化。阶段 8 必须由有权人员针对明确的环境、源、目标、数据操作及 DNS 记录作出并留存明确确认；沉默、回归通过或完成阶段 7 都不构成确认。

PostgreSQL 17 验证身份/MFA、完整计费依赖、目标独有数据、冲突回滚、并发互斥、计划过期、重放、中断恢复与 schema 指纹。
历史回归包含证书/公共 SNI、凭据范围、正式入口、Agent 注册、VLESS、OAuth/Webhook、Content，以及
Exporter → Vector → Billing → PostgreSQL → Accounts。
稳定观察至少覆盖两个完整相关采集周期，记录起止时间、数据新鲜度与结果；必测项 FAIL、BLOCKED、NOT_RUN 均不能进入切换。

## 五仓构建与不可变发布

核心五仓为 `accounts`、`billing-service`、`portal`、`content-service`、`postgresql`。
从五仓各自精确、已记录的源码 SHA 创建一个统一快照。可由 `daily-main-snapshot.yaml` 等 GitHub Actions workflow 执行纯构建路径；GitHub Actions 不是构建的强制依赖。
经发布负责人批准后，也可使用下述本地不可变构建路径。两条路径都只能构建，不创建资源、不部署、不迁移、不改 DNS；执行前检查实际 workflow 或本地构建规程。

已核实 r101：五仓 tag 均在各自源码 SHA 上 CREATED；`accounts`、`billing-service`、`portal`、`content-service`
四仓 CI 与 release manifest 已验证成功，PostgreSQL release 缺失。
PostgreSQL 经 GitHub App 派发再次返回 HTTP 422，原文为 `Actions has been disabled for this repository`；
rerun attempt 2 仍相同，见 [run 39891515095，attempt 2](https://github.com/ai-workspace-infra/platform-ops-toolkit/actions/runs/39891515095)。
同时，个人管理员 API 的 `actions/permissions` 返回 `enabled: true`，workflow 状态为 `active`。
当前观测是 GitHub App dispatch 路径被拒绝，不能据此断言仓库 Actions 仍全局禁用；执行身份配置差异尚待解决。
这一历史 r101 快照状态仍为 **五仓 tag 已创建 / 四仓构建已验证 / PostgreSQL 派发被拒且 release 缺失**，因此构建不完整、不可部署。
这不是仓库筛选错误，也不是 tag 不存在。

HTTP 422 记录描述的是当时 GitHub App 的派发路径，不要求在使用获批的本地构建前必须先修好该身份配置。
保留具体 API 错误和各身份设置证据作为历史事实。若以本地构建补齐缺失构件，必须使用原记录源码 SHA 和不可变快照身份，并产生下述等效来源及验证证据；不得追溯性地改写 r101 当时的结果或宣称其当时已可部署。
不得移动、替换 tag，也不得将已有 tag 复用于不同源码。

### 已批准的本地不可变构建路径

发布负责人针对指定快照批准后，可采用本路径替代 Actions，同时保留不可变源码与构件控制：

1. 每个仓库均检出记录中的完整 commit SHA；确认 tracked/untracked 工作区干净，并记录仓库、快照 tag 与 SHA。
2. 按仓库已审核的构建和验证规程执行，不修改构建输入、不读取浮动分支内容；逐仓记录命令、工具链版本和结果。
3. 在快照 manifest 中记录构件名称、大小、SHA-256、容器镜像 digest、schema 身份和迁移校验和；将 manifest 与构建日志纳入发布证据。
4. 将输出发布或保存在批准的不可变构件存储中，并回读每个构件、按 manifest 校验 digest 后再选用。本机文件副本、可变 tag 或仅仅编译成功，都不代表已发布或运行验收。
5. 仅当五仓源码与构件证据完整且匹配时，快照才可标记为可部署。复用 CI 构件时，也必须证明其源码 SHA 和 digest 与同一快照一致。

若获批规程不能产出等效且可独立复核的来源证明和不可变构件，快照仍为不完整。有效本地构建无需启用 GitHub Actions、workflow dispatch 或重试；如使用 Actions，其结果仍须准确标注对应 workflow run。

五仓逐一核对 tag、源码 SHA、构建来源与结果、构件及 digest，缺任一项不得选择部署。
tag 或 registry 构件存在不能证明运行健康。发布使用审核后的固定构件，不从浮动分支重建；
稳定版本永久不可变，正式发布说明提供固定脚本 URL 和匹配的 GitOps/Playbooks SHA，不编造发布版本。

## 安装合同

执行端先具备 Git、Python 3、PyYAML 和固定 Playbooks owner 的依赖。
缺 Python/PyYAML 明确失败；包装脚本不安装软件包。
操作者提供 IaC 生成的 CMDB 和受保护 vars 文件，放在源码 checkout 外。
`CONTROL_PLANE_VARS_FILE` 只保存非敏感运行策略和 Vault 引用，不存明文凭据。
Playbooks owner 在执行内部解析 Vault 凭据；包装脚本不解析或复制秘密值，不传命令行、不进入公开回执。

所选 owner 要求 Python 3.11+、Ansible 及其文档规定的 collections；实际执行还要求 Vault CLI 和已签发的短期 Vault 身份。
策略文件须由操作者拥有，权限为 0600 或 0400；根 `control_plane_runtime` 中包含
`vault_addr`、`vault_token_env: VAULT_TOKEN` 和 owner 要求的完整 `secret_refs` 映射。
`vault_addr` 为显式 HTTPS origin，单独继承 `VAULT_ADDR` 不能替代策略。
`--check` 检查本地声明/策略，不登录 Vault，不证明凭据、SSH 或目标可用。

```bash
export ENTRYPOINT_RELEASE='<审核过的不可变 .github release 或完整 SHA>'
export GITOPS_SHA='<审核过的40位 GitOps commit SHA>'
export CONTROL_PLANE_CMDB='/secure/run/cmdb.json'
export CONTROL_PLANE_VARS_FILE='/secure/run/vars.yaml'

curl -fsSL "https://raw.githubusercontent.com/ai-workspace-services/.github/${ENTRYPOINT_RELEASE}/scripts/install-control-plane.sh" \
  -o /tmp/install-control-plane.sh
# 阅读脚本并核对发布 checksum 后执行。
bash /tmp/install-control-plane.sh \
  --config '<path/to/control-plane.yaml>' --gitops-ref "$GITOPS_SHA" --check
# owner 联调验收及相应部署授权完成后：
bash /tmp/install-control-plane.sh \
  --config '<path/to/control-plane.yaml>' --gitops-ref "$GITOPS_SHA"
```

`--config` 必须是该固定 GitOps commit 中已跟踪的相对 YAML 文件，不能绝对路径或越界读取。
`execution.playbooks_sha` 必须是完整提交 SHA。实际执行还要求
`release.billing.source_sha`（小写40位提交 SHA）及
`release.billing.schema_file: sql/billing-service-schema.sql`。GitOps URL 固定为
`https://github.com/ai-workspace-infra/gitops.git`，Playbooks URL 固定为
`https://github.com/ai-workspace-infra/playbooks.git`，Billing URL 固定为
`https://github.com/ai-workspace-services/billing-service.git`，配置不得改源仓库。
包装脚本安全读取 YAML，自动获取三个精确提交：GitOps 的 `--gitops-ref`、Playbooks 的
`execution.playbooks_sha` 和 Billing 的 `release.billing.source_sha`。
验证 HEAD、canonical origin 与干净状态后，在 Playbooks checkout 调用：

```text
python3 scripts/control_plane/entrypoint.py --config <resolved-path> --gitops-ref <SHA> [--check]
```

`release.snapshot_tag` 标识五仓服务构建，`--gitops-ref` 标识独立的 GitOps 声明提交；
GitOps 无需创建同名服务快照 tag。记录两种身份，不能互相替代。

传给 owner 的 `GITOPS_CHECKOUT`、`PLAYBOOKS_CHECKOUT`、`BILLING_CHECKOUT`、
`CONTROL_PLANE_CMDB`、`CONTROL_PLANE_VARS_FILE` 均为绝对路径，无新增公开 flags 或秘密输入。
owner 的 `billing_artifact` 按 `release.accounts.billing_schema_sha256` 核对已跟踪 SQL 字节，
由 owner 在首个空库的业务授权/应用启动前执行审核过的 Billing DDL；包装脚本不执行 SQL。
旧结构性 `--check` fixture 可省略 `release.billing`、仅用两个 checkout；实际 owner 执行缺少该声明或构件会失败。
owner 须验证已审查声明、目标、固定构件和受保护配置；跨仓 schema 一致性仍是集成门禁，包装脚本 mock 测试不证明该门禁通过。
缺 commit、owner 或前置条件立即失败，不回退分支或 main。`--check` 仅委派预检，不代表业务运行验收。

路径与输入边界：

| 输入 | 解析/归属 |
| --- | --- |
| 公开 `--config` | 相对 GitOps 根目录的已跟踪 YAML；包装脚本向 owner 传已解析的绝对路径 |
| `GITOPS_CHECKOUT`、`PLAYBOOKS_CHECKOUT`、`BILLING_CHECKOUT` | 包装脚本生成的固定 checkout；Billing 取 `release.billing.source_sha`；操作者覆盖仅供离线测试 |
| `CONTROL_PLANE_CMDB`、`CONTROL_PLANE_VARS_FILE` | 必填外部文件，相对路径在切换工作目录前按调用目录解析 |
| `AI_WORKSPACE_CMDB_JSON`、`CMDB_FILE` | owner 调用 inventory 前，从 `CONTROL_PLANE_CMDB` 同时设置两者 |
| `release.doco_cd.target` / `storage_target` | 选择 GitOps 根目录的 `.doco-cd.<selection>.yml`；`working_dir` 相对 GitOps 根目录，Compose/env 文件相对该工作目录 |

公开 GitOps schema 禁止 `target.cmdb_file` 和顶层 `vars_files`；即使更宽的 owner parser 接受，也应使用外部操作者输入。
部署声明的 `source.host` / `source.generation` 仅为审计元数据，不是迁移端点。
独立的 `kind: accounts-migration` 示例不能交给 `install-control-plane.sh`；URL 迁移使用下方 flags，本文不声称已有自动迁移 YAML 消费器。
两个 GitOps 示例均刻意不可执行，须另行准备审核过的执行声明。

CMDB 还须声明 `storage`（或 `host_vars.control_plane_storage`）：`profile` 选择 `root` 或 `dedicated`，并给出 `data_path`；
独立盘再声明 `mount_path` / `device_path`。固定 PostgreSQL bind 必须匹配 `data_path`；根盘模式不要求另加数据盘，实际存储由 owner 执行时核验。

离线测试可同时设置 `CONTROL_PLANE_OFFLINE_TEST=1`、`GITOPS_CHECKOUT`、`PLAYBOOKS_CHECKOUT`，并必须传 `--check`。
声明 `release.billing` 时还必须提供 `BILLING_CHECKOUT`；离线模式不会联网补齐缺失 checkout。
所有 checkout 必须是仓库根目录、精确匹配 HEAD，且没有修改、未跟踪或忽略文件。
GitOps/Playbooks 接受上述 canonical HTTPS origin 或对应的 `git@github.com:` SSH 写法；
Billing 与 owner 保持一致，只接受精确 canonical HTTPS origin。没有对应声明的 Billing 覆盖也会被拒绝。
本地固定 checkout 仅供离线测试；正常执行使用三个临时的固定提交 checkout。

## URL 迁移合同：隔离验收待完成

以下为 Accounts 迁移客户端接口。URL/API 模式仍待隔离验收，不代表现有环境已有 API。

已检查的 Accounts 候选为 [Draft #267](https://github.com/ai-workspace-services/accounts/pull/267)，
源码 `c5e3bae3bea1d9b71ee2a579e4da8657fc192bc8`。实现提交
`84df2658cd70da0cdfd7e38d559f688705d4c218` 已解决原 32 MiB 总行数据限制：
加密不可变分块具备校验和、持久暂存和可恢复获取，preview/apply 通过 SQL TEMP 表消费页面，不再构造完整行数据 map。
已有隔离 PostgreSQL 17 证据表明，约 44 MiB preview/apply 和中断获取后的恢复通过。
64 MiB 仍是元数据对象限制，不是业务数据总量限制；仍保留精简的逐行 digest 元数据，不承诺无限数据下常量内存。
`--transfer-only` 仅暂存/核验页面，不写业务数据；默认预览不变。缺失页面下载最多尝试两次，变更请求不自动重试。

[GitOps #505](https://github.com/ai-workspace-infra/gitops/issues/505) 继续跟踪实际含业务数据的备份恢复门禁及完整跨仓运行验收；
分块/续传代码不再是未实现缺口。[Playbooks #729](https://github.com/ai-workspace-infra/playbooks/pull/729)
已合并可选 listener 和 Billing/bootstrap 就绪检查等 owner 工作。
代码与隔离回归通过，不代表全新运行部署、二进制版本发布或现有环境提供可用迁移 API。

```bash
export MIGRATECTL_BIN='/secure/tools/migratectl'
export MIGRATECTL_SHA256='<已核验发布清单中的64位 SHA-256>'
bash scripts/migrate-core-data.sh \
  --source-url https://accounts-source.example.com \
  --source-token-env SOURCE_MIGRATION_TOKEN \
  --target-url https://accounts-target.example.com \
  --target-token-env TARGET_MIGRATION_TOKEN
# 原参数基础上应用已审查预览：
# 追加 --apply --plan-id '<id>' --plan-sha256 '<sha256>'
```

审核过的 Accounts 二进制须单独准备。`MIGRATECTL_BIN` 必须是普通可执行文件的绝对路径，不能符号链接，不能允许组/其他用户写入。
`MIGRATECTL_SHA256` 来自独立核验的发布证据，不能只对不可信本地下载计算 hash 后当作可信来源。
Python 3 包装脚本校验该 digest 后执行 `transfer-api`；不安装、不下载二进制、不从 `PATH` 发现客户端。
已核对 Accounts 所属脚本中的固定二进制合同；API 隔离验收仍待完成。

Accounts `e829428800617900c51c779e4462b6236c8c017b` 的生产器构建
`migratectl-linux-amd64`、`migratectl-linux-arm64`、`migratectl-darwin-amd64`、`migratectl-darwin-arm64`，
并生成 `SHA256SUMS` 和 `release-manifest.json`。Linux 为支持的主机迁移 runner，Darwin 资产用于本地工具，不宣称 Windows 支持。
完整合同见固定源码的 [Accounts 发布资产说明](https://github.com/ai-workspace-services/accounts/blob/c5e3bae3bea1d9b71ee2a579e4da8657fc192bc8/docs/migrations/migratectl-release-assets.md)：

1. 核对不可变 release tag 与选定的目标 Accounts 精确源码 SHA。生产器要求干净 checkout 的 HEAD 等于完整 `GITHUB_SHA`；
   manifest 的 `commit` 必须等于该预期源码 SHA，不能因文件名匹配而接受其他源码。
2. 核对 manifest 的 `schema: 1`、`repository`、`tag`、`commit`。`files` 为文件名列表，
   `artifacts` 逐项提供精确 `name`、`sha256`、`size_bytes`。
3. 先按可信 manifest 对应条目校验 `SHA256SUMS` 自身，再将选定平台二进制同时与 manifest 条目和 `SHA256SUMS` 核对，包括实际字节数。
   `SHA256SUMS` 覆盖 payload，不包含它自身的 hash；两个校验文件均不提供自身的 checksum。
4. 安装为前述受保护普通可执行文件，再设置 `MIGRATECTL_BIN` 和 manifest 记录的预期资产 `MIGRATECTL_SHA256`。
   生产器实现提交不能替代所选 release 的源码 SHA 或资产 digest；旧 release 缺少这些资产时不能静默接受或修改旧版本。

四平台本地构建、checksum 及原生 help 已通过，但这些打包测试未发布 release。
实际运维前仍须核对真实发布资产，并分别记录固定 Accounts 和 Playbooks 提交。

每端可用 `--source-auth-kv` / `--target-auth-kv` 替换对应 token-env；同端两种方式互斥。
参数只传引用名称，绝不传 Token 值。迁移凭据短期、限定对端/用途，独立于共享服务 Token。
`/api/migrations/v1` 为新增显式启用的 API 合同：源端只读一致性快照、清单、数据流；目标端预览、应用、查询进度。
目标主动获取审核过的源数据；受保护分块暂存与校验和支持幂等恢复。
计划绑定源快照、目标基线、工具版本、数据范围和 schema；基线变化、过期、身份或财务冲突、非法对端、重定向、同库、篡改及无法安全合并的目标独有活动必须阻断。

范围包括稳定身份、邮箱、密码 hash、MFA/恢复状态、OAuth、XConnect 身份、团队、订阅、额度、用量、账单、付款、退款和审计依赖。
TOTP 按受保护格式迁移并验证目标可用性；旧 session、临时验证码、迁移访问凭据不复制。
迁移不调用真实支付、退款或通知服务。以机器可读表/字段合同和内容指纹验收，不能只核对行数；数据与回执留在受控存储。

现有 V4 尚无该 API。V4→V5 首次兼容继续使用单独审核的 SSH/数据库 owner 路径；
URL 模式遇到旧端点明确报不支持，不隐式回退，V4 无需为首次迁移回补 API。
依赖顺序为 Accounts → Playbooks → GitOps → 公开入口；owner 固定提交、声明及隔离端到端验收集成前保持 Draft。

## 历史文档

下列均为仓内已有文件，保留原日期、假设与历史证据；统一入口以本指南为准：

- [PROD V2 部署](prod-v2-deployment.md)
- [2026-10-16 升级切换](prod-v2-upgrade-cutover-20261016.md)
- [2026-10-18 升级恢复](prod-v2-upgrade-recovery-20261018.md)
- [V3 catalog 回归](E2E/p0f-v3-catalog-upgrade-20261019.md)
- [V4 固定版本节点部署](prod-v4-pinned-node-deployment-tldr.md)
- [历史 Selfhost 实施任务书](selfhost-orchestrator-one-shell-uat-prod.md)

执行编号、真实端点绑定、主机/库身份、备份恢复、迁移计划/结果与回归证据保存在受控记录中；公开文档仅使用通用参数示例。
