# selfhost-orchestrator：UAT / PROD one-shell 整理与实施任务书

> 2026-10-16。本文对应现有 selfhost-orchestrator.yml 的部署链路，作为 Antigravity Code Agent 的实施输入。
> one-shell 入口已在 IaC 与 Playbooks 仓库提交；本次提交只交付可审查的脚本、参数合同和回执逻辑，不触发部署或流水线。目标环境运行仍需按本文件完成 preflight、人工审批和真实验收。

> 历史任务书：保留 2026-10-16 的阶段、数据与接口背景。当前统一入口、八阶段流程及候选状态见[控制面部署与迁移指南](control-plane-deployment-and-migration.zh.md)。下文历史分阶段脚本不作为新入口可用性证明。

## 1. 前提条件

开始 Quickstart 前必须满足：

- 已获得对应环境的云账号、Vault/OIDC、GitHub、SSH/Ansible 和目标数据库权限。
- 已核对 workflow、IaC、GitOps、Playbooks、Accounts、Portal、Billing 和 Agent 仓库的 remote、固定 commit、工作树和 AGENTS.md。
- 已准备对应环境的 GitOps manifest、IaC receipt、CMDB/inventory、固定镜像或边缘制品 checksum，以及受保护 vars 文件。
- 环境、deployment ID、Console/Accounts/Billing/PostgreSQL/节点域名全部由调用者提供；脚本不从环境名推导域名。
- 源数据库和目标数据库身份已明确；单向迁移只允许从 Selfhost 源到目标，禁止 Serverless 源、反向写入和旧 session 迁移。
- 已确认目标数据库是新库或允许幂等增量升级；非空业务库禁止重新初始化、清库或覆盖。
- 已确认旧 PROD 服务、旧 PROD DNS、旧 Terraform state 和旧资源不在本次目标内。
- 已确认各节点实际架构和制品可用；允许 AMD64/ARM64 混合，以稳定资源规格、持续性能和网络质量验收。
- 已确认控制面 80/443、节点实际业务端口、SSH 和监控来源的防火墙范围；PostgreSQL 5432 不公网开放。
- 已确认本阶段不触发 GitHub Actions；手工部署和真实验收完成后，才允许运行 selfhost-orchestrator 对齐。

敏感值只能通过 Vault、受保护 vars 或运行时环境传递。不得把 token、密码、私钥、完整 proxy UUID、DSN 或订阅导入 receipt 写入仓库、命令行参数或公开 artifact。

### CLI 和身份预检

执行者本机或受控 runner 至少需要以下工具。版本以对应仓库锁定的执行环境为准，不要在目标主机临时安装最新版来绕过版本约束：

~~~sh
set -e
for tool in git gh terraform ansible-playbook gcloud aws curl jq; do
  command -v "$tool" >/dev/null || { echo "missing CLI: $tool" >&2; exit 1; }
done

git --version
gh --version
terraform version
ansible-playbook --version
gcloud version
aws --version
jq --version

# GitHub 只读身份；不得把 token 作为命令行参数
gh auth status

# GCP 身份和当前 project；project 必须由环境参数或 vars 明确提供
gcloud auth list --filter=status:ACTIVE
gcloud config get-value project
gcloud projects describe "$GCP_PROJECT_ID" --format='value(projectId)'

# AWS 身份、账号和 region；必须与 manifest 的 provider/account 一致
aws sts get-caller-identity --output json | jq '{Account,Arn,UserId}'
aws configure get region

# Terraform 只读初始化/校验由 provision.sh 在正确 state/profile 中执行
terraform version
ansible-playbook --syntax-check -i "$INVENTORY" "$PLAYBOOK"
~~~

如果任一身份、project、account、region 或 Git ref 与 manifest 不一致，preflight 立即停止。gcloud、AWS、Vault、GitHub 会话不能混用 UAT 和 PROD；不在 shell 历史中写入云密钥、Vault token、数据库 DSN 或管理员 cookie。

### 账号清单

账号清单由 Selfhost 源 account 数据库只读导出生成，使用受保护的 CSV/YAML 文件传给 migrate-users.sh。下表是字段合同，文件本身不提交仓库：

| 序号 | email（幂等 key） | username | account UUID | proxy UUID | active | MFA | 权益分组 | 订阅类型 | 有效期 | 月额度 | 年额度 | 迁移状态 |
| ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- | ---: | ---: | --- |
| 1..N | 脱敏或受保护值 | 脱敏或受保护值 | 受保护值 | 受保护值 | true/false | enabled/disabled | free/plus/team/root | month/year/none | ISO 日期或空 | GiB | GiB | preview/applied/verified |

当前历史验收基线汇总：

