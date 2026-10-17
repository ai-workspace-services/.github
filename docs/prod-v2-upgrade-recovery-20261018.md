# PROD V2 手工升级恢复记录（2026-10-18）

发布路径为 SSH → Playbooks → GitOps → Doco-CD。应用镜像在维护工作站编译、构建和推送；主机只拉取固定 digest。GitHub PR 检查属于代码验证，本次没有 dispatch CI 部署。

## 范围与身份

- 目标：现有 `web-saas-prod-v2`；主机和 `/data` 数据盘均保留。
- GitOps 目标：`prod-v2`，使用 `.doco-cd.prod-v2.yml` 和 `compose/web-saas/.env.prod-v2`。
- 最终候选：`prod-v2-2026.10.18-r5`；r4 已恢复业务，r5 仅补 Billing 版本元数据解析。
- r5 GitOps 提交：`060dadeca933700254d9153632345f0fc8b402d7`。
- Accounts 源：`8c7ecd9cf4bb711b6ad491b2ac299f57b4d65184`。
- Billing 源：`8cdd4e95b83c96b7c4586c58eca22bcec821acf1`。
- Console 源：`bef82c807cf66cd6ad50036ba4fafaf33c33db32`。
- Accounts OCI digest：`sha256:6d70a8ff8319c0fc058fd8faaea212d74cd85a01bb7a00a1c1840be1e8fc5e7f`。
- Billing OCI digest：`sha256:ae7b56e2e01011f9f32b93a4106f1897eab71e857c7c9f2ecf676c95fdb65bbb`。

主机 PostgreSQL 的实际挂载为 `/data/postgresql`。存在同名历史 Docker volume 不代表业务正在使用它；以 `docker inspect` 的实际挂载为准。

## 故障与修复

1. 镜像 config digest 被误当作可拉取 manifest digest，导致 GHCR 404。后续固定 OCI manifest/index digest，并在主机拉取验证。
2. 旧库为 `2026101502 / dirty=false`，新 Accounts 要求精确 `2026101703`。前序执行已完成三段受控增量迁移，禁止直接 force 版本或初始化数据库。
3. Accounts 把迁移器的 `accounts_controlled_migration_history` 当成未知业务表。修复只排除此固定内部审计表，保留未知业务关系、列定义与权限校验。
4. PostgreSQL 不接受 Go 格式 `5m0s`。修复迁移器以数值毫秒设置超时；集成测试覆盖真实五分钟配置及超时回滚。
5. Billing 仅接受旧审核版本。新增精确的 `2026101703` 检查，业务表数量为 73；迁移审计表不计入业务范围，未知版本仍拒绝。
6. 维护角色创建的新邮件表缺少应用角色 DML 权限。Playbook 只对九张已审核新表授权，未变更表属主、角色权限等级或全局默认权限。
7. Billing 解析 `:sha-<commit>@sha256:<digest>` 时把 digest 当成 tag。r5 修复先移除 digest 后解析 tag，同时保留完整原始 IMAGE。

原计划把迁移审计表改名为 `system_release_checkpoints` **未执行**；正式修复保留原表名和三条 checksum 记录。

## 备份、恢复和增量 SQL

发布前自定义格式备份保存在主机：

`/data/backups/web-saas/prod-v2/prod-v2-2026.10.18-r3/20261017T163132Z/account.dump`

目录权限 `0700`，文件 `0600`。归档 SHA-256：

`f166fdf404e16d15fcd55b62e0b23b865f6a79efbf373749cfd28b368cf74dde`

该文件为 PostgreSQL custom-format 备份，本记录不将其表述为加密备份。凭据、备份内容和用户级标识不进入公开文档。

| 起始版本 | 目标版本 | SQL SHA-256 |
| --- | --- | --- |
| 2026101502 | 2026101701 | 21da5da1f05a79707bac527147a07b58d84dcadeab96933935a03ca8f7e25a1b |
| 2026101701 | 2026101702 | 6453608516d620773565b343d2397a0d3dc2415332a86f989a8952bcb044c5eb |
| 2026101702 | 2026101703 | 28ca2c8673875ba6e13ffa0b8bf11828a0f5c2975f6a305de4fdacae9f3ff77e |

本续接开始时生产数据库已经升级，因此隔离恢复证据是本轮补齐，不能倒述为首次迁移前已经完成。后续发布应先完成备份恢复验收，再执行真实升级。

实际验证步骤：

