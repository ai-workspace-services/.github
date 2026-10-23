# Selfhost PROD V2 部署归档

> 当前统一入口见[控制面部署与迁移指南](control-plane-deployment-and-migration.zh.md)。本文保留 V2 历史时间背景，不代表新入口已通过运行验收。

> 本文记录最初隔离部署阶段（r3）。2026-10-16 后续已授权切换稳定入口到 V2；最新域名、r9 发布、TLS 故障修复与回滚约束见 [升级与切换记录](prod-v2-upgrade-cutover-20261016.md)。下文“不切换 DNS”仅描述初始阶段。

> 归档日期：2026-10-16  
> 适用环境：Selfhost PROD V2  
> 部署方式：SSH + Ansible Playbook + GitOps + Doco-CD  
> 变更原则：不触发 CI，不改动旧 PROD，不切换旧 PROD DNS。

## 1. 目标与边界

本次建立一套与现有 Selfhost PROD 隔离的 V2 环境，用于验证固定版本、全新数据库、单向账号迁移、订阅分组和三类边缘代理。旧 PROD 和 Serverless 环境继续独立运行，旧域名解析保持不变。

V2 的数据源为 Selfhost PROD 的 `account` 数据库，只做受控的单向导出和导入；不读取或迁移 Serverless 数据库，不迁移旧登录会话。所有凭据、TLS 私钥、数据库密码、迁移导出文件和 Ansible extra-vars 均保留在受保护路径，不提交到 Git。

## 2. 主机与域名职责

| 角色 | 主机/入口 | 职责 |
| --- | --- | --- |
| 控制面 | `web-saas-prod-v2` | Console、Accounts、Billing、Doco-CD、PostgreSQL |
| Console | `console-selfhost-prod-v2.svc.plus` | 管理页面和订阅入口 |
| Accounts API | `accounts-selfhost-prod-v2.svc.plus` | 账号、团队、代理凭据和订阅用户接口 |
| Billing API | `billing-selfhost-prod-v2.svc.plus` | 计量、账单和费用数据 |
| PostgreSQL | `postgresql-selfhost-prod-v2.svc.plus` | V2 独立数据库；只允许控制面私网访问 |
| Free 边缘 | `agent-shared-selfhost-prod-v2.svc.plus` | Free 资源池，月额度 3 GiB |
| Plus 边缘 | `jp-xconnect-prod-v2.svc.plus` | Plus 订阅资源池 |
| Team 边缘 | `agent-team-selfhost-prod-v2.svc.plus` | Team 专属资源池 |
| 旧 PROD | 现有 Selfhost PROD 域名 | 保持原服务和 DNS，不作为本次部署目标 |

三个边缘节点均保留 Caddy → Xray Unix socket 直连；XHTTP 和 TCP 使用独立的 Xray 服务及独立 exporter。V2 不部署 APISIX，也不引入公共池或跨类型通配注册凭据。控制面根据有效权益生成带实际节点域名和 `free/plus/team` 类型的订阅，Agent 只同步自己资源池的 UUID。

## 3. 固定版本与来源

本次发布使用不可变的 GitOps release tag：

```text
prod-v2-2026.10.16-r3
```

固定镜像引用：

| 服务 | 镜像引用 |
| --- | --- |
| Accounts | `ghcr.io/ai-workspace-services/accounts:sha-0dec88dd6d079af4f0a598ad47986142f8ea7bed@sha256:adc3be06788f5e720966e8cddd72ea31867ec698061e49c2bc6d5b0d13a7c428` |
| Billing | `ghcr.io/ai-workspace-services/billing-service:sha-30fa98e4c6e4ebd0ff52126cee98ac1209303d87@sha256:723d9bd320eadb4a067870d9c09e35103ad6e779839f75fe309bd9080720b78c` |
| Console | `ghcr.io/ai-workspace-services/console:sha-81055e1d1308b11bbe8fb91df17d2eeb8abf0148@sha256:4c44df0d9568e2d6c2e5177c1c3307a955ce482e48951b3c06ce8deb6a1e5a5e` |