| 项目 | 数量/规则 |
| --- | ---: |
| 源账号总数 | 30 |
| Free | 19 |
| Plus | 10 |
| Team | 0 |
| Root | 1，管理用途，不进入代理池 |
| 订阅记录 | 10 |
| 年付订阅 | 7 |
| 月付订阅 | 3 |
| Free 月额度 | 3 GiB，自然月耗尽暂停，下月恢复 |
| Plus 月额度 | 20 GiB |
| Plus 年额度 | 240 GiB |

迁移前输出仅允许包含数量、分组计数、冲突数和 checksum；迁移后比较 email 归一化映射、账号/proxy UUID、密码 hash、MFA、active 和订阅有效期，完整值只留在权限受控的 receipt。历史数量是验收参考，不是脚本硬编码；执行时按当前源库和有效权益报告差异。

## 2. Quickstart

### Self-hosted control plane 与边缘节点接入

控制面入口现统一为 `install-control-plane.sh`；旧域名打印脚本已合并移除。
域名在审核过的固定 GitOps YAML 中显式声明，IaC 管理 DNS，PostgreSQL 保持隧道访问。
以下是候选入口的预检合同，隔离联调验收待完成：

~~~sh
export CONTROL_PLANE_CMDB='/secure/run/cmdb.json'
export CONTROL_PLANE_VARS_FILE='/secure/run/vars.yaml'
bash scripts/install-control-plane.sh \
  --config '<GitOps相对路径.yaml>' --gitops-ref '<已审核40位commit>' --check
~~~

包装脚本安全读取 `execution.playbooks_sha` 并调用该固定 Playbooks owner；
缺 Python/PyYAML 明确失败，不安装依赖，不回退 main。完整参数与正式发布要求见统一指南。
边缘节点接入使用既有入口：

~~~sh
curl -fsSL 'https://raw.githubusercontent.com/ai-workspace-services/.github/<release-or-SHA>/scripts/setup-proxy.sh' \
  | bash -s -- --node xhttp.example.com
~~~

生产或受控环境必须将上述 URL 固定到已审核 commit/tag，并通过 Vault/受保护运行时注入节点凭据；不要把真实 Token 放入命令行或 Shell 历史。

以下是执行顺序和最小参数集。脚本统一实现 --help、参数校验、阶段边界和幂等回执；执行前仍必须使用目标环境自己的 manifest、inventory、受保护 vars 和固定 release。

先准备每个环境自己的参数文件。环境、部署 ID、所有域名、manifest、inventory 和 vars 都是输入，不从 uat/prod 拼接域名：

~~~sh
export DEPLOY_ENV=uat
export DEPLOYMENT_ID=selfhost-uat
export CONSOLE_DOMAIN="由环境配置提供"
export ACCOUNTS_DOMAIN="由环境配置提供"
export BILLING_DOMAIN="由环境配置提供"
export POSTGRES_DOMAIN="由环境配置提供"
export SOURCE_ACCOUNTS_DOMAIN="仅迁移时提供"
export MANIFEST="/secure/$DEPLOYMENT_ID/gitops-manifest.json"
export INVENTORY="/secure/$DEPLOYMENT_ID/cmdb/inventory.ini"
export VARS_FILE="/secure/$DEPLOYMENT_ID/vars.yml"
~~~

首次部署按以下顺序执行。每一步成功后保存 receipt，再继续下一步：

~~~sh
# 1. 创建/导入云资源，输出权威 CMDB 和 inventory
bash provision.sh --env "$DEPLOY_ENV" --deployment-id "$DEPLOYMENT_ID" --manifest "$MANIFEST" --vars-file "$VARS_FILE" --phase plan
bash provision.sh --env "$DEPLOY_ENV" --deployment-id "$DEPLOYMENT_ID" --manifest "$MANIFEST" --vars-file "$VARS_FILE" --phase apply

# 2. 控制面：Console、Accounts、Billing、全新 PostgreSQL、Doco-CD
bash control.sh --env "$DEPLOY_ENV" --deployment-id "$DEPLOYMENT_ID" --console-domain "$CONSOLE_DOMAIN" --accounts-domain "$ACCOUNTS_DOMAIN" --billing-domain "$BILLING_DOMAIN" --postgres-domain "$POSTGRES_DOMAIN" --manifest "$MANIFEST" --inventory "$INVENTORY" --vars-file "$VARS_FILE" --phase bootstrap
bash control.sh --env "$DEPLOY_ENV" --deployment-id "$DEPLOYMENT_ID" --console-domain "$CONSOLE_DOMAIN" --accounts-domain "$ACCOUNTS_DOMAIN" --billing-domain "$BILLING_DOMAIN" --postgres-domain "$POSTGRES_DOMAIN" --manifest "$MANIFEST" --inventory "$INVENTORY" --vars-file "$VARS_FILE" --phase initialize

