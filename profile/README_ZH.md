<!-- Target: ai-workspace-services/.github → profile/README_ZH.md (English default: profile/README.md) -->
<!-- Style mirrors ai-workspace-infra/.github profile/README.md. Spec: org-homepage-handoff.md -->

<p align="center">
  <img src="../assets/ai-workspace-services-poster.png" alt="AI Workspace Services poster" width="100%" />
</p>

<h1 align="center">ai-workspace-services</h1>
<p align="center"><strong>开放的 AI 云原生服务底座 | Open Cloud-Native Services for AI Workspaces</strong></p>

<p align="center">
  <a href="https://console.svc.plus"><img src="https://img.shields.io/badge/Console-SVC%2B-0B5C7A?style=for-the-badge" alt="Console" /></a>
  <a href="https://github.com/ai-workspace-services"><img src="https://img.shields.io/badge/GitHub-Organization-181717?style=for-the-badge&logo=github" alt="GitHub Organization" /></a>
  <a href="https://github.com/ai-workspace-services?tab=repositories"><img src="https://img.shields.io/badge/Public%20Repos-10-2F855A?style=for-the-badge" alt="Public Repositories" /></a>
  <a href="#-快速开始"><img src="https://img.shields.io/badge/Self--Host-3%20min-blue?style=for-the-badge&logo=gnubash&logoColor=white" alt="Self-Host in 3 minutes" /></a>
  <a href="https://github.com/ai-workspace-services/accounts"><img src="https://img.shields.io/badge/Auth-GitHub%20%7C%20Google%20OAuth-black?style=for-the-badge&logo=openid&logoColor=white" alt="OAuth" /></a>
</p>

<p align="center">
  <a href="https://github.com/ai-workspace-services">🌐 English</a> ｜ <strong>🇨🇳 简体中文</strong>
</p>

---

## 🇨🇳 组织概览