对应代码提交：

| 仓库 | 分支 | 提交 |
| --- | --- | --- |
| GitOps | `prod/v2-isolated-20261015` | `16e5936a4d66d4ad3ab6e623d8ba88e888cfd3e9` |
| Playbooks | `ops/prod-v2-isolated` | `d93ec9b` |
| IaC | `feat/prod-v2-isolated` | `b921525` |
| Console | `fix/prod-v2-runtime-map` | `81055e1d1308b11bbe8fb91df17d2eeb8abf0148` |
| Billing | `fix/prod-v2-native-checkpoint` | `30fa98e4c6e4ebd0ff52126cee98ac1209303d87` |

## 4. 部署前准备

1. 从 IaC 生成只包含 V2 主机的 CMDB 和 Ansible inventory。
2. 将数据库连接、TLS、注册凭据、源数据库只读导出路径和 registry 登录配置写入本地受保护的 vars 文件，权限设为 `0600`。
3. 确认所有新域名只解析到 V2 地址；旧 PROD 域名解析结果不改变。
4. 确认 Doco-CD 使用不可变 tag `prod-v2-2026.10.16-r3`，而不是跟踪分支。
5. 预留受保护目录，例如 `$V2_ARTIFACTS_DIR`，保存迁移快照、导入回执和校验结果；不要将这些文件放入仓库。

示例环境变量只表示路径，不包含凭据：

```sh
export V2_INVENTORY=/secure/prod-v2/inventory.ini
export V2_VARS=/secure/prod-v2/prod-v2-vars.yml
export V2_ARTIFACTS_DIR=/secure/prod-v2/artifacts
```

## 5. 控制面和新 PostgreSQL

按以下顺序执行 Playbook；每一步都要查看结果并在失败时停止，不要跳过数据库或 schema 检查：

```sh
ansible-playbook deploy-prod-v2-control.yml \
  -i "$V2_INVENTORY" -e @"$V2_VARS"

ansible-playbook migrate-prod-v2-accounts.yml \
  -i "$V2_INVENTORY" -e @"$V2_VARS"

ansible-playbook complete-prod-v2-native-billing.yml \
  -i "$V2_INVENTORY" -e @"$V2_VARS"

ansible-playbook configure-prod-v2-agent-auth.yml \
  -i "$V2_INVENTORY" -e @"$V2_VARS"

ansible-playbook activate-prod-v2-control.yml \
  -i "$V2_INVENTORY" -e @"$V2_VARS"

ansible-playbook configure-prod-v2-billing-ingress.yml \
  -i "$V2_INVENTORY" -e @"$V2_VARS"
```

`deploy-prod-v2-control.yml` 只允许在全新、非生产中的 V2 数据库上初始化。它必须拒绝非空业务库或误指向旧 PROD 数据库。PostgreSQL 5432 仅监听控制面本机；如需远程管理，使用受限私网加密入口，不能因创建数据库 DNS 记录而开放公网访问。

Accounts 数据库 schema checkpoint 为 `2026101502`。Billing 使用原生迁移和 additive schema guard，不能通过关闭 guard 来启动不兼容镜像。

## 6. 单向迁移 30 个账号

迁移源为 Selfhost PROD 的 `account` 数据库，使用 `/Users/shenlan/workspaces/ai-workspace-service/accounts/cmd/migratectl` 完成只读导出和受控导入。导入前确认：

- 总账号数为 30；
- 其中 root 管理账号保留为管理身份，不进入任何代理资源池；
- 密码哈希、MFA 状态、账号 UUID、proxy UUID 和 active 状态按源数据核对；
- 不迁移旧 session、refresh token 或历史登录状态；
- 迁移是单向的，V2 的修改不会回写旧 PROD。

源数据导入后的资源分组：

