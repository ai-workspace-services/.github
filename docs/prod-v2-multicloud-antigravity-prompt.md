# Antigravity Code Agent 执行提示词：PROD V2 多云 JP 部署及编排对齐

将下文直接交给 Antigravity Code Agent。本文为执行任务书，不代表多云拓扑已经部署或验收。

## 任务目标

结合现有部署记录，先通过 IaC + 本地 SSH/Ansible + GitOps/Doco-CD 完成隔离的 Selfhost PROD V2 多云部署与验收；验收后再运行 selfhost-orchestrator.yml，使流水线对齐已经部署的真实资源，不重复创建主机、不重置数据库、不触碰旧 PROD。

必须先阅读：
- /Users/shenlan/workspaces/ai-workspace-service/.github/docs/prod-v2-deployment.md

该文档的旧结果为历史验收基线，必须重新核对当前主机、镜像、DNS、数据库和资源池。不得把历史验收当成本次多云验收。

## 仓库和职责

| 本地目录 | GitHub 仓库 | 职责 |
| --- | --- | --- |
| /Users/shenlan/workspaces/ai-workspace-infra/platform-ops-toolkit | ai-workspace-infra/platform-ops-toolkit | 编排、配置解析、矩阵、验收与 workflow |
| /Users/shenlan/workspaces/ai-workspace-infra/iac_modules | ai-workspace-infra/iac_modules | Terraform 多云主机、网络、防火墙、公网 IP、DNS 和 state |
| /Users/shenlan/workspaces/ai-workspace-infra/gitops | ai-workspace-infra/gitops | PROD V2 拓扑、资源类型、固定版本、非敏感配置和 Doco-CD 声明 |
| /Users/shenlan/workspaces/ai-workspace-infra/playbooks | ai-workspace-infra/playbooks | 控制面、PostgreSQL、迁移、边缘节点安装和验证 |
| /Users/shenlan/workspaces/ai-workspace-service/accounts | ai-workspace-services/accounts | 账号迁移、有效权益、订阅导入、按 pool 下发 UUID |
| /Users/shenlan/workspaces/ai-workspace-service/portal | ai-workspace-services/portal | Console、用户订阅和 root 管理页面 |
| /Users/shenlan/workspaces/ai-workspace-service/billing-service | ai-workspace-services/billing-service | 配额、计量、账单与数据库增量迁移 |
| /Users/shenlan/workspaces/ai-workspace-xstream/agent.svc.plus | 以 git remote get-url origin 为准 | Agent、setup-proxy、Xray 同步、exporter |
| /Users/shenlan/workspaces/ai-workspace-service/.github | ai-workspace-services/.github | 归档本次过程和最终证据 |

Agent 仓库当前本地 remote 指向 ai-workspace-xstream/agent.svc.plus；历史安装 URL 使用 xconnect-edge-agent。先核对仓库迁移/重定向、release 来源和脚本内容，禁止仅凭旧 URL 下载执行。

已有 worktree 也可能保存最近部署实现：
- /Users/shenlan/worktrees/playbooks-prod-v2
- /Users/shenlan/worktrees/gitops-prod-v2
- /Users/shenlan/worktrees/iac-prod-v2
- /Users/shenlan/worktrees/console-prod-v2

先检查各仓库 AGENTS.md、status、worktree list、remote 与当前 origin/main，保留已有未提交修改。本文不授权清理其他任务的工作树。

## 目标拓扑

| 角色 | 云厂商和位置 | 规格及要求 | 资源类型 |
| --- | --- | --- | --- |
| 控制面一台 | GCP open-platform-prod；核对并优先复用 web-saas-prod-v2 | Console + Accounts + Billing + 独立 PostgreSQL + Doco-CD，按现有已验证容量配置 | control-plane |
| JP Free 一台 | Akamai Cloud 东京 | 1 vCPU / 2 GiB，核对实际 plan ID、东京 region 和库存 | free |
| JP Plus 一台 | AWS ap-northeast-1 | c8gd.medium，On-Demand，ARM64；非 T 系列、非 Spot | plus |
| JP Team 一台 | GCP asia-northeast1 东京 | n2-custom-2-2048，2 vCPU / 2 GiB，标准非抢占实例 | team |

AWS 官方规格：c8gd.medium 为 1 vCPU / 2 GiB，带本地 NVMe；不能误写成 2 vCPU。持久配置和必须保留的数据存放在持久启动盘，不依赖 instance store。GCP N2 自定义规格满足本任务的 CPU/内存及非突发要求，但不预设与 AWS 单核、带宽或延迟等效；用后述实测确认。

