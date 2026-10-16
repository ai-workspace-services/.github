# Selfhost PROD V1 → V2 升级、迁移与稳定域名切换记录

- 日期：2026-10-16（Asia/Shanghai）。
- 范围：Selfhost；Serverless 不参与此次迁移。
- 部署：SSH → Ansible Playbook → 固定 GitOps tag → Doco-CD；不使用流水线部署。
- 初始部署、迁移命令与镜像摘要：[PROD V2 部署归档](prod-v2-deployment.md)。
- 本文记录已观察到的结果；历史迁移验收与本轮切换验收分别列示。

## 1. 最终拓扑与域名契约

控制面 `web-saas-prod-v2` 承载 Console、Accounts、Billing、独立 PostgreSQL 和 Doco-CD。V2 公网地址为 `35.234.51.233`，控制面私网地址为 `10.74.0.2`；切换前稳定入口地址为 `34.81.174.112`。IP 是本次记录，不应作为未来版本硬编码默认值。

| 服务 | V1 版本域名 | V2 版本域名 | 稳定入口 |
| --- | --- | --- | --- |
| Console | `console-selfhost-prod.svc.plus` | `console-selfhost-prod-v2.svc.plus` | `console.svc.plus` |
| Accounts | `accounts-selfhost-prod.svc.plus` | `accounts-selfhost-prod-v2.svc.plus` | `accounts.svc.plus` |
| Billing | `billing-selfhost-prod.svc.plus` | `billing-selfhost-prod-v2.svc.plus` | `billing.svc.plus` |
| PostgreSQL | `postgresql-selfhost-prod.svc.plus` | `postgresql-selfhost-prod-v2.svc.plus` | `postgresql.svc.plus` |
| 品牌入口 | 不作为 V1 版本标识 | Console V2 | `xworktech.com` |

稳定入口使用 CNAME 指向对应 V2 版本域名；`xworktech.com` 指向 `console-selfhost-prod-v2.svc.plus`，由 Cloudflare 对根域名执行 CNAME flattening。五条记录均为 DNS-only，TTL 300 秒。DNS 切换不修改 V1 主机。

PostgreSQL 域名仅用于数据库连接，不进入 Caddy HTTP 路由，也不代表允许公网访问。数据库访问继续受网络和认证限制。

边缘节点保持三个独立资源池：

| 类型 | 入口 | 服务方式 |
| --- | --- | --- |
| Free | `agent-shared-selfhost-prod-v2.svc.plus` | Caddy → Xray Unix socket |
| Plus | `jp-xconnect-prod-v2.svc.plus` | Caddy → Xray Unix socket |
| Team | `agent-team-selfhost-prod-v2.svc.plus` | Caddy → Xray Unix socket |

不部署 APISIX；Agent 按资源类型过滤 UUID，控制面使用实际节点 EntryPoint 生成订阅。XHTTP/TCP 保持独立服务与计量 checkpoint。

## 2. 数据迁移基线

初始迁移源为 Selfhost PROD 的 PostgreSQL `account` 库，不读取 Serverless 数据库。使用 Accounts `cmd/migratectl` 单向导入全新 V2 库，保留账号身份、密码哈希、MFA、代理身份与有效状态，不迁移旧登录会话。

订阅名单通过管理导入接口按规范化 email 幂等更新，落入 PostgreSQL，由 API 管理、前端展示。名单为 10 条；不将邮箱名单或用户凭据硬编码到应用。

历史隔离部署验收记录：30 个账号、10 条订阅，代理池 Free 19 / Plus 10 / Team 0，root 不进入代理池。本轮切换前又查询确认 V2 `public.users` 为 30 条。该总数不能证明两库逐字段一致，也不能代替切换时的数据增量核对。

## 3. 发布与配置步骤