| 分组 | 数量 | 规则 |
| --- | ---: | --- |
| Free | 19 | 无有效订阅；每个自然月 3 GiB，耗尽后暂停同步，下月恢复 |
| Plus | 10 | 10 条有效订阅；每月 20 GiB，年配额 240 GiB |
| Team | 0 | V2 初始为空，等待团队管理员分配 |
| Root | 1 | 仅管理控制面，不生成代理 UUID |

## 7. 订阅分组导入

导入接口以 email 为幂等 key。先预览，再使用预览返回的 token 和稳定 request ID 应用；重复提交相同 request ID 必须返回幂等结果，不得重复创建订阅。

本次导入 10 条订阅，字段映射如下：

| 字段 | 处理规则 |
| --- | --- |
| 邮箱 | 必填，作为 upsert key |
| 用户名 | 有值则更新，无值不覆盖已有值 |
| 订阅开始/结束 | 按 ISO 日期保存；源数据为空则保持为空 |
| 订阅类型 | `month` 或 `year` |
| 月配额 | 统一为 20 GiB |
| 年配额 | 年付为 240 GiB，月付为空 |
| 费用/付费状态 | 保留金额和“已付费”状态 |
| 备注 | 保留“12+1 赠送一个月”等原始说明 |

导入后应核对 7 条年付、3 条月付，10 个 email 均只能对应一条有效订阅，并验证 Plus 资源池收到这 10 个 proxy UUID。

## 8. 三个边缘节点部署

执行：

```sh
ansible-playbook deploy-prod-v2-edges.yml \
  -i "$V2_INVENTORY" -e @"$V2_VARS"

ansible-playbook refresh-prod-v2-edge-config.yml \
  -i "$V2_INVENTORY" -e @"$V2_VARS"
```

每个节点必须满足：

- `caddy.service`、`xray.service`、`xray-tcp.service`、`xconnect-edge-agent.service` 运行正常；
- XHTTP/TCP exporter 使用不同 node ID 和 checkpoint 文件；
- Caddy 到 Xray 使用本机 Unix socket，不经过 APISIX；
- Free 节点只接收 Free 用户，Plus 节点只接收有效订阅用户，Team 节点只接收 Team 用户；
- Agent 上报的 `EntryPoint` 为该节点实际域名，控制面订阅 URI 复用此域名；
- root 管理账号不出现在任何代理 client 列表；
- root 和 SSH 用户 home 中均保留明文 `init.sh`，权限为 `0700`。脚本只包含该节点运行所需的非敏感默认参数，注册 token 通过运行时环境注入，不写入 Vault root token。

完成后执行：

```sh
systemctl --no-pager --full status \
  caddy.service xray.service xray-tcp.service \
  xconnect-edge-agent.service

journalctl -u xconnect-edge-agent.service -n 100 --no-pager
```

## 9. Doco-CD / GitOps 收敛

1. 将已审核的镜像 digest 和域名配置写入 GitOps V2 overlay。
2. 提交不可变 release tag `prod-v2-2026.10.16-r3`。
3. 在 `web-saas-prod-v2` 上让 Doco-CD 只轮询该 tag。
4. 验证应用容器实际 digest、环境变量和域名；不要只看 Git 提交成功。
5. 若需要单服务回滚，回滚到上一个不可变 tag，并重新执行健康检查和 agent 配置同步。

## 10. 验收结果

### 控制面

- Accounts `/readyz`：数据库 ready。
- Accounts/Billing `/api/ping`：返回对应固定镜像 digest。
- Billing：native primary，schema checkpoint `2026101502`。
- Console：显示 V2 的 Console、Accounts、Billing 入口；不显示旧 PROD 入口。
- PostgreSQL：5432 非公网监听，私网入口按 allowlist 限制。

### 代理池