`ai-workspace-services` 是 AI Workspace Lab 的应用服务组织，构建在 [`ai-workspace-infra`](https://github.com/ai-workspace-infra) 基础设施之上。我们把统一身份、AI 协作工作空间与全球低延迟连接整合为一套开箱即用的服务，既可云端免运维使用，也可 3 分钟自建。

### 我们的产品准则

- **开放无锁定**：全部服务 Apache-2.0 开源，可自托管，可随时迁出。
- **身份统一**：一个账户贯通控制台、计费与所有产品，支持 GitHub / Google 一键登录。
- **低延迟优先**：面向 Cursor、Claude、ChatGPT 等 AI 工具的流式体验做网络优化。
- **多租户与可治理**：租户隔离、密钥治理与可观测性为默认能力。

### 常用访问入口

- **统一控制台**: [console.svc.plus](https://console.svc.plus)
- **知识库与文档**: [knowledge](https://github.com/ai-workspace-services/knowledge)
- **基础设施组织**: [ai-workspace-infra](https://github.com/ai-workspace-infra)
- **固定版本节点部署**: [PROD V4 一键部署 TL;DR](../docs/prod-v4-pinned-node-deployment-tldr.md)

---

## 🧩 三大核心产品 (Core Products)

<table>
<tr>
<td width="33%" align="center" valign="top">
  <h3>⚡<br/><a href="https://console.svc.plus/products/xstream">XConnect</a></h3>
  <p><strong>AI 工作空间加速连接</strong></p>
  <p align="left"><sub>为 AI 工具流式响应优化延迟，内核级 BBR + FQ，自动 TLS；支持 1 VPS + 1 域名自建或托管 SaaS。</sub></p>
</td>
<td width="33%" align="center" valign="top">
  <h3>🤖<br/><a href="https://console.svc.plus/products/xworkmate">XWorkmate</a></h3>
  <p><strong>自主 AI 协作工作空间</strong></p>
  <p align="left"><sub>持久上下文执行多步骤 AI 工作流，多 Agent 团队协作与状态追踪。</sub></p>
</td>
<td width="33%" align="center" valign="top">
  <h3>🛡️<br/><a href="https://console.svc.plus">Open-Platform Core</a></h3>
  <p><strong>统一身份与多租户核心</strong></p>
  <p align="left"><sub>GitHub / Google OAuth 一键登录，租户隔离、密钥治理与全链路可观测。</sub></p>
</td>
</tr>
</table>

---

## 🔀 服务架构 (Service Architecture)

```mermaid
flowchart LR
    U[用户 / AI 工具] --> E[edge-gateway<br/>frontend-router]
    E --> P[portal<br/>统一控制台]
    E --> G[ai-aggregator-gateway<br/>模型聚合网关]
    P --> S{核心服务}
    S --> A[accounts<br/>身份 · MFA]
    S --> B[billing-service<br/>计费]
    S --> C[content-service<br/>内容]
    A & B & C --> D[(postgresql<br/>pgvector · 队列)]

    style U fill:#F3F4F6,stroke:#9CA3AF,stroke-width:1px
    style E fill:#DBEAFE,stroke:#3B82F6,stroke-width:2px
    style P fill:#DBEAFE,stroke:#3B82F6,stroke-width:1px
    style G fill:#F3E8FF,stroke:#8B5CF6,stroke-width:1px
    style S fill:#FEF3C7,stroke:#F59E0B,stroke-width:1px
    style D fill:#ECFDF5,stroke:#10B981,stroke-width:2px
```

---

## 🚀 快速开始

| 方式 | 适合 | 入口 |
| :--- | :--- | :--- |
| ☁️ **云端免运维** | 立即体验 | 访问 [console.svc.plus](https://console.svc.plus)，GitHub / Google 登录 |
| 📱 **跨平台客户端** | 日常使用 | [下载 XConnect 预览版](https://console.svc.plus/products/xstream)（macOS / Windows / iOS / Linux） |
| 🖥️ **自托管控制面** | 自建 Console、Accounts、Billing 和 PostgreSQL | 使用审核过的 SSH → Playbook → 固定 GitOps → Doco-CD 部署路径 |
| 🔌 **Proxy 节点** | 为已有控制面增加一个 XConnect 边缘节点 | 1 台 VPS + 1 个节点域名，执行下方代理脚本 |

```bash
# 仅部署 Proxy 节点，不会部署自托管控制面。
curl -fsSL https://raw.githubusercontent.com/ai-workspace-services/.github/main/scripts/setup-proxy.sh \
  | bash -s -- --node xhttp.example.com
```

自托管控制面使用独立域名，例如
`console-sit-v4.<base domain>`、`accounts-sit-v4.<base domain>`、
`billing-sit-v4.<base domain>`、`postgresql-sit-v4.<base domain>`。
PostgreSQL 只允许隧道访问，不开放公网数据库端口。

---

## 📦 核心仓库矩阵 (10 Repositories)

| 仓库 (Repository) | 类型 / 定位 | 说明 / 功能特性 |
| :--- | :--- | :--- |
| [`portal`](https://github.com/ai-workspace-services/portal) | `Control Panel` | 开放云控制台，构建摆脱厂商锁定的“逃生舱” |
| [`accounts`](https://github.com/ai-workspace-services/accounts) | `Identity & Auth` | 生产级账户服务：认证、MFA 与 Agent 协同，svc.plus 生态核心 |
| [`billing-service`](https://github.com/ai-workspace-services/billing-service) | `Billing` | 计费与订阅服务 |
| [`content-service`](https://github.com/ai-workspace-services/content-service) | `Content API` | 内容管理与分发服务 |
| [`edge-gateway`](https://github.com/ai-workspace-services/edge-gateway) | `Edge Ingress` | 边缘入口网关 |
| [`frontend-router`](https://github.com/ai-workspace-services/frontend-router) | `Routing` | 前端路由与多站点分发 |
| [`ai-aggregator-gateway`](https://github.com/ai-workspace-services/ai-aggregator-gateway) | `AI Gateway` | AI 聚合网关契约、适配器与 Home-Lab 部署包 |
| [`postgresql`](https://github.com/ai-workspace-services/postgresql) | `Database & Vector` | PostgreSQL + 向量检索 + 中文分词 + 消息队列 |
| [`knowledge`](https://github.com/ai-workspace-services/knowledge) | `Knowledge Base` | 工程咨询、技术长文与 Workshop 文档资产 |
| [`.github`](https://github.com/ai-workspace-services/.github) | `Org Profile & CI` | 组织主页与发布状态自动化 |

---

## 🚦 发布状态 (Release Status)

<!-- RELEASES:START — CI 生成，请勿手改 -->
| 环境 | 定位 | 状态 | 最新版本 | 更新时间 (UTC) |
| :--- | :--- | :--- | :--- | :--- |
| `prod` | 生产发布 | ![none](https://img.shields.io/badge/-暂无发布-lightgrey) | — | — |
| `uat` | 预发验证 | ![live](https://img.shields.io/badge/-live-2F855A) | `uat-platform-rebuild-2026.07.27-r4` | 2026-07-27 05:38 |
| `sit` | 验证集成 | ![live](https://img.shields.io/badge/-live-2F855A) | `4a7176c` | 2026-07-27 05:40 |

<details>
<summary>镜像清单 (Image Tags)</summary>

| 环境 | 镜像 | Tag |
| :--- | :--- | :--- |
| sit | console | `4a7176c` |
| uat | accounts | `ca13285` · `latest` |
| uat | billing-service | `uat-platform-rebuild-2026.07.27-r4` |
| uat | docs | `uat-platform-rebuild-2026.07.27-r4` |
| uat | postgresql | `uat-platform-rebuild-2026.07.27-r4` |

</details>
<!-- RELEASES:END -->

---

<p align="center">
  <strong>开放 · 统一 · 低延迟 · 可自建 · AI 原生</strong><br/>
  <sub>Open · Unified · Low-Latency · Self-Hostable · AI-Native</sub>
</p>