1. 初始固定版本为 `prod-v2-2026.10.16-r3`，完成隔离控制面、全新库和边缘验证。
2. 增加稳定域名配置，将公开 Console、Accounts、Billing URL 与版本域名分开。
3. 核对不可变 tag 的实际内容，发现 canonical 环境变量曾只存在于本地工作区；以新 tag `prod-v2-2026.10.16-r9` 修正，未覆盖已有 tag。
4. GitOps PR [#446](https://github.com/ai-workspace-infra/gitops/pull/446) 合并，Doco-CD 固定跟踪 r9，并观察到收敛成功。应用镜像摘要沿用初始归档中的固定版本。
5. 更新 V2 主机 Caddy 和 Accounts 域名配置。Accounts frontend/public URL、OAuth callback 使用稳定域名；运行凭据保持原值。
6. 修复 Billing 路由并持久化来源 allowlist；Playbooks PR [#664](https://github.com/ai-workspace-infra/playbooks/pull/664) 已合并，同时将 Doco-CD 声明固定到 r9。
7. 重启 Caddy、Accounts，检查磁盘文件确实被运行进程加载，而不只检查模板或 Doco-CD 日志。

相关仓库：`ai-workspace-infra/gitops`、`ai-workspace-infra/playbooks`、`ai-workspace-infra/iac_modules`、`ai-workspace-services/accounts`、`ai-workspace-services/console`、`ai-workspace-services/billing-service`、`ai-workspace-xstream/xconnect-edge-agent`。

## 4. 切换前验证

先绕过 DNS 缓存，将稳定域名请求直接发送到 V2，保留真实 Host/SNI，禁止使用 `-k` 绕过证书检查：

```sh
curl --resolve console.svc.plus:443:35.234.51.233 https://console.svc.plus/login
curl --resolve accounts.svc.plus:443:35.234.51.233 https://accounts.svc.plus/readyz
curl --resolve billing.svc.plus:443:35.234.51.233 https://billing.svc.plus/healthz
curl --resolve xworktech.com:443:35.234.51.233 https://xworktech.com/
```

- Console 首页、登录、注册页面返回 200。
- Accounts `/readyz` 返回 200，`database=ok`。
- 登录空请求返回 400 `missing_credentials`，注册空请求返回 400 `name_required`；这仅证明 API 路由和参数校验可达。
- Billing 公网返回 403；从允许的控制面私网来源请求返回 200、`status=ok`。
- Caddy 配置校验通过；PostgreSQL `pg_isready` 接受连接。

早期品牌入口 TLS 检查结论未能覆盖重启后真实状态，切换后暴露证书缺失；不能将此前的单次 200 视为完整上线验收。

## 5. DNS 切换执行

用户明确授权后，经 Vault 中 DNS 专用凭据调用 Cloudflare API，先保存五条原记录，再逐条更新为上述 CNAME。未将 token、私钥或完整配置备份提交到仓库。

Cloudflare API 确认五条记录更新成功。Google 公共 DoH 查询确认 Console、Accounts、Billing 的 CNAME 和 V2 地址；根域名 flatten 为 V2 A 地址。PostgreSQL 在第一次公共查询时仍命中旧记录缓存，因此当时只确认控制面记录已更新，没有宣称客户端已迁移完成。

本轮原记录备份位于执行机 `/tmp/prod-v2-dns-before.json`，这是临时路径，不是长期备份保障；需要回滚时先确认该文件仍存在，并将受控备份转存到运维制品存储。

## 6. 故障、原因与修复

### 6.1 Billing 磁盘配置缺少路由

Caddy 模板只有在 Billing 域名和来源 CIDR 均非空时生成 Billing handler。本地渲染时依赖的 CIDR 变量未生效，磁盘文件漏掉路由，而运行容器仍加载旧内容，形成磁盘和进程不一致。

修复：将 V2 来源 allowlist 写入 host vars，补齐稳定与版本 Billing 域名。重启容器后再次校验，允许来源 200，公网 403。不要为通过公网探测而取消来源限制。

### 6.2 验证模板占位配置误写磁盘

验证用 Accounts 模板包含占位值，曾被复制到主机磁盘；容器绑定的旧文件仍包含真实配置。修复时先从运行容器 `/app/config/account.yaml` 恢复完整配置到受保护路径，确认不含占位值，再只修改域名并重启 Accounts。重启后 `/readyz` 和数据库连接正常。

后续部署不得复制验证模板充当生产配置；应在远端使用真实 secret 渲染，并在发布前拒绝占位值。真实配置与恢复文件不得进入 Git。

### 6.3 `xworktech.com` TLS 握手失败

切换后公网出现 TLS internal alert。V2 只加载了 `*.svc.plus` 证书，该证书不覆盖 `xworktech.com`。品牌站点依赖 ACME 自动签发，但 CA 验证仍访问缓存中的旧地址，TLS-ALPN/HTTP challenge 失败，Caddy 进入重试等待。

修复步骤：

1. 从 Vault `kv/data/CICD/domains/xworktech.com` 获取已有证书和私钥，仅在受保护运行路径处理。
2. 校验证书 SAN 包含 `xworktech.com`、`*.xworktech.com`；本次证书有效期为 2026-10-07 至 2027-01-05。
3. 安装到 V2 `/etc/xcontrol/tls/xworktech.com/current/`；私钥权限 0600。
4. 品牌站点显式加载该目录的 `fullchain.pem` 和 `key.pem`，重启 Caddy。
5. 先直连 V2 检查，再检查普通公网请求；两者均返回 200、TLS 校验通过，公网连接地址为 `35.234.51.233`。
6. 抽查页面 12 个 JS/CSS 资源，全部返回 200；临时证书传输副本清理。
7. Playbooks PR [#665](https://github.com/ai-workspace-infra/playbooks/pull/665) 已合并，以 `web_saas_host_config_brand_tls_domain: xworktech.com` 保留加载契约。

复用证书解决本次恢复，不等于已验证后续自动续期。下次部署须先恢复品牌域名证书，再生成 Caddy；还需核对证书续期和刷新机制。

## 7. 本轮验收状态与剩余工作

| 项目 | 结果或边界 |
| --- | --- |
| r9 Doco-CD 收敛 | 已观察成功 |
| Caddy 磁盘配置及重启 | 校验通过，Billing 路由补齐 |
| Accounts / PostgreSQL | 就绪，30 个账号 |
| Console 登录、注册页面 | 200 |
| 登录、注册 API 参数校验 | 正常；不代表真实业务成功 |
| Billing | 允许来源 200，公网 403 |
| 品牌公网入口 | V2 地址、200、可信 TLS，抽查资源 200 |
| DNS 更新 | 五条 Cloudflare 记录更新成功；缓存按各解析器过期 |
| 真实账号登录和 MFA | 本轮尚未完成验收 |
| 注册邮件、验证码与完整注册 | 本轮尚未完成验收 |
| 切换时两库增量/写入核对 | 本轮未证明完成，需补核对 |
| PostgreSQL 稳定域名客户端重连 | 本轮尚未完成验收 |
| 边缘真实连接与计量 | 见初始部署历史验收；本轮未重测 |
| 品牌 TLS 续期 | 已恢复现有证书；后续刷新流程需核对 |

## 8. 回滚与后续 V3 / VN

1. 保留版本域名和固定镜像，稳定入口只作为指向当前版本的别名。
2. 任何新版本先准备完整证书、真实 Accounts 配置和 Billing allowlist，再以 Host/SNI 直连测试；重启后复测。
3. 切换前保存 DNS、数据库迁移 checkpoint、数据差异报告及当前可用版本。
4. 若 V2 尚无新增业务写入，确认数据状态后可以恢复原 DNS 记录；不要根据“保留了 V1 主机”推断可以无损回退。
5. V2 开始接收写入后，回切旧数据库可能丢失新增账号、订阅和账单。需暂停相关写入、备份并完成受控数据追平；不能只回滚 CNAME。
6. 数据库稳定域名变更不会迁移已建立的连接；应用连接池、网络 allowlist、TLS 身份和 schema 兼容性需单独验证。
7. 旧 V1 主机在观察期内保留；清理需要独立授权和数据保留计划。

## 9. 日常复核命令

```sh
# DNS 查询可能命中缓存，需结合权威/API 和公共 DoH 判断。
dig +short console.svc.plus
dig +short accounts.svc.plus
dig +short postgresql.svc.plus

# 公网验收，不忽略 TLS 错误。
curl -sS -o /dev/null -w 'HTTP=%{http_code} TLS=%{ssl_verify_result} IP=%{remote_ip}\n' https://xworktech.com/
curl -fsS https://accounts.svc.plus/readyz

# 在 V2 主机执行。
sudo docker exec web-saas-caddy caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
sudo docker exec web-saas-postgresql pg_isready
sudo docker exec web-saas-postgresql psql -U postgres -d account -Atc 'select count(*) from users;'
```

操作记录不得包含 Vault token、Cloudflare token、私钥、密码、完整 proxy UUID、生产导出数据或带凭据的 DSN。

## 10. V2 → V3 → VN 后续演进方案

### 10.1 固定产品入口，版本身份独立

客户端、OAuth 提供商、邮件链接使用稳定入口；每套部署保留自己的版本域名、资源标签、GitOps 目录和不可变 tag。例如 V3 使用 `console-selfhost-prod-v3.svc.plus`、`accounts-selfhost-prod-v3.svc.plus`、`billing-selfhost-prod-v3.svc.plus`、`postgresql-selfhost-prod-v3.svc.plus`。发布完成后只调整稳定入口的目标，不重命名运行主机。

Console、Accounts、Billing 的公开地址作为显式输入参数；不能从主机名推导，也不能将版本域名或 Serverless URL 编译为隐藏回退值。品牌根域名继续使用 flattening。CNAME 只负责解析，不修改 HTTP Host、SNI、CORS 或 Cookie，目标版本必须预先支持稳定域名及对应证书。

### 10.2 区分应用升级与数据库迁移

优先将无状态应用升级与数据库主库迁移拆开：应用版本切换可继续使用既有权威数据库；只有数据库本身需要更换时才走独立迁移流程。避免每次 UI/API 升级都同时引入数据搬迁风险。

| 变更类型 | 数据库处理 | 回滚条件 |
| --- | --- | --- |
| Console 或兼容 API 更新 | 保留权威数据库，执行向后兼容 schema 扩展 | 旧应用能读取新 schema、数据和 token |
| 同库应用蓝绿切换 | 两版本共享权威库，避免重复执行后台任务 | 后台计量、队列与定时任务只有预期写入者 |
| 新库或新主机迁移 | 全量快照 → 增量追平 → 短暂停写 → 最终核对 → 提升新库 | 有明确反向追平或恢复计划，否则不能直接回旧库 |

不得通过轮询 DNS 让两个独立主库同时承接随机写入。自然月额度、订阅有效期、计量账本与 checkpoint 必须有单一权威来源。

### 10.3 Schema 与数据兼容

按 expand → migrate → contract 分阶段演进：先新增兼容字段/索引和可兼容读取逻辑，再后台回填并核对，最后在旧版本退出后删除旧字段。禁止在同一次可回滚发布中直接删除旧版本仍依赖的列。

迁移核对至少包括账号主键和规范化 email、密码/MFA、角色/团队归属、proxy 身份、订阅起止时间、配额和暂停状态、账单 ledger/checkpoint。使用记录数、差异摘要及幂等回执核对，不将完整用户资料写入公开日志。

### 10.4 会话、OAuth 与凭据

稳定域名能减少回调地址变动，但不能自动保证会话兼容。发布前验证 token 签名/验证策略、Cookie 域和 SameSite、CORS allowlist、OAuth redirect URL、MFA 状态及撤销逻辑。密钥轮换须保留受控验证窗口，不为迁移临时取消校验。

既有迁移排除了旧会话，应预期需要重新登录；未来是否保留会话必须作为单独的明确策略。真实登录、MFA 和注册邮件闭环是切换门槛，不能仅以 `/readyz` 或空参数 400 替代。

DNS 管理凭据、部署凭据和 TLS 私钥继续通过 Vault/受保护运行时注入。复用现有证书时确认 SAN、有效期、私钥匹配和容器读取权限；续期必须能更新到新版本主机，并触发受控重载。

### 10.5 标准发布阶段与门槛

1. **准备**：确定源版本、目标版本、不可变镜像摘要、GitOps tag、Playbook 提交、数据兼容性与回滚窗口；保存当前 DNS。
2. **建环境**：IaC 创建目标资源，SSH/Playbook 配置，Doco-CD 收敛固定 tag；环境名、域名和资源池均为输入参数。
3. **预热**：恢复全部证书和真实 secret，校验 Caddy、Accounts、Billing ingress，重启后复测；验证观测链路。
4. **数据门槛**：明确唯一写入主库，必要时完成全量/增量迁移及最终核对。暂停旧后台写入者，防止重复计量或重复发送。
5. **业务门槛**：指定 Host/SNI 直连，完成登录/MFA、注册邮件、订阅读取、Free/Plus/Team 隔离、正向连接及跨池拒绝、计量验证。
6. **切换**：用户授权后更新稳定入口，核对 Cloudflare/API、公共 DoH 和普通客户端请求；记录缓存窗口。
7. **观察**：持续检查 5xx、TLS、登录错误、数据库连接、同步延迟、计量重复/缺失及 pool 分配。阈值与观察期在发布前约定。
8. **收尾**：确认缓存和长连接迁移、数据回执与账本一致，归档结果；观察期结束且获授权后下线旧版本。

每次都区分“PR 合并”“镜像构建”“Doco-CD 收敛”“接口健康”“业务验收”“DNS 生效”，不得合并为一个成功状态。

### 10.6 回滚决策

- 仅应用异常且 schema 向后兼容：回退应用固定 tag，保留当前权威数据库。
- DNS 指向或证书异常：优先修复目标版本证书/路由；需要回切时先确认新旧应用的数据兼容和权威库。
- 独立新库已产生写入：暂停变更并保全数据，完成追平或恢复决策后回切；DNS 回退不等于数据回退。
- 不自动删除新版本库或重置生产数据库；数据恢复和资源销毁使用独立受控步骤。

### 10.7 下一轮建议交付

- 在部署模板加入缺少 Billing allowlist、secret 占位值、品牌证书缺失时的失败校验。
- 将证书恢复/续期与 Caddy 部署顺序固化到 Playbook，避免仅依赖手工恢复。
- 提供只读预检与切换脚本：输入环境/版本/域名，先输出计划，保存回滚记录，再执行并回报 DNS 与 HTTPS 结果。
- 将数据库增量核对、单一后台写入者检查、真实认证与代理测试纳入可重复验收脚本。
- 发布归档同时保存目标版本、镜像摘要、迁移 checkpoint、DNS 前后记录和待办；凭据与个人数据继续排除。

这些是后续实施计划，不表示本轮已经交付对应自动化。