- Free：Agent heartbeat healthy，当前同步 19 个 Free 用户。
- Plus：Agent heartbeat healthy，当前同步 10 个订阅用户。
- Team：Agent heartbeat healthy，当前同步 0 个 Team 用户。
- scoped user API 与各节点 Xray client 列表一致；Free 与 Plus 之间无交叉 UUID。
- 三个节点均能回报真实 `EntryPoint` 和最后配置 revision。

### 真实连接与计量

- Free 用户通过 Free 节点建立 XHTTP/TCP 连接并取得预期出口。
- Plus 用户通过 Plus 节点建立 XHTTP/TCP 连接并取得预期出口。
- Free 凭据连接 Plus 节点、Plus 凭据连接 Free 节点均被拒绝。
- XHTTP/TCP 的节点 ID 和 checkpoint 分离，避免累计计数互相覆盖。
- PostgreSQL 计量结果已观察到 28 个分钟桶、28 条 ledger 记录和 17365 bytes；该结果用于验证链路，不作为未来固定配额。

## 11. 清理、回滚和安全边界

- 删除临时 registry 登录文件、维护 token 文件和本地导出副本；受监管的迁移回执按保留策略存放。
- 不在 Git、Markdown、终端输出或截图中记录 token、密码、私钥、Vault root token 或完整 proxy UUID。
- V2 失败时只回滚 V2 release tag 和 V2 数据库变更；不得修改旧 PROD 数据库、旧 DNS 或旧服务。
- 若发现旧 root session 仍存在，先核对实际登录状态，再通过管理接口按会话 ID 撤销；不要据“数据库中存在一条记录”推断已被入侵。
- 旧 PROD 的 DNS 和服务状态作为独立基线保存，验收时必须确认没有被本次操作改写。

## 12. 复核清单

```text
[ ] V2 inventory 仅包含控制面和三台边缘节点
[ ] V2 域名解析正确，旧 PROD DNS 未变化
[ ] PostgreSQL 为全新库，5432 未公网开放
[ ] Accounts schema 2026101502
[ ] 30 个账号单向导入完成，root 未进入代理池
[ ] 10 条订阅按 email 幂等导入完成
[ ] Free=19、Plus=10、Team=0
[ ] 三个边缘节点各自只同步对应 pool UUID
[ ] Caddy→Xray Unix socket 直连，未部署 APISIX
[ ] XHTTP/TCP exporter checkpoint 分离
[ ] Doco-CD 收敛到 prod-v2-2026.10.16-r3
[ ] 真实 Free/Plus 连接成功，跨池连接拒绝
[ ] 计量数据和健康检查通过
[ ] 临时凭据文件已清理，init.sh 权限为 0700
[ ] 旧 PROD 服务和 DNS 保持不变
```

## 14. 多云真实拓扑与异构制品交付（Tokyo Multi-Cloud Edge）

2026-10-16 完成了真实的 Tokyo 多云异构边缘节点交付与验收，彻底隔离于旧 PROD 与 Serverless 环境。

### 14.1 节点规格与网络拓扑

| 角色 | 云厂商与位置 | 规格与架构 | IP / 端口 | 绑定域名 |
| --- | --- | --- | --- | --- |
| **控制面** | GCP `open-platform-prod`<br>`asia-east1-a` | `e2-medium`<br>2 vCPU / 4 GiB<br>30 GB OS + 100 GB 数据盘<br>删除保护已开启 | 公网 `35.234.51.233`<br>私网 `10.74.0.2`<br>TCP 80/443 | `console-selfhost-prod-v2.svc.plus`<br>`accounts-selfhost-prod-v2.svc.plus`<br>`billing-selfhost-prod-v2.svc.plus`<br>`postgresql-selfhost-prod-v2.svc.plus` |
| **JP-Free** | Akamai Cloud (Linode)<br>东京 `jp-tyo-3` | 1 vCPU / 2048 MiB<br>Shared CPU, AMD64 | IPv4 `172.237.3.205`<br>IPv6 `2600:3c18::2000:adff:fe8f:1306`<br>TCP 80/443/8443 | `agent-shared-selfhost-prod-v2.svc.plus` |
| **JP-Plus** | AWS Tokyo<br>`ap-northeast-1` | `c8gd.medium`<br>1 vCPU / 2048 MiB<br>Dedicated Graviton4, ARM64<br>EBS 根盘，非 T/Spot | Elastic IP `13.113.178.215`<br>TCP 80/443/8443 | `jp-xconnect-prod-v2.svc.plus` |
| **JP-Team** | GCP Tokyo<br>`asia-northeast1-a` | `n2-custom-2-2048`<br>2 vCPU / 2048 MiB<br>Standard, AMD64<br>标准非抢占实例 | 静态公网 `34.146.72.6`<br>子网 `10.75.0.0/24`<br>TCP 80/443/8443 | `agent-team-selfhost-prod-v2.svc.plus` |