选型原则：不要求 AWS、GCP 和 Akamai 的 CPU 架构一致。主要要求资源规格满足业务需要、持续负载稳定、网络可靠、制品可维护。允许 ARM64 与 AMD64 混合部署；不要为了架构对齐更换已满足要求的机型，也不要把架构相同当成性能对等。按每台主机实际架构选择并校验 Agent、Xray 和 exporter 制品，应用版本保持一致。

Akamai Free 可使用共享 CPU 产品，但应在结果中明确共享 CPU 的性质。禁止为了适配抽象 1C2G/2C2G 档位，静默替换 Plus 或 Team 机型。

所有边缘均标记业务 region=jp，各云 region/zone 单独记录，不能沿用旧 GCP 台湾节点的实际位置并标成东京。

## 域名合同

- Console：console-selfhost-prod-v2.svc.plus
- Accounts：accounts-selfhost-prod-v2.svc.plus
- Billing：billing-selfhost-prod-v2.svc.plus
- PostgreSQL：postgresql-selfhost-prod-v2.svc.plus
- Free：agent-shared-selfhost-prod-v2.svc.plus
- Plus：jp-xconnect-prod-v2.svc.plus
- Team：agent-team-selfhost-prod-v2.svc.plus

只允许管理这些 V2 记录。旧 Selfhost PROD 和 Serverless 的域名、解析、数据库及服务保持不变。更新 V2 记录前保存当前值和 TTL，确认新节点服务、证书、UUID 和真实连接可用后再更新；保留旧 V2 边缘以供回退，本任务不授权删除旧节点。

控制面已存在时复用；不得为了“全新部署”覆盖非空 V2 数据库。若确实需要第二套空库，先完成独立数据库命名和连接隔离设计，再执行，不使用 DROP/TRUNCATE 清库。

## 阶段 A：只读盘点与部署合同

1. 核对 GCP、AWS、Akamai 认证及权限。gcloud 曾因需要 reauthentication 失败；重新检查，不把失败当成未创建资源。
2. 只读枚举当前 V2 主机、IP、DNS、Terraform state、Doco-CD 配置、镜像 digest、库表和迁移 checkpoint。
3. 明确 Selfhost PROD 源数据库，确认是 30 个账号；不得使用 Serverless 的 24 个账号，也不得为凑数创造账号。
4. 输出拓扑差异：保留、复用/import、创建、仅更新配置。任何 Terraform replace/delete 涉及现有服务都停止该项并解释。
5. 固定每个仓库的完整 commit SHA 和镜像 digest；现有参考 release 为 prod-v2-2026.10.16-r3，先核对 tag 与制品可用性。历史完整镜像引用见部署归档。
6. 补齐 Agent、Xray、exporter、Caddy 的实际版本/校验和及 amd64/arm64 制品，不能只有控制面镜像固定。
7. 输出手工执行命令、预期变更和回退点；继续执行已授权的 V2 增量部署。

阶段 A 至阶段 F 不触发任何 GitHub Actions。检查 push/PR/tag 自动触发条件；需要保留代码时先本地提交，不默认推送 main/release/v* 或创建 PR。不能仅靠“不调用 workflow_dispatch”声称未触发流水线。

## 阶段 B：先补齐 IaC / GitOps

1. 基于现有 provider modules 建立独立 PROD V2 拓扑与状态。参考而不覆盖：
   - gitops/topology/uat/hybrid/resource-matrix.json
   - iac_modules/terraform-hcl-standard/{gcp-cloud,aws-cloud,akamai-cloud}
2. 同一 JP 区域下显式声明三个节点身份及 pool：
   - jp-free / free / akamai-cloud
   - jp-plus / plus / aws-cloud
   - jp-team / team / gcp-cloud
3. state key 至少包含环境、部署标识、provider/account、namespace，不能仅以 agent-proxy-jp 为 key 造成三个 pool 互相覆盖。
4. 固定公网 IP 或记录 provider 的保留地址能力；资源输出生成 CMDB 和 Ansible inventory，不在 Playbook 中手工抄 IP。
5. 创建所需网络、安全组、最小服务账号、持久磁盘。控制面 TCP 80/443 公网开放，目标只指向 V2；开启控制面删除保护。
6. 边缘开放真实使用的 HTTPS/XHTTP 和 TCP 监听端口；SSH 限制管理来源，exporter 与管理 API 限制控制面/监控来源。
7. DB 不因跨云而暴露公网 5432。边缘通过 Accounts HTTPS 同步，不直接连接 PG。
8. PostgreSQL 域名不是公网访问授权；核对防火墙、监听地址和实际外部探测。
9. 对已有托管资源执行安全 import 或状态对齐，避免双重 Terraform ownership。
10. 本地 terraform fmt/validate/plan，再 apply。第二次 plan 无意外创建、替换或删除。

## 阶段 C：控制面、新库与单向迁移

