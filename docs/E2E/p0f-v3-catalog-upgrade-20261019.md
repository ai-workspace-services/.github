# P0-F：V3 套餐目录与 Stripe Test 映射发布记录

> 当前统一入口见[控制面部署与迁移指南](../control-plane-deployment-and-migration.zh.md)。本文保留 2026-10-19 的 V3 回归范围与历史证据。

日期：2026-10-19（北京时间）。目标仅为既有 `web-saas-prod-v3`。

最终 GitOps tag：`prod-v3-billing-catalog-2026.10.19-r2`。
GitOps commit：`cc72b7b4275530ec11c9bf1adfe0ffdca23b9f5a`。
发布路径：SSH → Playbooks → GitOps → Doco-CD，target 为
`prod-v3-stripe-sandbox`。本次没有 dispatch CI 部署。PR 的 CI 检查与构建不等于部署。

V2、公共域名及共享 Vault/Observability 的部署保持原状；本次没有读取 V2 数据源、
重新同步 PROD 数据、重建表、创建测试用户、执行真实扣款或退款。

## 构件与运行身份

Accounts/Billing 在维护工作站构建并推送；Console 复用已发布的同一 main 源码提交构件。
主机只拉取固定 manifest/index digest，没有在目标主机编译。

| 服务 | 源码提交 | 固定 OCI digest |
| --- | --- | --- |
| Accounts | `883e18216e1170e1fbab6932af320a402eafe082` | `sha256:7c1ec4a1bd246b4d18046e20a8792c413bf72f824b635766087bf8d6339c6ffc` |
| Billing | `22cbfc06d3fe030c2d32fa076335853fa6aa2865` | `sha256:462a7835f649ffad3bd88cb7e51e8e6ea4deb1f8fa6509f6a5ed5d9259058db4` |
| Console | `121569cda404c6a9a9bc6e1784f2f8c37f0c82b8` | `sha256:9fc0fb54fb680d553fbce23bff1ca1bebba60b070d039ff76ce43d3a035f15b4` |

镜像使用对应仓库的 `sha-<完整源码 SHA>@sha256:<digest>` 引用，版本声明位于
GitOps `compose/web-saas/.env.prod-v3`。
Accounts/Billing 的 `/api/ping` 与声明的 image、tag、commit、version 匹配，
重启后均报告 checkpoint `2026101902`，`bootstrap_writes=false`。
Console `/api/ping` 的 `releaseImageRef`、`releaseCommit` 和 V3 Accounts API 地址匹配。

## 实际发布顺序

1. 核对 IaC 原始 inventory 与已验证 receipt 的 SHA-256，选择唯一 V3 记录；
   使用已确认的 SSH 主机身份，启用严格 host-key 检查。
2. 对 V3 创建加密备份并恢复到同机独立临时数据库，核对完整行、序列、schema、用户和订阅。
3. 合并兼容性修复，创建不可变 r1 tag，通过
   `select-doco-cd-release.yml` 选择 r1。先在旧 checkpoint `2026101703` 上确认新应用能够启动。
4. 每段迁移重新建立备份与恢复证据，再通过
   `web-saas-generation-data-operations.yml` 执行一个 checksum 固定的增量；相同请求重复执行一次。
5. 从指定 Stripe Test 账户同步目录，通过
   `web-saas-billing-price-mapping.yml` 写入已核对的 provider 引用，再重复执行验证无变化。
6. 合并 r2 声明，创建新 tag 并由 Playbook 选择。Doco-CD 更新数据库 checkpoint label，
   重新创建 Accounts/Billing，验证它们在升级后的数据库上能够启动。
7. 对最终 checkpoint `2026101902` 再建立加密备份并完成隔离恢复。

执行逻辑位于 Playbooks Roles；GitOps 只保存版本、目标与配置引用。本次未向 Toolkit 增加执行脚本。

## 增量与恢复证据

PostgreSQL 引擎维持 17；以下编号是数据迁移 checkpoint，不是 PostgreSQL 引擎版本。