1. 暂停失败后持续重试的 Doco-CD 和 Accounts/Billing 写入端。
2. 在独立 Docker 网络、无生产挂载和宿主机端口的临时 PostgreSQL 容器恢复备份；数据使用临时内存文件系统。
3. 恢复得到旧版本 `2026101502`、30 用户、12 条 `subscription_records`、12,019 条 `billing_ledger`。
4. 对用户全行、两类订阅表、发票/付款/退款、用量账本和流量桶计算稳定序列指纹，与真实库比对相等。仅输出布尔结论，未输出行内容。
5. 在恢复库按表中 checksum 复跑三段迁移，到达 `2026101703 / dirty=false`；审计记录数量为 3。
6. 使用修复后的迁移二进制重复执行最后一步，五分钟配置被接受，已有 checksum 记录匹配，未重复应用 SQL。
7. 在隔离恢复库以关闭后台写入的应用配置启动修复镜像；Accounts 和 Billing `/readyz` 均返回 ready。
8. 清理本轮专用临时应用、数据库容器及隔离网络，保留原始备份。

## Playbooks 与 GitOps 发布步骤

`ai-workspace-infra/playbooks` 的 `select-doco-cd-release.yml` 与 `doco_cd_release_selection` Role 仅更新已有 Doco-CD 的 `POLL_CONFIG`，显式保留 `target=prod-v2`，验证 Compose 后重建控制器；不重复安装 Docker，也不删除应用容器、数据卷或重写凭据。

`apply-web-saas-migration-grants.yml` 与 `web_saas_migration_grants` Role 要求精确 clean checkpoint、已有非超级用户角色和显式新表列表。在本次 `2026101703`，对九张新邮件表授予 SELECT/INSERT/UPDATE/DELETE，用户表及迁移元数据禁止作为授权目标。

调用示例（inventory 和变量文件由受控维护环境提供，不提交实际主机连接事实或凭据）：

```bash
ansible-playbook select-doco-cd-release.yml \
  -i /path/to/verified-inventory.yml \
  -e @/path/to/reviewed-release-selection.yml \
  --limit web-saas-prod-v2
```

GitOps PR 合并后创建新不可变 tag，再由 Playbook 选择。失败 tag 保留，不移动 r1–r4。修复早期误改的旧 `.env.prod` 已单独恢复到发布前值，不派发旧 PROD 部署。

## 已观察到的生产验收与边界

r4 恢复后的实测：

- Accounts/Billing `/readyz` 均为 200，运行角色 primary，schema `2026101703`，`bootstrap_writes=false`。
- 用户 30、订阅记录 12 保留；用量账本由 12,019 增长到 12,029，服务恢复计量。
- Free 套餐 `included_quota_bytes=5368709120`（5 GiB）；本次配额迁移保留当月使用量。
- Accounts/Billing/Console/PostgreSQL 新容器重启计数均为 0。
- 主机直连 HTTPS 与主机侧公网 URL：Accounts readyz 200；未登录 Console `/panel` 307。
- Doco-CD 成功对账后下一轮轮询未再次部署，说明 release 已稳定。

管理员登录后的页面操作、终端代理连接和真实支付不由以上探针代替。原密码登录按用户此前约定由用户手工验证；本次没有真实扣款或退款测试。

回滚只选择兼容 `2026101703` 的已验证应用 digest，例如本次正常运行的 r4。旧应用若只接受 `2026101502`，不能在当前库上直接回退。数据库修复优先前向处理，不执行破坏性 down、不覆盖生产数据库，也未进行真实 PROD 回滚演练。

最终 r5 对账于北京时间 2026-10-18 01:21:45 成功，Doco-CD 解析的提交与 tag 均匹配。r5 只更换 Billing：Accounts、Console 和 PostgreSQL 的启动时间保持 r4 恢复后的值，四个服务重启计数均为 0。

Accounts `/api/ping` 报告源码 `8c7ecd9c…`、完整固定镜像引用及 schema `2026101703`；Billing 报告源码 `8cdd4e95…`、完整固定镜像引用及相同 schema。两者配置的数据库身份指纹相同，`bootstrap_writes=false`、`proxy_uuid_rotator=false`，`/readyz` 均成功。真实用量账本继续增长到 12,070 条，用户/订阅记录仍为 30/12；Free 套餐仍为 5 GiB。主机侧公网 Accounts readyz 200、Console 未登录跳转 307。

## 变更索引

- [Accounts #234](https://github.com/ai-workspace-services/accounts/pull/234)：迁移审计范围及 PostgreSQL 超时格式。
- [Billing #50](https://github.com/ai-workspace-services/billing-service/pull/50)：审核通过的 2026101703 runtime checkpoint。
- [Billing #51](https://github.com/ai-workspace-services/billing-service/pull/51)：digest-qualified IMAGE 元数据。
- [Playbooks #672](https://github.com/ai-workspace-infra/playbooks/pull/672)：只选择已安装 Doco-CD 的 release。
- [Playbooks #673](https://github.com/ai-workspace-infra/playbooks/pull/673)：增量迁移后的显式应用授权。
- [GitOps #456](https://github.com/ai-workspace-infra/gitops/pull/456)：r4 恢复构件。
- [GitOps #457](https://github.com/ai-workspace-infra/gitops/pull/457)：恢复旧 PROD profile 的非目标变更。
- [GitOps #458](https://github.com/ai-workspace-infra/gitops/pull/458)：r5 Billing 追溯构件。