先核对现有 Playbook 参数和保护条件，再复用：
- deploy-prod-v2-control.yml
- migrate-prod-v2-accounts.yml
- complete-prod-v2-native-billing.yml
- configure-prod-v2-agent-auth.yml
- activate-prod-v2-control.yml
- configure-prod-v2-billing-ingress.yml

仅首次、确认为空的新库允许初始化。已导入的 V2 只运行检查、幂等增量迁移及比对，不重置。

使用 Accounts cmd/migratectl 从 Selfhost PROD 只读导出并单向导入：
- 30 个账号；
- 保留账号 ID、proxy UUID、密码 hash、MFA、active 状态；
- 不迁移旧会话、不回写源库；
- 受保护导出文件和 receipt 不进入 Git，权限 0600。

通过后台 API 以规范化 email 为 key 导入下面 10 条订阅。预览→应用→重复执行→PG 比对。不得前端硬编码分组、绕过有效权益或凭空补日期。

```csv
邮箱,用户名,订阅开始,订阅结束,订阅类型,月配额,年配额,费用,付费状态,备注
yangzhiyun724@126.com,elsa0724,2026-08-01,2027-07-30,year,20GB,240GB,200元,已付费,
13191446515@163.com,audrejing,2026-07-01,2027-06-30,year,20GB,240GB,200元,已付费,
challen66@163.com,fuyouhu,,,year,20GB,240GB,200元,已付费,
sukhadukkha@163.com,summer,2026-05-01,2027-05-30,year,20GB,240GB,200元,已付费,12+1赠送一个月
208746734@qq.com,,2026-10-15,2026-11-14,month,20GB,,20元,已付费,
304235059@qq.com,,2026-09-01,2027-08-30,year,20GB,240GB,200元,已付费,
1324171503@qq.com,,2026-10-15,2026-11-14,month,20GB,,20元,已付费,
514916831@qq.com,,2026-10-15,2026-11-14,month,20GB,,20元,已付费,
1767425958@qq.com,,2026-10-15,2027-09-15,year,20GB,240GB,200元,已付费,
sccxboy@163.com,,2026-09-01,2027-08-30,year,20GB,240GB,200元,已付费,
```

CSV 中 GB 的历史存储单位按现有 API/DB 合同核对，避免十进制和二进制转换漂移。2026-10-16 的验收基线是 7 年付、3 月付，Free=19、Plus=10、Team=0，另 1 root 不下发代理；若执行时订阅过期或真实数据变化，报告按当前时间计算的差异，不强行维持历史数量。

订阅缺失日期的年付用户遵循明确的后台业务合同，保留空值并报告有效权益如何计算，不自动填一年有效期。

Free 每自然月 3 GiB，耗尽断流、邮件提醒、下月恢复；不参与限额/内部特权必须来自显式 DB 权益。不得给所有管理员自动无限流量。

## 阶段 D：SSH / Playbook 部署三个边缘

复用并扩展 deploy-prod-v2-edges.yml / refresh-prod-v2-edge-config.yml，支持多云 inventory 和 ARM64。

每台均为独立 Caddy → Xray Unix socket 代理，不部署 APISIX：
- xray.service 与 xray-tcp.service 独立；
- xconnect-edge-agent.service 按 resource class/pool/team scope 过滤；
- XHTTP/TCP exporter 使用不同 node ID 与 checkpoint；
- 配置 JSON 使用缩进，避免不可读的单行模板；
- Agent EntryPoint 分别为实际 Free/Plus/Team 域名；
- URI/QR 复用匹配用户 proxy UUID 所在节点的 EntryPoint 与实际 path，不保留静态域名列表回退，不使用公共 jp 入口代替 Free/Team 域名；
- UI 按 JP 区域分组，用 free/plus/team 标签展示实际域名；
- Free 和 Plus client 列表互斥，Team 空池正常，不把 clients=0 自动判为服务故障。

每个节点 root 和指定 SSH 用户 home 保留可重复执行的 init.sh，权限 0700；包含该节点正确的安装入口、固定制品版本、域名、pool、resource class 和重跑流程。用户已要求节点本地保留明文运行凭据，可只保存该节点必需且最小权限的 enrollment token；不得复制 Vault root token、数据库密码或其他节点 token。文件不进 Git，Ansible 使用 no_log，归档只保留脱敏模板。

## 阶段 E：GitOps / Doco-CD 手工发布

- Console/Accounts/Billing 固定 SHA 镜像 + digest；
- Doco-CD 固定不可变 release ref；跨仓库 ref 不假设同名 tag 均存在；
- 在不触发 GitHub Actions 的前提下交付 GitOps refs（先审查当前触发规则，必要时使用受控部署分支）；
- 控制面由 Doco-CD 收敛，边缘由 SSH/Ansible 收敛；
- 核对 Console runtime endpoint 全部指向 V2；
- 保存 release manifest、Doco-CD revision、实际 container digest 和边缘 binary version。
- 本阶段的“不可变版本”不等于重建镜像；无代码修复时复用已验收制品。