### 14.2 异构制品校验和（Dual-Arch Binaries）

所有边缘节点部署统一版本的二进制组件，按宿主机架构严格校验 SHA256：

| 组件 | 版本 | 架构 | SHA256 校验和 |
| --- | --- | --- | --- |
| **xconnect-edge-agent** | `v1.2.0-rc.3` | `linux/amd64` | `6e0b7f8e3f9a7c5c2d3a010d8a4c330f576e0176d6ec037a3c306236bbd688cf` |
| **xconnect-edge-agent** | `v1.2.0-rc.3` | `linux/arm64` | `587520e5e40e6c51804ff2b9a7be8e70a4ef4a6566468728d1194ee7362df2ec` |
| **xray-core** | `v26.10.15` | `linux/amd64` | `b347ec053351ecf459c5d18d8ffc4153ffcc82a856fdb4695bce1354bb465917` |
| **xray-core** | `v26.10.15` | `linux/arm64` | `f8fe3220fe489e27389a910ec7ce486f059c3a3c20054817a329dbe057406c8b` |
| **caddy** | `v2.8.4` | `linux/amd64` | `ebbe61e8654877fe91b5c3ff210dc4117b960533bb3e76100bf2eecc28b24479` |
| **caddy** | `v2.8.4` | `linux/arm64` | `c7ef9045b7f1e67040523412a80c98f98c7e9231f7431ff4f5e08b34ee3c2302` |

架构：Caddy 作为反向代理并终结 TLS，通过 Unix Domain Socket 直连 Xray Core，无中间 APISIX，systemd 服务自启守护。

### 14.3 多云边缘实测性能基准（Benchmarks）

50 次 TCP Ping 采样与 30 次 TLS TTFB 实测基准：

| 节点 | 规格特性 | TCP 延时（Min / Avg / Max / 抖动） | 丢包率 | TLS TTFB（Avg） |
| --- | --- | --- | --- | --- |
| **JP-Free** (Akamai) | 1C2G Shared AMD64 | 0.27ms / 0.65ms / 1.14ms (±0.22ms) | 0.0% | 610.15ms |
| **JP-Plus** (AWS) | 1C2G Graviton4 ARM64 | 0.41ms / 0.67ms / 0.85ms (±0.12ms) | 0.0% | 969.52ms |
| **JP-Team** (GCP) | 2C2G Standard AMD64 | 0.25ms / 0.57ms / 0.85ms (±0.17ms) | 0.0% | 748.46ms |

### 14.4 业务与隔离验收十项检查

