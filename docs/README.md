# 部署、迁移与运行记录索引

本目录索引指向既有流程和历史回执，不另设执行规范。流程权威入口为[Selfhost 控制面部署与核心数据迁移](control-plane-deployment-and-migration.zh.md)；实际运行声明仍由对应 owner 仓库管理。

| 阅读目的 | 文档 |
| --- | --- |
| 统一部署与迁移流程 | [Selfhost 控制面部署与核心数据迁移](control-plane-deployment-and-migration.zh.md) |
| V2 部署及 V1→V2 历史交接 | [V2 初始部署](prod-v2-deployment.md)、[V1→V2 升级与切换](prod-v2-upgrade-cutover-20261016.md)、[V2 升级恢复](prod-v2-upgrade-recovery-20261018.md) |
| V2→V3→V4→V5 运行基线、故障、迁移和回归证据 | [V4→V5 基线与复盘索引](https://github.com/ai-workspace-services/knowledge/blob/main/content/02-iac-devops/cloud-infrastructure-devsecops-baseline/17-prod-v4-v5-baseline-and-upgrade-retrospective.zh.md) |
| V2→V3 快照与升级复盘 | [V2→V3 历史索引](https://github.com/ai-workspace-services/knowledge/blob/main/content/02-iac-devops/cloud-infrastructure-devsecops-baseline/15-prod-v2-v3-snapshots-and-upgrade-retrospective.zh.md) |
| V3→V4 运行基线与升级复盘 | [V3→V4 历史索引](https://github.com/ai-workspace-services/knowledge/blob/main/content/02-iac-devops/cloud-infrastructure-devsecops-baseline/16-prod-v3-v4-baseline-and-upgrade-retrospective.zh.md) |
| 服务级 V5 配置路径与部署回执 | [V5 运行基线与快照清单](https://github.com/ai-workspace-services/knowledge/blob/main/content/02-iac-devops/cloud-infrastructure-devsecops-baseline/records/prod-v5-20261023/prod-v5-runtime-and-snapshot-baseline-20261023.zh.md) |
| V5 故障时间线 | [V5 部署流程复盘](https://github.com/ai-workspace-services/knowledge/blob/main/content/02-iac-devops/cloud-infrastructure-devsecops-baseline/records/prod-v5-20261023/prod-v5-deployment-postmortem-20261023.zh.md) |
| V5 净室重建、在线 users-only 与三轮实际重验 | [2026-10-24 执行回执](https://github.com/ai-workspace-services/knowledge/blob/main/content/02-iac-devops/cloud-infrastructure-devsecops-baseline/records/prod-v5-20261023/prod-v5-cleanroom-deployment-migration-validation-20261024.zh.md)，实际结果以每轮状态为准 |
| V5 套餐/订阅/账务追加、三轮真实 no-op 与实时采集 | [在线业务追加与流量重验](https://github.com/ai-workspace-services/knowledge/blob/main/content/02-iac-devops/cloud-infrastructure-devsecops-baseline/records/prod-v5-20261023/20261024-prod-v5-business-append-and-traffic-regression.zh.md) |
| V5 修复后有业务数据的快照、隔离恢复及异机校验 | [环境快照与恢复回执](https://github.com/ai-workspace-services/knowledge/blob/main/content/02-iac-devops/cloud-infrastructure-devsecops-baseline/records/prod-v5-20261023/20261024-prod-v5-post-repair-environment-snapshot.zh.md) |

V1 独立运行基线的 Knowledge 文件缺失，现有 V1→V2 历史记录只提供升级交接，不冒充 V1 原始运行清单。链接目标缺失或后续记录尚未合并时，应保留该缺口并在对应 PR 后复核。

2026-10-24 当前环境修订：以[V5 最新运行总表](https://github.com/ai-workspace-services/knowledge/blob/main/content/02-iac-devops/cloud-infrastructure-devsecops-baseline/records/prod-v5-20261023/prod-v5-runtime-and-snapshot-baseline-20261023.zh.md)区分当前状态与历史采样；[公共 Console 白屏与路由回归](https://github.com/ai-workspace-services/knowledge/blob/main/content/02-iac-devops/cloud-infrastructure-devsecops-baseline/records/prod-v5-20261023/20261024-prod-v5-public-console-route-repair.zh.md)记录 DNS 校验之后发现的入口遗漏。公共数据库别名、代理注册、实际流量、逻辑快照与最终写入交接分别判定。

巡检权限与恢复后重验：[统一流程只读巡检章节](control-plane-deployment-and-migration.zh.md#系统与业务只读巡检) · [V5 执行回执](https://github.com/ai-workspace-services/knowledge/blob/main/content/02-iac-devops/cloud-infrastructure-devsecops-baseline/records/prod-v5-20261023/20261024-prod-v5-inspection-access.zh.md)。


2026-10-25 V5 K3s all-in-one：核心控制面（Web-SaaS、Vault Server、Grafana/观测栈）汇聚到一台 Linode 2C4G VPS 的[部署快照与完成状态](https://github.com/ai-workspace-services/knowledge/blob/main/content/02-iac-devops/cloud-infrastructure-devsecops-baseline/records/prod-v5-k3s-20261025/prod-v5-vps-to-k3s-runtime-and-acceptance-20261025.zh.md)，以及[可复用 23 组 Markdown 验收 TODO](https://github.com/ai-workspace-services/knowledge/blob/main/content/02-iac-devops/cloud-infrastructure-devsecops-baseline/records/prod-v5-k3s-20261025/deployment-migration-acceptance-checklist.template.zh.md)。降本目标、实际资源回收及账单结果分别记录。