# 3. 单向迁移账号，再导入订阅用户
bash migrate-users.sh --env "$DEPLOY_ENV" --deployment-id "$DEPLOYMENT_ID" --source-accounts-domain "$SOURCE_ACCOUNTS_DOMAIN" --accounts-domain "$ACCOUNTS_DOMAIN" --manifest "$MANIFEST" --inventory "$INVENTORY" --vars-file "$VARS_FILE" --phase preview
bash migrate-users.sh --env "$DEPLOY_ENV" --deployment-id "$DEPLOYMENT_ID" --source-accounts-domain "$SOURCE_ACCOUNTS_DOMAIN" --accounts-domain "$ACCOUNTS_DOMAIN" --manifest "$MANIFEST" --inventory "$INVENTORY" --vars-file "$VARS_FILE" --phase apply
bash import-subscriptions.sh --env "$DEPLOY_ENV" --deployment-id "$DEPLOYMENT_ID" --accounts-domain "$ACCOUNTS_DOMAIN" --csv "$SUBSCRIPTIONS_CSV" --manifest "$MANIFEST" --vars-file "$VARS_FILE" --phase preview
bash import-subscriptions.sh --env "$DEPLOY_ENV" --deployment-id "$DEPLOYMENT_ID" --accounts-domain "$ACCOUNTS_DOMAIN" --csv "$SUBSCRIPTIONS_CSV" --manifest "$MANIFEST" --vars-file "$VARS_FILE" --phase apply

# 4. 控制面激活和三个区域节点
bash control.sh --env "$DEPLOY_ENV" --deployment-id "$DEPLOYMENT_ID" --console-domain "$CONSOLE_DOMAIN" --accounts-domain "$ACCOUNTS_DOMAIN" --billing-domain "$BILLING_DOMAIN" --postgres-domain "$POSTGRES_DOMAIN" --manifest "$MANIFEST" --inventory "$INVENTORY" --vars-file "$VARS_FILE" --phase activate
bash free.sh --env "$DEPLOY_ENV" --deployment-id "$DEPLOYMENT_ID" --region jp --node-id "$FREE_NODE_ID" --node-domain "$FREE_NODE_DOMAIN" --accounts-domain "$ACCOUNTS_DOMAIN" --billing-domain "$BILLING_DOMAIN" --manifest "$MANIFEST" --inventory "$INVENTORY" --vars-file "$VARS_FILE" --phase deploy
bash plus.sh --env "$DEPLOY_ENV" --deployment-id "$DEPLOYMENT_ID" --region jp --node-id "$PLUS_NODE_ID" --node-domain "$PLUS_NODE_DOMAIN" --accounts-domain "$ACCOUNTS_DOMAIN" --billing-domain "$BILLING_DOMAIN" --manifest "$MANIFEST" --inventory "$INVENTORY" --vars-file "$VARS_FILE" --phase deploy
bash team.sh --env "$DEPLOY_ENV" --deployment-id "$DEPLOYMENT_ID" --region jp --node-id "$TEAM_NODE_ID" --node-domain "$TEAM_NODE_DOMAIN" --accounts-domain "$ACCOUNTS_DOMAIN" --billing-domain "$BILLING_DOMAIN" --manifest "$MANIFEST" --inventory "$INVENTORY" --vars-file "$VARS_FILE" --phase deploy

# 5. 验收；通过后才允许 selfhost-orchestrator 对齐
bash control.sh --env "$DEPLOY_ENV" --deployment-id "$DEPLOYMENT_ID" --console-domain "$CONSOLE_DOMAIN" --accounts-domain "$ACCOUNTS_DOMAIN" --billing-domain "$BILLING_DOMAIN" --postgres-domain "$POSTGRES_DOMAIN" --manifest "$MANIFEST" --inventory "$INVENTORY" --vars-file "$VARS_FILE" --phase verify
~~~

UAT 使用 DEPLOY_ENV=uat 和 UAT 自己的域名/manifest；PROD 使用 DEPLOY_ENV=prod、独立 DEPLOYMENT_ID 和 PROD V2 自己的域名/manifest。新增区域只替换 region、node-id、node-domain 和对应 manifest，不复制脚本。

### 最后运行 selfhost-orchestrator

手工部署和真实验收完成后，才运行 /Users/shenlan/workspaces/ai-workspace-infra/platform-ops-toolkit/.github/workflows/selfhost-orchestrator.yml 对齐。先 operation=plan 且 dns_mode=none，核对无重建、无数据库初始化、无重复迁移和无旧 PROD 变更；再使用相同 deployment_id、域名、manifest、固定 release 和 provider/account 执行部署。selfhost-orchestrator 必须读取 IaC receipt/CMDB，不能自行猜主机或生成第二份拓扑。

## 3. 目标和统一原则