| 起始 checkpoint | 目标 checkpoint | 已审核 SQL SHA-256 |
| --- | --- | --- |
| 2026101703 | 2026101901 | `b9fee298512e7d888fe619917c8238120f0e227f4ea348e59397d074c41f878d` |
| 2026101901 | 2026101902 | `53f9aaf7c56a14fd7c132c6649b79582cd2063f8903b94efb4e23cbf4895437c` |

两段均使用内嵌审核 SQL 的 `migratectl controlled-migrate`，通过 advisory lock、锁等待和
statement timeout 约束执行；SQL、版本和 checksum 历史在同一事务提交。
每段重复执行均通过，最终版本精确 `2026101902 / dirty=false`。
维护二进制 SHA-256：`3db6147ea83cd75de92a9a3a11312364af5e94191ad18f271749a6f704af7dcd`。

成功检查点的文件均为 `account.dump.enc`，位于
`/data/backups/web-saas/prod-v3/<release-tag>/<run-id>/`：

| release-tag | run-id | 备份 checkpoint | 加密归档 SHA-256 |
| --- | --- | --- | --- |
| `prod-v3-billing-catalog-2026.10.19-r1` | `20261019014506` | 2026101703 | `097802907281309b0ac041916824db73270459cfa4fbb1d02a6bbeb263751703` |
| `prod-v3-billing-catalog-2026.10.19-r1` | `20261019014507` | 2026101901 | `989db3c29a8ef05147651c8c936b0eebc2b229bfc21445b856471c36da62a7cc` |
| `prod-v3-billing-catalog-2026.10.19-r2` | `20261019014508` | 2026101902 | `853d2bcdfeedd35499071d30880ebef46d802629ae597f59937a4e3e9104e582` |

这些检查点均通过独立临时数据库的完整行与序列指纹比较，临时数据库随后按 OID 校验清理。
目录权限 `0700`，归档文件 `0600`；没有创建明文 dump 文件。

备份密钥引用：CLI path `kv/prod-v3/backups`，key `web_saas_release_passphrase`。
首次缺失时由 Role 在内存生成随机密钥，通过 Vault CAS=0 保存并回读；已有路径不会覆盖。
密钥不进入 inventory、extra-vars、Git、进程参数或公开回执。

## 套餐、币种与价格映射

| 套餐 | 金额 | 权益 |
| --- | --- | --- |
| Plus 月付 | ¥20/月 | 每月 20 GiB |
| Pro 月付 | ¥50/月 | 每月 50 GiB |
| Pro 年付 | ¥500/年 | 不限流量 |

| PAYG 币种 | 快捷档位 | 自定义充值范围 |
| --- | --- | --- |
| CNY | ¥50 / ¥100 / ¥200 | ¥10–¥200，整数金额 |
| USD | $20 / $50 / $100 | $5–$100，整数金额 |

USD/CNY 独立余额；PAYG 与付费订阅的互斥规则及金额边界由 Accounts 校验。
旧档位和旧 Pro 记录保留用于历史核对，只停止新的购买展示。

九个活动售卖项的金额、币种、周期与 Stripe Test Price 引用逐项匹配。
Stripe 已有 ¥50/¥100 Price 保留；七项新引用在一笔带审计的事务中写入。
重复映射 `changed=0 / audit_records=0`，没有重写已有不同引用或制造重复审计。
映射回执 SHA-256：`79bbadc7d82c7afc18040e276483903c25539e6941089264684f5f0fc1245bb4`。

Stripe 密钥引用仍为 `kv/prod/billing-service` 下的：

- `SANDBOX_STRIPE_SECRET_KEY`
- `SANDBOX_STRIPE_WEBHOOK_SECRET`

通过只返回布尔结论的比较，确认运行容器中的两个值与当前 Vault 一致。
未输出值或 secret 指纹。Webhook URL 由 GitOps 环境注册表声明为：
`https://accounts-selfhost-prod-v3.svc.plus/api/billing/stripe/webhook`。
Stripe 中对应端点存在，六类当前必需事件齐全。

