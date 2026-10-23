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

V1 独立运行基线的 Knowledge 文件缺失，现有 V1→V2 历史记录只提供升级交接，不冒充 V1 原始运行清单。链接目标缺失或后续记录尚未合并时，应保留该缺口并在对应 PR 后复核。