把 selfhost-orchestrator.yml 中的部署阶段整理成可单独重跑的 one-shell。UAT 与 PROD 使用同一实现、不同 GitOps 环境 profile，不复制两套逻辑。工作流和本地 SSH/Playbook 调用同一组 owner 脚本，手工完成验收后再让 workflow 收敛到相同结果。

one-shell 指“一个脚本完成一个有边界的阶段”，不代表把 IaC、初始化、迁移、订阅导入全部隐藏在一次部署中。

- 云资源、网络、防火墙、IP、DNS、Terraform state：iac_modules owner。
- 主机、服务、数据库迁移、订阅管理 API 调用：playbooks owner。
- 拓扑、环境、区域、资源类型、非敏感运行配置、release manifest：gitops owner。
- 参数校验、阶段排序、授权、固定 ref 调用和证据放行：platform-ops-toolkit owner。
- 不在 Toolkit 新增 SSH、Ansible、Terraform 或数据库执行副本；遵守各仓库 AGENTS.md。
- 旧 PROD 与旧 DNS 保持原状；PROD profile 必须显式选择 selfhost-prod-v2，不能自动落入旧 prod。
- 控制面复用已存在且核验过的 V2；非空数据库不重新初始化。
- 不部署 APISIX；三类节点均为实际节点域名的 Caddy → Xray Unix socket 直连。
- 允许 AMD64/ARM64 混合，按实际架构选制品，以资源规格、持续性能、网络质量和稳定性验收。
- 阶段间不隐式递归调用，尤其 deploy 不隐式 migrate 或 import-subscriptions。

## 4. 先读仓库与基线

工作流实际路径：
/Users/shenlan/workspaces/ai-workspace-infra/platform-ops-toolkit/.github/workflows/selfhost-orchestrator.yml

历史实测归档：
/Users/shenlan/workspaces/ai-workspace-service/.github/docs/prod-v2-deployment.md

多云拓扑实施任务书：
/Users/shenlan/workspaces/ai-workspace-service/.github/docs/prod-v2-multicloud-antigravity-prompt.md

| 仓库 | 本地目录 |
| --- | --- |
| ai-workspace-infra/platform-ops-toolkit | /Users/shenlan/workspaces/ai-workspace-infra/platform-ops-toolkit |
| ai-workspace-infra/iac_modules | /Users/shenlan/workspaces/ai-workspace-infra/iac_modules |
| ai-workspace-infra/gitops | /Users/shenlan/workspaces/ai-workspace-infra/gitops |
| ai-workspace-infra/playbooks | /Users/shenlan/workspaces/ai-workspace-infra/playbooks |
| ai-workspace-services/accounts | /Users/shenlan/workspaces/ai-workspace-service/accounts |
| ai-workspace-services/portal | /Users/shenlan/workspaces/ai-workspace-service/portal |
| ai-workspace-services/billing-service | /Users/shenlan/workspaces/ai-workspace-service/billing-service |
| Agent | /Users/shenlan/workspaces/ai-workspace-xstream/agent.svc.plus |
| ai-workspace-services/.github | /Users/shenlan/workspaces/ai-workspace-service/.github |

核对所有 git remote、origin/main 与现有 worktree。PROD V2 实测实现另位于 /Users/shenlan/worktrees/{playbooks-prod-v2,gitops-prod-v2,iac-prod-v2,console-prod-v2}。不能只查主工作区，忽略部署分支尚未合入的实现。

历史 release 为 prod-v2-2026.10.16-r3，详细 SHA/digest 见归档；核验存在后才复用。每个仓库独立固定 SHA，不要求多个仓库共享一个 SHA 或同名 tag。

## 5. 已交付的 one-shell

建议放在对应 owner 的 scripts/selfhost/ 下；先搜索现有等价入口，若有则扩展并删除重复实现。

| 入口 | Owner | 唯一职责 |
| --- | --- | --- |
| provision.sh | iac_modules | 按 GitOps profile plan/apply；输出权威 CMDB/inventory |
| control.sh | playbooks | 控制面配置、PG bootstrap、Doco-CD 启用、版本验证；显式 phase |
| free.sh | playbooks | 仅指定区域的 Free 节点 |
| plus.sh | playbooks | 仅指定区域的 Plus 节点 |
| team.sh | playbooks | 仅指定区域的 Team 节点 |
| migrate-users.sh | playbooks | Selfhost 源库到指定目标库的单向账号迁移及比对 |
| import-subscriptions.sh | playbooks | CSV 预览、按 email 幂等应用、导出和比对 |

Free/Plus/Team 三个入口薄封装同一个 edge.sh，固定 resource class，避免复制安装逻辑。用 --region 和 --node-id 扩展多区域、多节点，不新增 jp-free.sh、sg-free.sh 等副本。

实际文件位置：