## 阶段 F：真实验收

1. 域名、证书、实际服务、删除保护及端口暴露范围通过。
2. Accounts readyz、Billing native schema、Console runtime map 通过。
3. 源→目标 30 账号比对，10 订阅持久化，重复导入无新增、无多扣费、无 UUID 变更。
4. scoped API、Agent 收到的 revision、XHTTP/TCP 已加载 client 列表三者一致。
5. 使用真实 Free/Plus 凭据分别完成 XHTTP/TCP 连接并确认出口 IP；跨池凭据被拒绝。
6. Team=0 的节点健康且无未授权 client；不要添加假用户凑验收。
7. 计量 minute bucket、checkpoint、ledger 更新，XHTTP/TCP 不互相重置。
8. root 能看到所有资源及分组；team 管理员和成员不能看到其他团队或公共共享成员。
9. 持续负载下记录 CPU、steal、内存、吞吐、延迟、丢包和跨云 Accounts 延迟；不以标称 vCPU 或 Up to 带宽认定性能对等。
10. 保存旧 PROD DNS/服务基线与本次结束后的对比；证明未改变。

## 阶段 G：最后对齐 selfhost-orchestrator

目标文件：
/Users/shenlan/workspaces/ai-workspace-infra/platform-ops-toolkit/.github/workflows/selfhost-orchestrator.yml

注意：用户给出的 github/workflows 路径缺少前导点，以上才是现有文件。

现有输入含 operation、target_domains、cloud_provider、cloud_account、source_ref、deploy_tag、dns_mode、vault_env_path 等；现有 mixed provider registry 主要面向 UAT。先审查实际逻辑，再补齐 PROD V2，不直接把 cloud_provider=gcp-cloud 应用于全部节点。

必须实现：
1. 一个明确的 PROD V2 deployment/profile 标识，独立于旧 prod 的默认资源和 state。
2. 拓扑驱动 per-resource provider/account/region/pool/arch，而不是一个 provider 覆盖四台主机。
3. 支持 JP 同区域多个 pool，不能仅用 region 去重；生成四台目标 CMDB/inventory。
4. 先采用现有命名空间扩展，确有必要再新增；不得将旧 agent-proxy-jp 的所有资源重归 V2。
5. Toolkit、IaC、GitOps、Playbooks、应用版本分别 pin；当前 source_ref 是共用 ref 时，修复/验证跨仓库映射，不假设同一 SHA 可跨仓库 checkout。
6. plan、deploy、migration、DNS 发布彼此明确，普通 deploy 不调用 init/账号迁移/订阅重导。
7. 首次流水线执行 operation=plan、dns_mode=none，仅 V2 目标；确认无重建后 operation=deploy 收敛已部署版本。
8. 不用 target_domains=all 误触共享基础设施、其他区域或旧 PROD；如需增加更窄的输入，先完成实现和测试再给实际 dispatch 命令。
9. 固定不同阶段 concurrency/state 锁，parent/child 不死锁；不同 provider/pool 不碰同一 state。
10. Vault OIDC/最小权限 secrets；禁止在 workflow_dispatch 输入里传明文 token。
11. 已完成手工验收后，才推送允许触发的 workflow/ref 并运行。记录 PR/push 自动 run 与 dispatch run，不能漏报自动触发。
12. 流水线第二次收敛应无主机替换、数据库初始化、账号重复、订阅重复或 DNS 漂移。

运行前输出本次版本实际支持的完整输入及匹配的固定 refs；不要复制本文之外未核实的 dispatch 命令。

## 最终交付

- 各仓库改动、分支、完整 SHA、PR（若创建）与固定 release manifest。
- IaC plan/apply 和第二次 plan，包含资源 ID、provider、region、pool。
- 30 账号迁移/比对回执、10 订阅幂等回执，全部脱敏。
- 四台主机服务状态、镜像/binary 版本、节点域名、真实连接和隔离证据。
- 先手工验收、后流水线对齐的时间顺序与 workflow run URL。
- 可重复的 SSH/Playbook 操作步骤，init.sh 脱敏模板和备份恢复说明。
- 更新 ai-workspace-services/.github/docs 的归档文档，保留旧 GCP-only 历史记录，新增本次多云变更记录。
- 明确未完成项；若云权限、机型库存或源库合同不符，只暂停依赖项，继续独立工作，不静默改动旧 PROD。

## 机型核对来源

- AWS C8g/C8gd：https://aws.amazon.com/ec2/instance-types/c8g/
- GCP N2 规格：https://docs.cloud.google.com/compute/docs/general-purpose-machines
- GCP 自定义机型：https://docs.cloud.google.com/compute/docs/instances/creating-instance-with-custom-machine-type

