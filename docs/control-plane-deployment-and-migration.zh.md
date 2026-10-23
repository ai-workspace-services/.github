# Selfhost 控制面部署与核心数据迁移

[English](control-plane-deployment-and-migration.md)

状态：实现候选，隔离联调与完整验收待完成。以下是可审查的接口合同，
不代表已发布安装版本或现有环境已提供 API。占位符必须替换为审核过的固定版本。

配套声明见 [GitOps Draft #504](https://github.com/ai-workspace-infra/gitops/pull/504)
（[合同任务 #503](https://github.com/ai-workspace-infra/gitops/issues/503)）。其中模板为示例，
`example_only: true` 不允许执行。

## 三个入口

| 脚本 | 用途 | 接口 |
| --- | --- | --- |
| [`install-control-plane.sh`](../scripts/install-control-plane.sh) | 安装 Accounts、Billing、Console/Portal、Content、PostgreSQL 及声明的运行依赖 | `--config <GitOps 相对 YAML> --gitops-ref <完整 SHA> [--check]` |
| `scripts/migrate-core-data.sh`（Accounts worker 负责） | 通过 Accounts URL 单向迁移身份与完整计费关联数据 | 固定 `MIGRATECTL_BIN` / `MIGRATECTL_SHA256`，源/目标 URL 与两端认证引用；默认预览，隔离验收待完成 |
| [`setup-proxy.sh`](../scripts/setup-proxy.sh) | 为已有控制面接入边缘节点 | 保留当前 `--node` 等接口及节点凭据合同，脚本原样保留 |

旧 `setup-selfhost.sh` 域名打印入口已合并到新安装入口；域名由固定 GitOps 声明提供。
公开 Shell 仅解析参数、验证提交、调度执行。Playbooks 管理主机、证书、部署、备份恢复与迁移执行；
IaC 管理资源、DNS、state、CMDB；GitOps 保存不含秘密值的期望状态；Accounts 管理数据范围、冲突、事务和幂等语义。
公开包装脚本不内嵌 Ansible、SQL 或 Compose 执行。

## 八阶段流程

| 阶段 | 动作 | 通过条件 |
| --- | --- | --- |
| 1 | 准备 GitOps | 环境、资源、域名、密钥引用及源/目标身份明确 |
| 2 | IaC 创建资源 | 计划审核、独立 state、CMDB、主机与 SSH 身份核实 |
| 3 | 创建统一不可变快照 | 五仓全部构建成功，固定源码 SHA、镜像 digest、schema 与迁移校验和 |
| 4 | 安装 Selfhost Control Plane | SSH → Playbook → 固定 GitOps → Doco-CD，核验已加载构件 |
| 5 | 核心数据单向迁移 | 目标可恢复备份、一致性预览无冲突、事务导入与业务指纹通过 |
| 6 | 新环境完整验收 | 含业务数据的隔离恢复、全量适用回归、重复部署、中断恢复和稳定观察 |
| 7 | 准备切换报告 | 明确写入权交接、最终追齐、DNS、观察与恢复计划，等待人工确认 |
| 8 | 经确认切换并正式验收 | 隔离源写入、最终追齐、移交写入权、切流量并观察真实业务 |

全新空环境执行 1–4、6，记录跳过迁移的原因；代际升级执行全部阶段。
已有环境滚动更新采用盘点与备份 → IaC 无破坏增量 → 固定发布收敛 → 仅显式增量迁移 → 边缘节点收敛 → 验证。
重跑不隐式初始化、清库、重导入或创建第二个 writer。源持续服务时记录快照边界；最终追齐属于阶段 8，阶段 7 不自动授权执行。

PostgreSQL 17 验证身份/MFA、完整计费依赖、目标独有数据、冲突回滚、并发互斥、计划过期、重放、中断恢复与 schema 指纹。
历史回归包含证书/公共 SNI、凭据范围、正式入口、Agent 注册、VLESS、OAuth/Webhook、Content，以及
Exporter → Vector → Billing → PostgreSQL → Accounts。
稳定观察至少覆盖两个完整相关采集周期，记录起止时间、数据新鲜度与结果；必测项 FAIL、BLOCKED、NOT_RUN 均不能进入切换。

## 五仓构建与不可变发布

核心五仓为 `accounts`、`billing-service`、`portal`、`content-service`、`postgresql`。
`daily-main-snapshot.yaml` 必须显式选择这五仓，仅运行构建路径。
创建 tag 或派发前，预检各仓 Actions 已启用、目标 workflow 为 active，且实际执行身份可派发；
个人管理员 API 可访问不等于 GitHub App 已获 dispatch 授权。
检查实际 workflow 和 tag 触发条件，确认仅构建，不创建资源、不部署、不迁移、不改 DNS。

已核实 r101：五仓 tag 均在各自源码 SHA 上 CREATED；`accounts`、`billing-service`、`portal`、`content-service`
四仓 CI 与 release manifest 已验证成功，PostgreSQL release 缺失。
PostgreSQL 经 GitHub App 派发再次返回 HTTP 422，原文为 `Actions has been disabled for this repository`；
rerun attempt 2 仍相同，见 [run 39891515095，attempt 2](https://github.com/ai-workspace-infra/platform-ops-toolkit/actions/runs/39891515095)。
同时，个人管理员 API 的 `actions/permissions` 返回 `enabled: true`，workflow 状态为 `active`。
当前观测是 GitHub App dispatch 路径被拒绝，不能据此断言仓库 Actions 仍全局禁用；执行身份配置差异尚待解决。
状态为 **五仓 tag 已创建 / 四仓构建已验证 / PG 派发被拒且 release 缺失**，整体构建未完成、不可部署；
不是仓库筛选错误，也不是 tag 不存在。

执行身份配置解决前，不再重试构建。保留具体 API 错误和各身份设置证据；阻断解除后，源码未变仍使用原 tag/SHA。
只有代码/源码 SHA 变化时才新建不可变 revision，不移动已有 tag。

五仓逐一核对 tag、源码 SHA、成功构建 URL、构件及 digest，缺任一项不得选择部署。
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
`execution.playbooks_sha` 必须是完整提交 SHA。GitOps URL 固定为
`https://github.com/ai-workspace-infra/gitops.git`，Playbooks URL 固定为
`https://github.com/ai-workspace-infra/playbooks.git`，配置不得改源仓库。
包装脚本获取两个精确提交、验证 HEAD 与干净状态、安全读取 YAML，在 Playbooks checkout 调用：

```text
python3 scripts/control_plane/entrypoint.py --config <resolved-path> --gitops-ref <SHA> [--check]
```

`release.snapshot_tag` 标识五仓服务构建，`--gitops-ref` 标识独立的 GitOps 声明提交；
GitOps 无需创建同名服务快照 tag。记录两种身份，不能互相替代。

传给 owner 的 `GITOPS_CHECKOUT`、`PLAYBOOKS_CHECKOUT`、`CONTROL_PLANE_CMDB`、`CONTROL_PLANE_VARS_FILE`
均为绝对路径。owner 须验证已审查声明、目标、固定构件和受保护配置；跨仓 schema 一致性仍是集成门禁，包装脚本 mock 测试不证明该门禁通过。
缺 commit、owner 或前置条件立即失败，不回退分支或 main。`--check` 仅委派预检，不代表业务运行验收。

路径与输入边界：

| 输入 | 解析/归属 |
| --- | --- |
| 公开 `--config` | 相对 GitOps 根目录的已跟踪 YAML；包装脚本向 owner 传已解析的绝对路径 |
| `GITOPS_CHECKOUT`、`PLAYBOOKS_CHECKOUT` | 包装脚本生成的固定 checkout；操作者覆盖仅供离线测试 |
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
两者必须是仓库根目录、上述 canonical origin（HTTPS 或对应的 `git@github.com:` SSH 写法）、匹配 HEAD，且没有修改、未跟踪或忽略文件。
本地固定 checkout 仅供离线测试；正常执行使用临时的固定提交 checkout。

## URL 迁移合同：隔离验收待完成

客户端由 Accounts worker 实现。以下是已接受的计划参数，不声称现有环境已有 API：

已检查的 Accounts 候选为 [Draft #267](https://github.com/ai-workspace-services/accounts/pull/267)，
源码 `a7c7f8743e409f21d49a9b0b55291e788312a865`。该版本将范围内行数据限制为 32 MiB、对象限制为 64 MiB，
恢复粒度为快照/计划 ID，尚无逐分块可恢复获取。已接受的大数据分块、校验和与断点续传要求，
以及 Playbooks 对真实含业务数据备份恢复的验证，仍为集成阻断项。
跟踪：[GitOps #505](https://github.com/ai-workspace-infra/gitops/issues/505)。
提交此包装脚本及固定二进制测试，不代表这些门禁通过、二进制版本发布或现有环境提供 API。

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