- IaC：`ai-workspace-infra/iac_modules/scripts/selfhost/provision.sh`。
- Playbooks：`ai-workspace-infra/playbooks/scripts/selfhost/control.sh`、`free.sh`、`plus.sh`、`team.sh`、`migrate-users.sh`、`import-subscriptions.sh`，以及共用的 `edge.sh`、`common.sh`。
- `provision.sh` 只负责 provider generator → Terraform plan/apply → CMDB/inventory；其余脚本只调用 Ansible owner playbook 或 Accounts 管理 API，不创建第二份拓扑。

脚本不自动创建云资源。节点和控制面的实际 host/IP 均从 IaC receipt 派生的 inventory 获取，不用脚本生成第二份人工拓扑。

## 6. UAT / PROD profile

### 输入参数合同（以本节为准）

环境、部署标识和域名均为显式输入，不根据 `uat/prod` 拼接域名，不硬编码 `onwalk.net/svc.plus`。下表域名仅为历史示例，不是程序默认值或固定映射。

统一参数：
- `--env`：部署环境，例如 uat、prod；值需通过环境 allowlist 和权限校验。
- `--deployment-id`：独立部署实例，例如 selfhost-prod-v2，不能仅凭 env 选择旧 PROD。
- `--console-domain`、`--accounts-domain`、`--billing-domain`、`--postgres-domain`：控制面各服务的完整域名。
- `--node-domain`：当前 Free/Plus/Team 节点的实际完整域名；同时用于该节点 EntryPoint。
- `--source-accounts-domain`：单向迁移源的 Accounts 服务域名；迁移源数据库身份另由受保护配置提供，不能从服务域名猜测 DSN。
- `--region`、`--node-id`、`--manifest`、`--inventory`、`--vars-file`、`--phase`：维持前述职责。

每个操作只要求自己实际使用的域名：控制面要求四个控制面域名；边缘要求 node/accounts/billing；订阅导入要求 accounts；迁移要求源/目标 Accounts 域名及独立数据库身份。禁止自动生成不存在的域名补齐参数。

命令行参数是本次目标选择，GitOps 是持久声明；两者不一致时 preflight 失败并报告差异，不能静默覆盖任意一方。需要换域名时先更新对应 GitOps/IaC 声明，核验 DNS/TLS 后执行服务配置；部署脚本自身不修改 DNS。域名规范化为不含 scheme、端口、路径的完整 hostname，拒绝通配符、用户信息、控制字符及不合法值；HTTPS URL 由校验后的域名生成。

域名输入不承载数据库密码、token 或 cookie；不因输入 postgres-domain 就开放数据库公网访问。不以域名后缀判断环境或信任边界。最终 receipt 记录本次环境、部署 ID 和所有实际使用域名。

Workflow caller 必须传递同样的显式域名参数或经验证的部署 manifest，不能把一个 target_domain_base 当成全部服务域名合同；保留 source_domain_base/target_domain_base 时仅用于兼容已有调用，不允许用于重写或推断新节点域名。

| 字段 | UAT | PROD |
| --- | --- | --- |
| environment | uat | prod |
| deployment_id | selfhost-uat | selfhost-prod-v2 |
| source-of-truth | 独立 UAT GitOps 声明 | 独立 PROD V2 GitOps 声明 |
| 控制面 | web-saas-uat，先核验身份 | web-saas-prod-v2，先核验身份 |
| Console | console-selfhost-uat.onwalk.net | console-selfhost-prod-v2.svc.plus |
| Accounts | accounts-selfhost-uat.onwalk.net | accounts-selfhost-prod-v2.svc.plus |
| Billing / PG | 从 UAT GitOps 解析，不猜域名 | billing-selfhost-prod-v2.svc.plus / postgresql-selfhost-prod-v2.svc.plus |
| Free / Plus / Team | 从当前 CMDB / EntryPoint 解析 | 见下表 |
| release | 经验证的 UAT 固定 release | 经验证的 PROD V2 固定 release |
| Vault | uat 最小权限 | prod 最小权限，且目标锁定 V2 |

PROD JP 目标：
- Free：Akamai 东京，1C2G，agent-shared-selfhost-prod-v2.svc.plus。
- Plus：AWS 东京，c8gd.medium，jp-xconnect-prod-v2.svc.plus。
- Team：GCP 东京，非突发 2 vCPU / 2 GiB；候选 n2-custom-2-2048，agent-team-selfhost-prod-v2.svc.plus。
- 控制面：GCP 一台，Console / Accounts / Billing / 独立 PostgreSQL / Doco-CD。

AWS c8gd.medium 为 1 vCPU / 2 GiB。选型和实际库存核验见多云任务书，不把 GCP 的两个逻辑 vCPU 直接视为与 Graviton 性能等价。

