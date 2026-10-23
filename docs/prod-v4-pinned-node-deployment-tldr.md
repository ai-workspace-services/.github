# PROD V4：固定版本节点部署 TL;DR

> 历史 V4 验收背景保留。当前控制面与迁移入口见[统一部署与迁移指南](control-plane-deployment-and-migration.zh.md)，候选入口尚待隔离联调验收。

控制面部署模式：**SSH → Playbook → 固定 GitOps → Doco-CD**。节点由 Playbook 管理原生 systemd 服务，控制面由 Doco-CD 收敛；节点安装不替代控制面发布。

背景：[PROD V4 运行基线与快照清单](https://github.com/ai-workspace-services/knowledge/blob/main/content/02-iac-devops/cloud-infrastructure-devsecops-baseline/records/prod-v3-v4-20261020/prod-v4-runtime-and-snapshot-baseline-20261021.zh.md)。它记录指定时间的运行事实；每次部署以新选择的固定 GitOps commit 为准。

## 快速入口

实现：[Playbooks #721](https://github.com/ai-workspace-infra/playbooks/pull/721)（草稿）。当前支持固定源码检查、发布合同校验和 plan/check/apply；完整节点 profile 及全新 VPS 验收尚在补齐。以下是接口示例，尖括号必须替换为已审查发布值，不能直接复制为生产安装命令。

```bash
export PLAYBOOKS_COMMIT='<包含部署入口的已审查40位commit>'
export GITOPS_COMMIT='<包含本节点发布合同的已审查40位commit>'
export NODE_RELEASE_MANIFEST='<GitOps相对路径.json>'

# 在上述固定 Playbooks checkout 内执行；默认只预览。
bash scripts/bootstrap-pinned-xconnect.sh --mode plan
bash scripts/bootstrap-pinned-xconnect.sh --mode check
bash scripts/bootstrap-pinned-xconnect.sh --mode apply
```

维护主机需具备 Git、Python 3.9+、Ansible、有效 Vault 会话及可信 SSH 主机身份。VPS 本机执行时使用审核过的 local inventory；远端执行时使用 IaC 输出的 CMDB/inventory。入口不安装浮动依赖，不接受 main/latest 替代固定源码，不通过命令行传递凭据。

## 节点类型

| 类型 | 部署和权限边界 |
| --- | --- |
| 独立节点 | 独立代理运行，不连接托管控制面；单独的已审核 profile 与验证步骤。 |
| shared | 公共共享资源；从统一 Vault 权威来源解析服务凭据。 |
| plus | 按控制面权益开放资源，不将展示套餐直接当作节点鉴权。 |
| team | 专属节点凭据及团队范围；凭据缺失或范围不匹配立即失败，不回退共享凭据。 |

Pro 使用可继承的公共资源权益，Team 只向 root／所属团队开放。发布合同不得把界面隐藏当作后端授权。

## 部署通过条件

1. IaC、Playbooks、GitOps、Agent/Xray/Exporter/Vector/Caddy 构件都有固定版本和 checksum/digest，下载后由执行 Role 核对。
2. Vault 读取及校验在配置修改前完成；敏感运行文件 root:root、0600；空值不能覆盖已有配置。
3. 节点身份、区域、资源池和团队范围符合合同；证书及 SNI 正常，状态上报由实际控制面接受。
4. 流量仍经 **Xray Exporter → Vector → Billing → PostgreSQL → Accounts**；保留 Vector 统一上报，不启用 Billing 主动拉取或 Agent 直报。
5. 区分鉴权成功、快照新鲜、分钟桶写入、非零字节和用户归属；真实零流量不得通过合成账本冒充业务成功。
6. 同版本重跑不重复创建资源、不重置凭据／计数、不产生非预期服务重启；至少观察两个相关完整采集周期。

## 当前验收范围与证据

历史七节点 Token 修复已经执行，不等同于本入口完成七节点全新部署。新入口在独立 Vultr 验收资源上验证，现有环境不参与配置变更。

本次按需测试目标已确认：东京区、2 vCPU／2 GB、套餐自带 65 GB 系统盘、独立 25 GB 数据盘及公网 IP。独立 state、明确验收标签；部署结果、重复执行及链路验证须分别记录。验收资源创建和自动清理是两个操作，清理需列出精确资源后确认。

本历史验收采用 `<service>-<ENV>-v4.<DOMAIN_BASE>` 域名，例如
`console-sit-v4.<base domain>`、`accounts-sit-v4.<base domain>`、
`billing-sit-v4.<base domain>`、`postgresql-sit-v4.<base domain>`。
当前应在固定 GitOps 配置中显式声明各环境域名，使用
`install-control-plane.sh --config <GitOps相对路径.yaml> --gitops-ref <40位SHA> --check`
委派 Playbooks 预检，详见统一指南。本仓库没有独立的域名 Python renderer；不再引用不存在的命令。
DNS 记录由 IaC 管理，验收编号只进入 state/回执。PostgreSQL 保持隧道访问，不开放公网数据库端口。

以相关 PR 的最新验收回执为准。当前文档不声称新机／重复部署已经通过，不发布不存在的安装 tag，不修改现有 DNS、生产节点或账本。