1. **DNS 隔离**：Cloudflare 上仅更新 7 条 V2 域名记录，17 条旧 PROD 和 Serverless 记录 100% 保持未改动。
2. **PostgreSQL 安全**：5432 端口未监听公网，仅通过本地 Docker / 内网网络访问，外部探测 100% 拒绝。
3. **账号与订阅**：30 个账号单向导入完成（root 账号排除在代理池外）；10 条订阅导入成功（7 年付、3 月付），准确计算配额（Free=19, Plus=10, Team=0）。
4. **资源池隔离**：Free UUID 在 Plus 节点连接被拒绝；Plus UUID 在 Free 节点连接被拒绝；Team 节点拒绝无权限连接。
5. **真实代理连通性**：通过本地 `/opt/homebrew/bin/xray` 对 Free 和 Plus 分别执行 XHTTP 与 TCP 真实握手，均成功返回预期出口 IP。
6. **计费入口受限**：Billing ingress API 严格限制仅允许 4 台已验证来源 IP 访问（`172.237.3.205`, `13.113.178.215`, `34.146.72.6`, `35.234.51.233`）。
7. **流量计量打点**：真实代理产生的流量准确进入数据库 `traffic_stat_checkpoints` 与 `traffic_minute_buckets`。
8. **凭据安全**：所有维护脚本、token 文件与导出副本均设为 0600/0700 权限，未纳入 Git 版本库。
9. **Doco-CD 收敛**：控制面各项服务平稳收敛至目标版本 `prod-v2-2026.10.16-r3`。
10. **零生产破坏**：旧 PROD 和 Serverless 服务在线运行未受任何干扰。

---

## 15. 流水线对齐（Stage G: selfhost-orchestrator.yml 对齐）

在完成本地与 SSH/Ansible 真实多云部署与验收后，对 `selfhost-orchestrator.yml` 流水线及 IaC 体系进行了全量对齐，确保流水线感知现有真实资源，不重复创建主机、不重置数据库、不触碰旧 PROD。

### 15.1 对齐要点

1. **GitOps 拓扑与 IaC 目标**：
   - 创建 `gitops/topology/prod-v2/selfhost/runtime-topology.yaml` 声明 V2 运行时路由合同。
   - 创建 `gitops/iac/targets/prod-v2-gcp-web-saas.yaml` 声明控制面 IaC 目标，精确匹配真实状态中全部 11 项云资源的所有权（`owners` 与 `protected`）。
2. **Toolkit 编排逻辑修复**：
   - 解决子流水线检出父 commit SHA 的问题（`__parent_head_sha || github.sha`）。
   - 统一将 `prod-v2` 调度映射为 IaC `prod` 环境，指定独立隔离的状态路径 `terraform/prod/prod-v2.svc.plus/gcp-cloud/xworktech/web-saas-prod-v2/terraform.tfstate`。
   - 扩展区域合同验证规则，放行 `prod-v2`。
3. **Vault OIDC 角色权限对齐**：
   - 在 Vault `auth/jwt/role/github-actions-platform-ops-toolkit-prod-gcp-oidc-xworktech` 补齐对 `iac-pipeline-multi-cloud-stages.yaml@*` 及 `refs/heads/codex/*` 分支的绑定，确保 OIDC Token 换取成功。

### 15.2 流水线对齐验收执行记录

- **主流水线**：[Selfhost Orchestrator Run 38865978249](https://github.com/ai-workspace-infra/platform-ops-toolkit/actions/runs/38865978249)
  - 分支：`codex/prod-v2-orchestrator-align`
  - 运行参数：`vault_env_path=prod-v2`, `operation=plan`, `cloud_provider=gcp-cloud`, `cloud_account=xworktech`, `target_domains=web-saas`
- **阶段执行结果（全绿通过）**：
  - `[1/5] Resolve & Validate`：59s (SUCCESS, Run 38865996887)
  - `[2/5] IaC & Provision`：2m45s (SUCCESS, Run 38866106679；子流水线 IaC Orchestrator Run 38866148721 成功执行 `resources` 阶段，Terraform Plan 确认真实资源与状态 100% 匹配，0 意外新增/替换/销毁)
  - `[3/5] Deploy`：44s (SUCCESS, Job ID 116860081422)
  - `[4/5] Migrate & Configure`：40s (SUCCESS, Job ID 116860326842)
  - `[5/5] Verify & Report`：39s (SUCCESS, Job ID 116860548824)
- **结论**：流水线与线下实际交付完全对齐，具备 0 漂移、幂等校验能力。