每份 profile 至少声明：
- environment、deployment_id、region、provider/account、resource_class、pool、node_id、EntryPoint；
- 控制面和每个节点身份、state key、inventory/CMDB receipt checksum；
- 每个仓库固定 SHA，应用镜像 digest，Agent/Xray/exporter 版本和各架构 checksum；
- PG 持久盘 ID、目标数据库身份、TLS/Vault 引用；
- Doco-CD immutable ref、源账号数据库只读身份、迁移目标身份；
- 订阅导入策略、日志/回执目录。秘密只写引用，不写值。

## 7. control.sh：控制面 one-shell

控制面一台：Console、Accounts、Billing、独立 PostgreSQL，由 GitOps/Doco-CD 部署。

显式阶段：
1. preflight：核对环境、实例身份、挂载盘、镜像和 GitOps refs。
2. bootstrap：仅首次安装基础依赖、准备持久卷/PG/Doco-CD；PG 先启动，应用 writer 暂不启用。
3. initialize：仅空库执行固定版本 native schema，已有库拒绝重新初始化；增量升级单独审计。
4. activate：显式允许应用写入后启动 Doco-CD，收敛固定镜像。
5. verify：核对 Accounts readyz、Billing schema/role、Console runtime endpoints、实际镜像 digest。
6. converge：日常幂等配置与版本收敛，不初始化、不迁移。

复用 setup-web-saas-domain.yml、Doco-CD role、已审查 native init/billing owner。
历史 deploy-prod-v2-control.yml / activate-prod-v2-control.yml 是 PROD V2 特例，必须先参数化目标断言、磁盘、域名和路径，再用于 UAT；不得靠 sed 替换主机名。

Doco-CD 不默认 reference=main，应显式固定 release ref。PostgreSQL 5432 不开放公网。控制面 80/443 对外开放，主机删除保护由 IaC 管理。

## 8. free.sh / plus.sh / team.sh：区域节点 one-shell

三个入口参数一致：
--env、--deployment-id、--region、--node-id、--manifest、--inventory、--vars-file、--phase。

phase 支持 preflight / deploy / verify / converge，不接受与入口冲突的 resource class。
底层复用 setup-agent-proxy-domain.yml 和统一 edge owner，禁止每个入口复制 curl 安装逻辑。

每台节点完成：
- 安装固定版本、校验架构/制品 checksum，不执行 main/latest 浮动脚本。
- Caddy → Xray Unix socket；XHTTP/TCP 独立服务。
- Agent 只同步对应 pool；Team 还校验 team scope，不使用跨池 wildcard token。
- 两个 exporter 分离 node ID 和 checkpoint。
- EntryPoint 是实际节点域名，控制面 URI/QR 复用正确域名、UUID 和 path。
- JSON 配置缩进可读，验证成功才原子替换/重启。
- root/指定 SSH 用户 home 保留 0700 的节点 init.sh；按用户授权可保留该节点最小权限 enrollment token，不保留 Vault root token。敏感任务 no_log。
- verify 同时检查心跳、已加载 client、真实连接、计量和跨池拒绝；Team=0 允许健康。

新增区域只新增 GitOps 声明和 IaC 资源，复用入口，不能沿用旧 IP 或将台湾主机标成 JP。

## 9. migrate-users.sh：单向迁移 one-shell

明确 source 与 target，source 必须是 Selfhost PROD，不是 Serverless。使用 Accounts cmd/migratectl 和审核过的迁移 owner。

显式阶段：
- preflight：确认只读源、目标实例/库身份、版本、连接方向；源目标不能相同。
- export：受保护快照，排除旧 session，保存必要账号状态和 checksum。
- preview：目标空库/合并策略检查；输出脱敏数量及冲突。
- apply：只向目标写，暂停初始导入期间的目标 writer；不回写源。
- compare：账号数、email 归一化映射、proxy UUID、密码 hash、MFA、active 状态。
- verify：回执和目标正常登录/代理配置同步；不输出完整 UUID/hash。

需要初次初始化时由 control.sh initialize 显式执行，不内嵌清库动作。已导入目标重跑优先 compare，禁止隐式 reset/clean。

历史基线 30 账号。Free=19、Plus=10、Team=0，1 root 不下发代理。这是历史数据状态，不是永久硬编码断言。执行时按有效订阅和当前时间核对差异。

特别注意：现有 cmd/migratectl/main.go 在部分 checkout 的 export/import 只支持 --dsn，而 native 部署使用其他版本的 --dsn-env/受控初始化接口。脚本必须核对固定版本 help；需要时在 Accounts owner 增加安全环境变量读取，不能将 DSN 放进日志或假装已有参数。
历史迁移还补充 active/有效期状态，不能仅包装 export/import 就宣称完全等价。

## 10. import-subscriptions.sh：订阅用户 one-shell