## 非破坏性验收结果与边界

- Accounts/Billing HTTPS `/readyz` 均成功；三个服务运行身份与固定 digest 匹配。
- Accounts/Billing 的新容器 checkpoint label 为 `2026101902`，重启计数均为 0；
  PostgreSQL 容器的启动时间与 image ID 和发布前一致。
- 公共套餐 API 返回九项正确的已映射价格；20 GiB、50 GiB、不限流量标记正确；旧售卖档位不再返回。
- 用户 33、`subscription_records` 12、旧 `subscriptions` 1 均保留。
- `users`、两类订阅、`account_billing_profiles`、`billing_ledger`、发票、付款、退款和流量桶的
  完整行指纹与升级前一致。非空样本包含 12,218 条用量账本、1 张发票、1 笔付款和 2 条退款记录。
- 未登录 Console `/panel/subscription` 返回 307；未登录 Checkout 返回 401；无有效签名的 Webhook 返回 401。
- 未自动添加用户、修改现有用户分组/套餐或产生真实交易。

原密码登录、登录后的三张套餐卡片、MFA 后 Stripe Sandbox Checkout、Stripe 实际事件投递、
订阅生效/充值到账及退款闭环仍需使用现有授权账户验收；以上探针和目录核验不替代这些步骤。
P0-F 因此仍为进行中，不能仅凭部署健康把完整支付闭环标记为完成。

## 中断处理与回滚边界

首次尝试在动态 Role 的 YAML 解析阶段停止，未执行迁移 SQL；另一尝试被应用账户缺少 schema
CREATE 权限拦截，事务回滚，仍为 clean `2026101703`。失败检查点保留，未 force 迁移版本或清除 dirty。

修复保留应用权限限制，改用精确 V3 PostgreSQL 容器中的本地维护 socket 执行审核 SQL，
不运输数据库密码；重新走完整备份恢复门禁后成功。静态 import fixture 现在可在连接主机前解析全部相关 Role。

数据库升级后应用回退至少需要 r1 的兼容构件。r1/r2 的应用 digest 相同，均接受审核后的
1901/1902 checksum 历史。更早、只接受 1703 的应用不能直接作为当前库的回退版本。
优先前向修复；保留新增目录和历史记录，不执行破坏性 down，不覆盖正在服务的数据库。

维护站的附加本地 CLI 复验遇到容器引擎无响应，未计为验收通过，也没有重启其他本地容器。
临时 fixture `accounts-catalog-runtime-test-20261019` 的清理待该引擎恢复后处理；远端演练未受影响。

## 变更索引

- [Accounts #241](https://github.com/ai-workspace-services/accounts/pull/241)、[#242](https://github.com/ai-workspace-services/accounts/pull/242)、[#243](https://github.com/ai-workspace-services/accounts/pull/243)：新目录、完整档位、运行 checkpoint 与安全价格同步。
- [Portal #449](https://github.com/ai-workspace-services/portal/pull/449)：新版本套餐展示。
- [Billing #52](https://github.com/ai-workspace-services/billing-service/pull/52)：审核 checkpoint 与 checksum 检查。
- [Playbooks #680](https://github.com/ai-workspace-infra/playbooks/pull/680)、[#681](https://github.com/ai-workspace-infra/playbooks/pull/681)、[#682](https://github.com/ai-workspace-infra/playbooks/pull/682)、[#683](https://github.com/ai-workspace-infra/playbooks/pull/683)、[#684](https://github.com/ai-workspace-infra/playbooks/pull/684)：代际数据门禁、备份密钥、审计映射、有效回执、执行器与维护连接。
- [GitOps #468](https://github.com/ai-workspace-infra/gitops/pull/468)、[#469](https://github.com/ai-workspace-infra/gitops/pull/469)：r1 兼容发布与 r2 新 checkpoint 重验。
- [P0-F #21](https://github.com/ai-workspace-services/.github/issues/21)：后续 Sandbox 业务验收进度。