复用真实管理 API，不直接向表硬写，也不前端硬编码。

已核对 Console 管理路由合同：
- PUT /api/admin/users/plan-groups/batch（Console BFF）；
- 对应 Accounts /admin/users/plan-groups/batch，认证模式按实际固定版本核验；
- preview body：mode=preview、requestId、reason、csv、reconcile；
- preview 返回 previewToken 等信息；
- apply 的确切 body 按 Accounts handler/真实回执核对，不凭前端类型猜 CSV apply 是否需要 updates。

phase：
1. preview：解析 CSV/email/date/额度/费用，服务端校验，保存受保护 preview receipt。
2. apply：使用同一批数据、同一 requestId 和匹配 previewToken；CSV checksum/目标环境必须与 preview 一致。
3. replay：复用 requestId 核验幂等，不重复建订阅或扣费。
4. compare：导出/DB 只读核对记录与分组，字段持久化。
5. export：导出当前订阅到受保护文件，供下次审核。

默认 reconcile=false，只有明确声明完整权威名单时才开启；部分名单不能把未列出的订阅用户全部降级 Free。
历史 10 条名单见多云任务书。缺失日期保留为空，不自动造日期。历史 7 年付/3 月付、每月 20 GiB；Free 3 GiB/自然月，耗尽断流/邮件/下月恢复按实际合同验证。
凭据经短期管理员会话/受保护 cookie 文件传递，避免命令行 token、自动跳转到不同认证域或 HTTP 降级。
receipt 可能含 email、UUID、previewToken，不能当作公开 artifact。

## 11. 与现有 workflow 的映射

| One-shell 阶段 | 当前 workflow 对应 |
| --- | --- |
| profile/目标解析 | resolve-targets |
| IaC provision | iac，调用 iac-pipeline-multi-cloud-master.yaml |
| receipt → CMDB/inventory | provision |
| 控制面配置/bootstrap | deploy_base |
| 固定版本 GitOps 收敛 | update_gitops_tags、deploy_web_saas |
| native PG/schema | native_prod_standby、native_prod_init、native_prod_billing |
| 三类边缘部署 | deploy_agent_proxy，按每台 host 增加 class/pool/env |
| 验证 | Web SaaS / Agent status 和最终 deployment summary |
| 账号迁移 | trigger_data_migration、native_prod_business，先核对保护合同 |
| 订阅导入 | 当前没有明确独立 job；需新增受控 owner 调用 |

当前发现的缺口，不得忽略：
- Agent job 使用 AGENT_PROXY_DOMAIN=matrix.host 是正确方向，但未展示完整 free/plus/team 独立 scope 合同。
- 当前调用传 agent_proxy_build_on_target=true；应改为复用校验过的固定制品，避免不同节点临时编译漂移。
- Agent job 目前读取共享 INTERNAL_SERVICE_TOKEN；迁移到每节点/每资源类型最小 scope 合同，不能简单复制到三台。
- update_gitops_tags 当前会修改环境 .env 并 git push，且有 ref=main；PROD V2 不允许修改旧 PROD 配置或依赖浮动实现。
- setup-web-saas-domain.yml 中 Doco-CD 当前默认 main，需要固定 release ref。
- 原生 PROD action 可能指向旧生产目标；不得只把 vault_env_path 改成 prod 就调用。
- web-saas-data-operations.yml 当前 UAT 限定，migration 有未实现阻断；不得通过换变量冒充支持 PROD。
- 历史 PROD V2 边缘模板写死 JP、PROD Accounts、AMD64、按 role 选首个节点，必须参数化为 env/region/node ID。
- workflows 中仍有 @main 引用，先审查并固定 owner/caller refs。
- 当前 dispatch 无独立 V2 deployment_id/资源类型输入，不应输出貌似可用的 free/plus/team dispatch 命令；先实现合同和测试。

## 12. 预期调用示例（接口合同，待实施）

以下是脚本落地后应支持的命令，不是当前可直接执行的现成命令。manifest 从 GitOps 获取，inventory 来自 IaC，vars 文件来自受保护运行时配置。

```sh
# UAT 控制面
bash control.sh --env uat --deployment-id selfhost-uat --phase bootstrap \
  --console-domain "$UAT_CONSOLE_DOMAIN" --accounts-domain "$UAT_ACCOUNTS_DOMAIN" \
  --billing-domain "$UAT_BILLING_DOMAIN" --postgres-domain "$UAT_POSTGRES_DOMAIN" \
  --manifest "$UAT_MANIFEST" --inventory "$UAT_INVENTORY" --vars-file "$UAT_VARS"

# PROD V2 控制面
bash control.sh --env prod --deployment-id selfhost-prod-v2 --phase bootstrap \
  --console-domain "$PROD_CONSOLE_DOMAIN" --accounts-domain "$PROD_ACCOUNTS_DOMAIN" \
  --billing-domain "$PROD_BILLING_DOMAIN" --postgres-domain "$PROD_POSTGRES_DOMAIN" \
  --manifest "$PROD_MANIFEST" --inventory "$PROD_INVENTORY" --vars-file "$PROD_VARS"

# 各环境分别取对应 manifest / inventory / vars
bash free.sh --env "$DEPLOY_ENV" --deployment-id "$DEPLOYMENT_ID" \
  --region jp --node-id "$FREE_NODE_ID" --phase deploy \
  --node-domain "$FREE_NODE_DOMAIN" --accounts-domain "$ACCOUNTS_DOMAIN" --billing-domain "$BILLING_DOMAIN" \
  --manifest "$MANIFEST" --inventory "$INVENTORY" --vars-file "$VARS_FILE"

bash plus.sh --env "$DEPLOY_ENV" --deployment-id "$DEPLOYMENT_ID" \
  --region jp --node-id "$PLUS_NODE_ID" --phase deploy \
  --node-domain "$PLUS_NODE_DOMAIN" --accounts-domain "$ACCOUNTS_DOMAIN" --billing-domain "$BILLING_DOMAIN" \
  --manifest "$MANIFEST" --inventory "$INVENTORY" --vars-file "$VARS_FILE"

bash team.sh --env "$DEPLOY_ENV" --deployment-id "$DEPLOYMENT_ID" \
  --region jp --node-id "$TEAM_NODE_ID" --phase deploy \
  --node-domain "$TEAM_NODE_DOMAIN" --accounts-domain "$ACCOUNTS_DOMAIN" --billing-domain "$BILLING_DOMAIN" \
  --manifest "$MANIFEST" --inventory "$INVENTORY" --vars-file "$VARS_FILE"

bash migrate-users.sh --env "$DEPLOY_ENV" --deployment-id "$DEPLOYMENT_ID" \
  --source-accounts-domain "$SOURCE_ACCOUNTS_DOMAIN" --accounts-domain "$ACCOUNTS_DOMAIN" \
  --phase preview --manifest "$MANIFEST" --inventory "$INVENTORY" --vars-file "$MIGRATION_VARS"

bash import-subscriptions.sh --env "$DEPLOY_ENV" --deployment-id "$DEPLOYMENT_ID" \
  --accounts-domain "$ACCOUNTS_DOMAIN" \
  --phase preview --csv "$SUBSCRIPTIONS_CSV" --manifest "$MANIFEST" --vars-file "$IMPORT_VARS"

# 新增 SG：先在 GitOps/IaC 声明 sg 的节点，再复用同一入口
bash free.sh --env "$DEPLOY_ENV" --deployment-id "$DEPLOYMENT_ID" \
  --region sg --node-id "$SG_FREE_NODE_ID" --phase deploy \
  --node-domain "$SG_FREE_NODE_DOMAIN" --accounts-domain "$ACCOUNTS_DOMAIN" --billing-domain "$BILLING_DOMAIN" \
  --manifest "$MANIFEST" --inventory "$INVENTORY" --vars-file "$VARS_FILE"
```

## 13. 阶段顺序及验收

首次空环境：
IaC plan/apply → receipt/CMDB → control bootstrap → initialize → migrate preview/apply/compare →
control activate/verify → subscription preview/apply/replay/compare → edge deploy/verify → 全链路验收。

已存在环境：
盘点/备份 → IaC 无破坏增量 → control converge → 仅显式增量迁移 → edge converge → 验证。
不因为 rerun 就重新初始化、迁移或导入。

先按 UAT 合同部署验证，再按 PROD V2 合同部署验证；此前不触发 GitHub Actions。
完成后切换 selfhost-orchestrator caller，先 plan，再部署同一固定版本；第二次运行不得重建主机、重复迁移、重复导入、改旧 DNS。
push/PR/tag 也可能自动触发，必须审查触发规则，不将“未 dispatch”误写成“没有触发流水线”。

最终验收：
- UAT/PROD secrets、state、账户、DB、EntryPoint 不串环境。
- 所有 one-shell 有 --help，错误参数/不存在目标拒绝，非零退出、阶段回执、并发锁和断点重跑明确。
- control rerun 不动非空库；migration 不回写源；import replay 幂等。
- Free/Plus 真凭据分别通过 XHTTP/TCP，跨池拒绝，Team 空池健康。
- Accounts/Console/Billing 实际版本、Doco-CD revision、节点二进制、计量链路均核对。
- 输出完整 owner→caller→验证证据；静态检查与本地 mock 不当成 UAT/PROD 实测。
- 在本仓库 docs 追加落地命令和真实结果，再将本任务书中“拟实施”标记逐项更新。

